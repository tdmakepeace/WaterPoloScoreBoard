
import errno
from time import sleep
import socket
from typing import Optional, TypedDict, Union
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, has_request_context
# from quart import Quart , render_template, request, redirect, url_for, jsonify, flash
import time
import csv
import math
import os
import re
import threading
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta
from fpdf import FPDF
from fpdf.enums import XPos, YPos

## Bluetooth ##
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import asyncio
import serial
from serial.tools import list_ports


class PlayerStats(TypedDict):
    """Statistics for a single player."""
    assists: int
    goals: int
    majors: int
    reds: int


class PeriodScores(TypedDict):
    """Period-by-period scoring."""
    goals1: int
    majors1: int
    goals2: int
    majors2: int
    goals3: int
    majors3: int
    goals4: int
    majors4: int


def newPlayerStats() -> PlayerStats:
    return {"assists": 0, "goals": 0, "majors": 0, "reds": 0}


def newPeriodScores() -> PeriodScores:
    return {
        "goals1": 0,
        "majors1": 0,
        "goals2": 0,
        "majors2": 0,
        "goals3": 0,
        "majors3": 0,
        "goals4": 0,
        "majors4": 0,
    }


# Initialize teams
teama: dict[int, PlayerStats] = {i: newPlayerStats() for i in range(1, 15)}
teamb: dict[int, PlayerStats] = {i: newPlayerStats() for i in range(1, 15)}

periodscores: dict[str, PeriodScores] = {"Home": newPeriodScores(), "Away": newPeriodScores()}

# Track when timer.html is loaded to notify display.html
timer_reload_timestamp = time.time()
webview_window = None
force_reload_token = time.time()
runtime_listening_port = 5000
external_call_token = 0
last_external_call = {"path": "", "method": "", "remote_addr": "", "timestamp": 0}

# When these routes are serving a "next screen" (goal/major/penalty),
# we must avoid bumping `force_reload_token` because timer.html's polling
# will reload the timer page and interrupt navigation.
SKIP_FORCE_RELOAD_PATHS = {
    "/goal",
    "/goalint",
    "/major",
    "/penalty",
    # Shot-clock +/- nudges update state via AJAX + updateCountdown(); a full
    # page reload here fights the user's click and makes the tweak look like
    # it didn't happen.
    "/shot_clock_plus",
    "/shot_clock_minus",
}

AUTO_REFRESH_EXCLUDED_PATHS = {
    "/",
    "/display",
    "/favicon.ico",
    "/goal",
    "/major",
    "/penalty",
    "/card",
    "/awaytimeout",
    "/hometimeout",
    "/timeout",
    "/interval",
    "/callinterval",
    "/returninterval",
    "/trigger_refresh",
    "/refresh_webview",
}
AUTO_REFRESH_EXCLUDED_PREFIXES = (
    "/static/",
    "/get_",
    "/displayshotclock/",
)

# Group related constants at the top
class Config:
    """Application configuration constants."""
    WEB_TIMEOUT: int = 180
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 5000
    SESSION_TYPE: str = "filesystem"
    SECRET_KEY: str = "waterpolo"

    # Game settings
    # All time is based on 30 second increments
    INTERVAL_TIME: int = 4
    HALFTIME: int = 4
    TIMEOUT_TIME: int = 2
    GAME_TIME: int = 13
    SHOT_CLOCK: int = 28
    FOUL_CLOCK: int = SHOT_CLOCK - 10
    BLUETOOTH_CONNECT: int = 0
    MAJORS: int = 3

    # Bluetooth constants
    UART_SERVICE_UUID: str = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
    RX_CHAR_UUID: str = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
    TX_CHAR_UUID: str = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
    BLUETOOTH_NAME: list[str] = ["Nano33BLE", "WaterPolo_1", "WaterPolo_2"]

    # Serial relay (e.g. LoRa master on USB). Empty string disables serial output.
    SERIAL_PORT: str = ""
    SERIAL_BAUD: int = 9600

    # Default values
    DEFAULT_LOCATION: str = "New Malden"
    DEFAULT_HOME_TEAM: str = "Kingston Royals"
    DEFAULT_AWAY_TEAM: str = "Away Team"


RESULTS_DIR = Path("results")
TEMP_DIR = RESULTS_DIR / "temp"


def ensureResultsDirs() -> None:
    """Create output directories for temp CSV logs and final PDF exports."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def buildGameCsvBasename() -> str:
    return datetime.now().strftime(
        Config.DEFAULT_HOME_TEAM + ' vs ' + Config.DEFAULT_AWAY_TEAM + '-%Y-%m-%d-%H-%M.csv'
    )


def buildCompressCsvBasename() -> str:
    return datetime.now().strftime(
        Config.DEFAULT_HOME_TEAM + ' vs ' + Config.DEFAULT_AWAY_TEAM + '_END_' + '-%Y-%m-%d-%H-%M.csv'
    )


def buildTempCsvPath() -> Path:
    return TEMP_DIR / datetime.now().strftime('temp' + '-%Y-%m-%d-%H-%M.csv')


def buildGameCsvPath() -> Path:
    return TEMP_DIR / buildGameCsvBasename()


def buildFinalPdfPath() -> Path:
    return RESULTS_DIR / f"{Path(buildCompressCsvBasename()).stem}.pdf"


def _preferred_listening_ipv4_address() -> Optional[str]:
    """Best-effort LAN IPv4 detection (never returns 127.0.0.1 or 0.0.0.0)."""

    def _is_acceptable(ip: str) -> bool:
        ip = (ip or "").strip()
        return ip not in ("0.0.0.0", "127.0.0.1") and not ip.startswith("127.")

    # UDP "connect" trick doesn't send packets, but selects the right outbound interface.
    for dest in (("8.8.8.8", 80), ("1.1.1.1", 80)):
        sock: Optional[socket.socket] = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(dest)
            ip = sock.getsockname()[0]
            if _is_acceptable(ip):
                return ip
        except OSError:
            continue
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    hostname = socket.gethostname()
    try:
        for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            ip = str(info[4][0])
            if _is_acceptable(ip):
                return ip
    except OSError:
        pass

    try:
        _, _, ips = socket.gethostbyname_ex(hostname)
        for ip in ips:
            if _is_acceptable(ip):
                return ip
    except OSError:
        pass

    return None


def load_scoreboard_config():
    """Load runtime config values used during app startup."""
    return {
        "listening_port": os.environ.get("SCOREBOARD_LISTENING_PORT", Config.WEB_PORT),
    }


def refresh_webview_window():
    """Best-effort native refresh for the pywebview window."""
    if webview_window is None:
        return False, "No active webview window"

    try:
        # Fast path: reload current page in-place.
        webview_window.evaluate_js("window.location.reload(true);")
        return True, "reload via evaluate_js"
    except Exception as js_error:
        try:
            # Fallback: navigate to index with a cache-busting query param.
            refresh_url = f"http://127.0.0.1:{runtime_listening_port}/?refresh={int(time.time() * 1000)}"
            webview_window.load_url(refresh_url)
            return True, "reload via load_url fallback"
        except Exception as load_error:
            return False, f"{js_error}; {load_error}"


def _should_auto_refresh(req):
    """Refresh for state-changing requests, excluding polling/noisy paths."""
    if req.method not in ("GET", "POST"):
        return False
    if req.path in AUTO_REFRESH_EXCLUDED_PATHS:
        return False
    return not any(req.path.startswith(prefix) for prefix in AUTO_REFRESH_EXCLUDED_PREFIXES)


def _is_external_browser_call(req):
    remote_addr = (req.remote_addr or "").strip()
    if not remote_addr:
        return False
    return not (remote_addr == "127.0.0.1" or remote_addr == "::1" or remote_addr.startswith("127."))


def broadcast_refresh_event():
    """Update shared refresh state (token)."""
    global timer_reload_timestamp, force_reload_token
    now = time.time()
    timer_reload_timestamp = now
    if has_request_context and request.path in SKIP_FORCE_RELOAD_PATHS:
        return
    force_reload_token = now
    # IMPORTANT:
    # Do not call `refresh_webview_window()` here.
    # Many "goal/major/penalty" routes call pause/reset functions internally, and
    # forcing a native WebView reload mid-navigation can interrupt the page change.
    # timer.html / display.html reload themselves when `force_reload_token` changes.

app = Flask(__name__, static_url_path='/static')
# app = Quart(__name__, static_url_path='/static')
app.config['SESSION_TYPE'] = Config.SESSION_TYPE
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=Config.WEB_TIMEOUT)
# app.config['SERVER_NAME'] = "0.0.0.0:5000"

# Session(app)

# Initial scores for two teams

scores = {
    'Home': {'goals': 0, 'majors': 0},
    'Away': {'goals': 0, 'majors': 0}
}

TeamHome = scores['Home']
TeamAway = scores['Away']

# PLAYERS NAMES
home_data = {'home': [['1', ''], ['2', ''], ['3', ''], ['4', ''], ['5', ''], ['6', ''], ['7', ''], ['8', ''], ['9', ''], ['10', ''], ['11', ''], ['12', ''], ['13', ''], ['14', '']]}
away_data = {'away': [['1', ''], ['2', ''], ['3', ''], ['4', ''], ['5', ''], ['6', ''], ['7', ''], ['8', ''], ['9', ''], ['10', ''], ['11', ''], ['12', ''], ['13', ''], ['14', '']]}
home_staff = {'home': [['HC', ''], ['AC', ''], ['TM', '']]}
away_staff = {'away': [['HC', ''], ['AC', ''], ['TM', '']]}

# home_data = {'home': [['1', 'player1'], ['2', 'player2'], ['3', 'player1'], ['4', 'player4'], ['5', 'player5'], ['6', 'player6'], ['7', 'player7'], ['8', 'player8'], ['9', 'player9'], ['10', 'player10'], ['11', 'player11'], ['12', 'player12'], ['13', 'player13'], ['14', 'player14']]}
# away_data = {'away': [['1', 'player1'], ['2', 'player2'], ['3', 'player3'], ['4', 'player4'], ['5', 'player5'], ['6', 'player6'], ['7', 'player7'], ['8', 'player8'], ['9', 'player9'], ['10', 'player10'], ['11', 'player11'], ['12', 'player12'], ['13', 'player13'], ['14', 'player14']]}



# REFEREE NAME AND EXPENCES
ref_data = {'referee': [['1', '','',''], ['2', '','','']]}
# ref_data = {'referee': [['1', 'Toby','kingston royals',''], ['2', 'Steve','surrey sharks','10']]}

# CARDS

home_coach = {'HC': 0, 'yellow': 0, 'AC': 0, 'TM': 0}
away_coach = {'HC': 0, 'yellow': 0, 'AC': 0, 'TM': 0}

home_team_red = {'red': 0, 'yellow': 0}
away_team_red = {'red': 0, 'yellow': 0}

runningclock = "no"


ensureResultsDirs()
filename = str(buildGameCsvPath())
filenamebak = filename + '.bak'
running_file = str(buildTempCsvPath())
compress_file = buildCompressCsvBasename()
countdown_running = False
quarter= 0
direction: str = "increment"
hometimeoutv = 0
awaytimeoutv = 0
start_time = 0
elapsed_time = 0
start_shot = 0
elapsed_shot = 0
clock_shot = Config.SHOT_CLOCK
remaining_shot = 0

timeoutrunning = False
starttimeout = 0
elapsedtimeout = 0

reason = 'Timeout'
timeout: int = Config.TIMEOUT_TIME
interval_active = False
BLUETOOTH_CONNECT = Config.BLUETOOTH_CONNECT


## Bluetooth code block ##
# Connection state. ble_clients / ble_client_names / ble_client_addresses are kept
# as parallel lists so a single index identifies one target device across all three.
ble_client = None  # kept for backward compatibility; not used directly
ble_clients: list = []
ble_client_names: list[str] = []
ble_client_addresses: list[str] = []

# Reliability / reconnect tuning
_BLE_SCAN_TIMEOUT = 3.0          # seconds per BleakScanner.discover
_BLE_SCAN_ATTEMPTS = 3           # how many scans to retry when nothing is found
_BLE_CONNECT_TIMEOUT = 5.0      # seconds per BleakClient.connect
_BLE_CONNECT_RETRIES = 3         # attempts per device during Connect
_BLE_RECONNECT_RETRIES = 2       # attempts per device during Reconnect

# _ble_op_lock serialises long-running BLE operations (Connect / Reconnect /
# Disconnect buttons) so two clicks cannot mutate ble_clients concurrently.
# Short read-only snapshots by send_* do not need it.
_ble_op_lock = threading.Lock()

# --- Persistent BLE event loop ----------------------------------------------
# bleak's WinRT backend posts device notifications (services changed,
# disconnect, etc.) back to the loop that created the BleakClient. If we use
# asyncio.run() per Flask request that loop is closed immediately, and a
# later notification from a powered-off device triggers
# "RuntimeError: Event loop is closed". We therefore run *all* BLE work on
# one long-lived loop in a dedicated thread, and dispatch coroutines onto it
# via asyncio.run_coroutine_threadsafe().
from concurrent.futures import TimeoutError as FuturesTimeoutError
_ble_loop: Optional[asyncio.AbstractEventLoop] = None
_ble_loop_thread: Optional[threading.Thread] = None
_ble_loop_start_lock = threading.Lock()


def _ensure_ble_loop() -> asyncio.AbstractEventLoop:
    """Start (once) and return the persistent BLE event loop."""
    global _ble_loop, _ble_loop_thread
    with _ble_loop_start_lock:
        if _ble_loop is not None and _ble_loop.is_running():
            return _ble_loop

        loop = asyncio.new_event_loop()

        def _runner():
            asyncio.set_event_loop(loop)
            try:
                loop.run_forever()
            finally:
                try:
                    loop.close()
                except Exception:
                    pass

        t = threading.Thread(target=_runner, name="ble-loop", daemon=True)
        t.start()
        _ble_loop = loop
        _ble_loop_thread = t
        print("[BLE] Persistent event loop started")
        return loop


def _run_ble(coro, timeout: Optional[float] = None):
    """Dispatch a coroutine to the persistent BLE loop and wait for it.

    This is the single funnel through which ALL BLE work is run so that
    BleakClient objects are always bound to a loop that never closes.
    Raises FuturesTimeoutError on timeout; callers should catch it.
    """
    loop = _ensure_ble_loop()
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return fut.result(timeout=timeout)
    except FuturesTimeoutError:
        fut.cancel()
        raise


def ble_send_command(command: str, timeout: float = 3.0) -> None:
    """Thread-safe fire-and-forget wrapper for send_ble_command.

    Swallows errors (including timeouts) so a flaky BLE device cannot turn
    a scoreboard action into a 500 response. Also mirrors the command to
    the configured serial port when connected.
    """
    try:
        _run_ble(send_ble_command(command), timeout=timeout)
    except FuturesTimeoutError:
        print(f"[BLE] send_ble_command('{command}') timed out after {timeout}s")
    except Exception as e:
        print(f"[BLE] send_ble_command('{command}') failed: {e}")
    serial_send_command(command)


def ble_send_int(value, timeout: float = 3.0) -> None:
    """Thread-safe fire-and-forget wrapper for send_ble_int."""
    try:
        _run_ble(send_ble_int(value), timeout=timeout)
    except FuturesTimeoutError:
        print(f"[BLE] send_ble_int({value}) timed out after {timeout}s")
    except Exception as e:
        print(f"[BLE] send_ble_int({value}) failed: {e}")
    serial_send_command(normalize_ble_int_payload(value))


def _on_ble_disconnect(client):
    """bleak disconnect callback. We intentionally do NOT auto-reconnect
    here; the user must press the Reconnect button to restore service."""
    try:
        addr = getattr(client, "address", "?")
        print(f"[BLE] Device disconnected (callback): {addr}")
    except Exception:
        pass


def _make_client(address: str):
    """Create a BleakClient, passing the disconnect callback when supported."""
    try:
        return BleakClient(address, disconnected_callback=_on_ble_disconnect)
    except TypeError:
        # Older bleak versions may not accept the kwarg in the constructor.
        return BleakClient(address)


async def _connect_one(name: str, address: str, retries: int = _BLE_CONNECT_RETRIES):
    """Connect to a single device by address with retries and backoff.

    Returns a connected BleakClient, or None if every attempt failed.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        client = _make_client(address)
        try:
            await client.connect(timeout=_BLE_CONNECT_TIMEOUT)
            if client.is_connected:
                print(f"[BLE] Connected to {name} at {address} (attempt {attempt}/{retries})")
                return client
            # Not connected but no exception -> treat as failure
            last_err = "connect() returned but is_connected is False"
        except Exception as e:
            last_err = e
            print(f"[BLE] Connect attempt {attempt}/{retries} to {name} ({address}) failed: {e}")
            try:
                await client.disconnect()
            except Exception:
                pass
        # Backoff before next try (skip after last attempt)
        if attempt < retries:
            await asyncio.sleep(min(1.0 * attempt, 3.0))
    print(f"[BLE] Giving up connecting to {name} ({address}) after {retries} attempts: {last_err}")
    return None


async def _scan_for_targets(attempts: int = _BLE_SCAN_ATTEMPTS):
    """Scan for BLE devices whose name matches Config.BLUETOOTH_NAME.

    Retries the scan a few times before giving up, because the first scan
    after Windows wakes up / the dongle resets often returns nothing.
    """
    for attempt in range(1, attempts + 1):
        try:
            devices = await BleakScanner.discover(timeout=_BLE_SCAN_TIMEOUT)
        except Exception as e:
            print(f"[BLE] Scan attempt {attempt}/{attempts} raised: {e}")
            devices = []

        found = [
            d for d in devices
            if d.name and any(n in d.name for n in Config.BLUETOOTH_NAME)
        ]
        # De-duplicate by address (some stacks report the same device twice)
        seen = set()
        unique = []
        for d in found:
            if d.address not in seen:
                seen.add(d.address)
                unique.append(d)
        if unique:
            return unique
        print(f"[BLE] Scan {attempt}/{attempts}: no matching targets; retrying...")
    return []


async def init_ble():
    """Discover and connect to every configured BLE device.

    This is idempotent: if a device is already connected it is re-used rather
    than forcibly reconnected, so calling /connectble repeatedly is safe.
    """
    global ble_clients, ble_client_names, ble_client_addresses

    targets = await _scan_for_targets()
    if not targets:
        print(f"[BLE] None of {Config.BLUETOOTH_NAME} found after {_BLE_SCAN_ATTEMPTS} scans.")
        # Keep any still-connected clients intact; just return.
        return ble_clients

    # Snapshot existing state so we can preserve healthy connections.
    existing_by_addr: dict = {}
    for c, n, a in zip(list(ble_clients), list(ble_client_names), list(ble_client_addresses)):
        existing_by_addr[a] = (c, n)

    new_clients: list = []
    new_names: list[str] = []
    new_addresses: list[str] = []

    for d in targets:
        addr = d.address
        nm = (d.name or "").strip()

        # Re-use a healthy existing connection to this same address.
        if addr in existing_by_addr:
            c, _ = existing_by_addr.pop(addr)
            try:
                if c and c.is_connected:
                    print(f"[BLE] Reusing existing connection to {nm} at {addr}")
                    new_clients.append(c)
                    new_names.append(nm)
                    new_addresses.append(addr)
                    continue
            except Exception:
                pass
            # Existing client is stale -> drop it cleanly before reconnecting.
            try:
                await c.disconnect()
            except Exception:
                pass

        client = await _connect_one(nm, addr)
        if client is not None:
            new_clients.append(client)
            new_names.append(nm)
            new_addresses.append(addr)

    # Clean up any previously-known clients that weren't seen in this scan.
    for addr, (c, nm) in existing_by_addr.items():
        try:
            if c and c.is_connected:
                await c.disconnect()
                print(f"[BLE] Disconnected stale device {nm} at {addr}")
        except Exception:
            pass

    ble_clients = new_clients
    ble_client_names = new_names
    ble_client_addresses = new_addresses

    return ble_clients


async def dis_ble():
    """Disconnect from every known BLE client and clear the state."""
    global ble_clients, ble_client_names, ble_client_addresses
    for client in list(ble_clients):
        try:
            if client and client.is_connected:
                await client.disconnect()
                print(f"[BLE] Disconnected safely from {getattr(client, 'address', '?')}")
            else:
                print(f"[BLE] Already disconnected from {getattr(client, 'address', '?')}, skipping.")
        except BleakError as e:
            print(f"[BLE] Error during disconnect from {getattr(client, 'address', '?')}: {e}")
        except Exception as e:
            print(f"[BLE] Unexpected error with {getattr(client, 'address', '?')}: {e}")

    ble_clients = []
    ble_client_names = []
    ble_client_addresses = []
    return ble_clients


async def reconnect_ble():
    """Reconnect any known BLE targets that currently report as disconnected.

    Strategy:
      1. Try a direct reconnect by the previously-known address.
      2. If that still fails, rescan: a device that was power-cycled may
         reappear at the same name but a (slightly) different address.
    """
    global ble_clients, ble_client_names, ble_client_addresses

    # Build the list of disconnected slots (index-based so we can update in place).
    slots = list(enumerate(zip(list(ble_clients), list(ble_client_names), list(ble_client_addresses))))
    disconnected = [
        (i, nm, addr) for i, (c, nm, addr) in slots
        if not (c and getattr(c, "is_connected", False))
    ]

    if not disconnected:
        return ble_clients

    print(f"[BLE] Reconnect: {len(disconnected)} target(s) disconnected: "
          f"{[(nm, addr) for _, nm, addr in disconnected]}")

    # Pass 1: reconnect by known address.
    still_missing = []
    for i, nm, addr in disconnected:
        # Drop any stale handle first
        old = ble_clients[i] if i < len(ble_clients) else None
        if old is not None:
            try:
                await old.disconnect()
            except Exception:
                pass

        new_c = await _connect_one(nm, addr, retries=_BLE_RECONNECT_RETRIES)
        if new_c is not None:
            if i < len(ble_clients):
                ble_clients[i] = new_c
                ble_client_addresses[i] = addr
        else:
            still_missing.append((i, nm, addr))

    # Pass 2: rescan if anything is still missing (the address may have changed).
    if still_missing:
        print(f"[BLE] Rescanning to find {len(still_missing)} missing target(s)...")
        found = await _scan_for_targets(attempts=1)
        by_name: dict[str, list] = {}
        for d in found:
            by_name.setdefault((d.name or "").strip(), []).append(d)

        for i, nm, addr in still_missing:
            candidates = by_name.get(nm, [])
            new_c = None
            for cand in candidates:
                if cand.address == addr:
                    continue  # already tried in pass 1
                new_c = await _connect_one(nm, cand.address, retries=_BLE_RECONNECT_RETRIES)
                if new_c is not None:
                    if i < len(ble_clients):
                        ble_clients[i] = new_c
                        ble_client_addresses[i] = cand.address
                    break
            if new_c is None:
                print(f"[BLE] Still cannot reconnect to {nm} (last known {addr}). "
                      f"Press Reconnect again after the device is powered back on.")

    return ble_clients


def ble_any_live_client() -> bool:
    """True when at least one BLE slot currently reports is_connected."""
    return any(c and getattr(c, "is_connected", False) for c in ble_clients)


def _run_ble_coro(coro, timeout: float = 120.0, *, reraise: bool = False):
    """Run a heavy BLE operation (Connect / Reconnect / Disconnect) on the
    persistent BLE loop, serialised by _ble_op_lock so two clicks cannot
    mutate ble_clients concurrently.

    By default errors are logged and suppressed so scoreboard routes keep
    returning HTTP 200. Pass reraise=True from manual connect/reconnect
    handlers so failures can be returned to the client.
    """
    with _ble_op_lock:
        if reraise:
            return _run_ble(coro, timeout=timeout)
        try:
            return _run_ble(coro, timeout=timeout)
        except FuturesTimeoutError:
            print(f"[BLE] Long BLE operation timed out after {timeout}s")
        except Exception as e:
            print(f"[BLE] Background BLE op failed: {e}")


# --- Watchdog intentionally disabled ----------------------------------------
# Auto-reconnect has been removed so BLE failures cannot delay the main game
# loop. The only way to re-establish a dropped link is the Reconnect button
# (/reconnectble). The no-op stubs below keep any stray call sites safe.
def start_ble_watchdog():
    """Disabled: automatic BLE reconnect has been turned off by design."""
    return


def stop_ble_watchdog():
    """Disabled: automatic BLE reconnect has been turned off by design."""
    return


def get_ble_waterpolo_connection_flags() -> dict[str, bool]:
    """True when a live BLE client matches WaterPolo_1 / WaterPolo_2 (name substring, case-insensitive)."""
    wp1 = False
    wp2 = False
    for name, client in zip(ble_client_names, ble_clients):
        if not client or not getattr(client, "is_connected", False):
            continue
        n = (name or "").lower()
        if "waterpolo_1" in n:
            wp1 = True
        if "waterpolo_2" in n:
            wp2 = True
    return {"waterpolo_1": wp1, "waterpolo_2": wp2}


# --- Serial relay (USB COM port) --------------------------------------------
_serial_lock = threading.Lock()
_serial_conn: Optional[serial.Serial] = None
_serial_drop_warned = False


def list_com_ports() -> list[dict[str, str]]:
    """Return available COM ports for the settings dropdown."""
    ports: list[dict[str, str]] = []
    for entry in list_ports.comports():
        device = (entry.device or "").strip()
        if not device:
            continue
        description = (entry.description or "").strip()
        ports.append({"device": device, "description": description})
    return ports


def serial_is_connected() -> bool:
    with _serial_lock:
        return _serial_conn is not None and _serial_conn.is_open


def _close_serial_locked() -> None:
    global _serial_conn
    if _serial_conn is None:
        return
    try:
        if _serial_conn.is_open:
            _serial_conn.close()
    except Exception as e:
        print(f"[SERIAL] close failed: {e}")
    finally:
        _serial_conn = None


def disconnect_serial() -> None:
    """Close the open serial port, if any."""
    with _serial_lock:
        _close_serial_locked()
    print("[SERIAL] Disconnected")


def connect_serial(port: Optional[str] = None, baud: Optional[int] = None) -> str:
    """Open the configured COM port. Returns an error message, or empty string on success."""
    global _serial_conn, _serial_drop_warned
    port_name = (port if port is not None else Config.SERIAL_PORT).strip()
    if not port_name:
        return "No COM port selected."
    baud_rate = baud if baud is not None else Config.SERIAL_BAUD

    with _serial_lock:
        _close_serial_locked()
        try:
            _serial_conn = serial.Serial(port_name, baud_rate, timeout=1)
        except Exception as e:
            _serial_conn = None
            return str(e)
    _serial_drop_warned = False
    print(f"[SERIAL] Connected on {port_name} @ {baud_rate}")
    serial_send_command("TEST")
    return ""


def try_autoconnect_serial() -> None:
    """Best-effort open of Config.SERIAL_PORT (logs errors, never raises)."""
    if not (Config.SERIAL_PORT or "").strip():
        return
    error = connect_serial()
    if error:
        print(f"[SERIAL] Auto-connect failed: {error}")


def serial_send_command(command: str) -> None:
    """Mirror a scoreboard text command to the serial port (newline-delimited)."""
    global _serial_drop_warned
    if not command:
        return
    with _serial_lock:
        if _serial_conn is None or not _serial_conn.is_open:
            if not _serial_drop_warned:
                print(
                    f"[SERIAL] Port not open; dropped '{command}'. "
                    "Save your COM port on Settings, click Serial Connect, and confirm the badge shows connected."
                )
                _serial_drop_warned = True
            return
        try:
            _serial_conn.write((command + "\n").encode("utf-8"))
            _serial_conn.flush()
            print(f"[SERIAL] TX: {command}")
        except Exception as e:
            print(f"[SERIAL] write '{command}' failed: {e}")
            _close_serial_locked()


def get_device_connection_flags() -> dict[str, Union[bool, str]]:
    """BLE WaterPolo slots plus serial relay link state for the settings UI."""
    flags: dict[str, Union[bool, str]] = dict(get_ble_waterpolo_connection_flags())
    flags["serial"] = serial_is_connected()
    flags["serial_port"] = Config.SERIAL_PORT or ""
    return flags


# Short upper bound on any individual BLE write from the game loop. If the
# Windows BLE stack is wedged we fail fast instead of holding up a Flask
# request. Users must press Reconnect to restore service.
_BLE_SEND_TIMEOUT = 1.5  # seconds


def _mark_slot_dead(index: int, reason: str) -> None:
    """Drop the client handle for `index` so status flags flip to False.

    We intentionally do NOT await client.disconnect() here -- that can itself
    hang the main request. Python will release the underlying handle when the
    BleakClient object is garbage-collected. The name/address stay in the
    parallel lists so Reconnect can restore this exact slot.
    """
    if 0 <= index < len(ble_clients):
        addr = getattr(ble_clients[index], "address", "?") if ble_clients[index] else "?"
        ble_clients[index] = None
        print(f"[BLE] Slot {index} ({addr}) marked disconnected: {reason}. "
              f"Press Reconnect to restore.")


async def send_ble_command(command: str):
    """Send a text command to every currently-connected BLE device.

    Failure policy (by design):
      * If the slot is already flagged as disconnected -> skip silently.
      * If the write raises / times out -> mark that slot dead and move on.
      * No inline reconnect is attempted. Use the Reconnect button.
    """
    payload = (command + "\0").encode("utf-8")
    for i in range(len(ble_clients)):
        client = ble_clients[i]
        if not (client and getattr(client, "is_connected", False)):
            continue
        try:
            await asyncio.wait_for(
                client.write_gatt_char(Config.RX_CHAR_UUID, payload),
                timeout=_BLE_SEND_TIMEOUT,
            )
        except asyncio.TimeoutError:
            _mark_slot_dead(i, f"write timeout on '{command}'")
        except Exception as e:
            _mark_slot_dead(i, f"write error on '{command}': {e}")


def normalize_ble_int_payload(value: str | int | float) -> str:
    """Coerce shot-clock values to a non-negative integer string for BLE (no float decimals)."""
    try:
        n = float(value)
    except (ValueError, TypeError):
        return str(value)
    return str(int(max(0.0, n)))


async def send_ble_int(value: str | int | float):
    """Send a numeric (shot-clock) value to every currently-connected BLE device.

    Same failure policy as send_ble_command: fail fast, mark the slot dead,
    never attempt an inline reconnect.
    """
    payload = (normalize_ble_int_payload(value) + "\0").encode("utf-8")
    for i in range(len(ble_clients)):
        client = ble_clients[i]
        if not (client and getattr(client, "is_connected", False)):
            continue
        try:
            await asyncio.wait_for(
                client.write_gatt_char(Config.RX_CHAR_UUID, payload),
                timeout=_BLE_SEND_TIMEOUT,
            )
        except asyncio.TimeoutError:
            _mark_slot_dead(i, f"write timeout on int '{value}'")
        except Exception as e:
            _mark_slot_dead(i, f"write error on int '{value}': {e}")

@app.route('/changeposs')
def changeposs():
    command = "CHANGE"
    ble_send_command(command)
    return jsonify({'status': 'success'})


@app.route('/periodend')
def periodend():
    command = "END"
    ble_send_command(command)
    return jsonify({'status': 'success'})


@app.route('/buzzer')
def buzzer():
    command = "BUZZER"
    ble_send_command(command)
    return jsonify({'status': 'success'})

# @app.route('/displayshotclock/<int:shot>')
# def displayshotclock(shot):
#     command = shot
#     # print(f"Sent command to int: {command}")
#     ble_send_int(command)
#     return jsonify({'status': 'success'})

@app.route('/displayshotclock/<int:shot>')
def displayshotclock(shot):
    command = shot
    try:
        ble_send_int(command)
        return jsonify({'status': 'success'})
    except Exception as e:
        # Log the error and return a controlled response
        print(f"Error in displayshotclock route: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
## end of Bluetooth code block



@app.route('/')
def index():
    global timer_reload_timestamp
    timer_reload_timestamp = time.time()  # Update timestamp when timer.html loads
    clock_display = getCountdownDisplayValues()
    return render_template('timer.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red,
                           initial_game_clock=clock_display['game_clock'],
                           initial_shot_clock=clock_display['shot_clock'])

@app.route('/display')
def display():
    clock_display = getCountdownDisplayValues()
    return render_template('display.html', scores=scores, teama=teama, teamb=teamb, 
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, 
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red,
                           initial_game_clock=clock_display['game_clock'],
                           initial_shot_clock=clock_display['shot_clock'])

@app.route('/controls')
def controls():
    """Controls-only page containing just the function buttons."""
    clock_display = getCountdownDisplayValues()
    return render_template(
        'controls.html',
        initial_game_clock=clock_display['game_clock'],
        initial_shot_clock=clock_display['shot_clock'],
    )

@app.route('/get_timer_reload_timestamp')
def get_timer_reload_timestamp():
    """Return the timestamp of when timer.html was last loaded."""
    return jsonify({'timestamp': timer_reload_timestamp})

@app.route('/get_force_reload_token')
def get_force_reload_token():
    """Shared token polled by pages to coordinate forced reloads."""
    return jsonify({'token': force_reload_token})


@app.route('/get_scoreboard_snapshot')
def get_scoreboard_snapshot():
    """JSON snapshot of scores and period breakdown for live display updates."""
    return jsonify(getScoreboardSnapshot())


@app.route('/ble_connection_status')
def ble_connection_status():
    """JSON for settings UI: WaterPolo BLE slots and serial relay link state."""
    return jsonify(get_device_connection_flags())

@app.route('/get_external_call_token')
def get_external_call_token():
    """Token and metadata updated when external browser calls are received."""
    return jsonify({
        'token': external_call_token,
        'path': last_external_call["path"],
        'method': last_external_call["method"],
        'remote_addr': last_external_call["remote_addr"],
        'timestamp': last_external_call["timestamp"],
    })

@app.route('/trigger_refresh', methods=['GET', 'POST'])
def trigger_refresh():
    """External hook: trigger all connected clients to reload."""
    global timer_reload_timestamp, force_reload_token
    now = time.time()
    timer_reload_timestamp = now
    force_reload_token = now
    refreshed, detail = refresh_webview_window()
    return jsonify({'status': 'success', 'token': force_reload_token, 'webview_refreshed': refreshed, 'detail': detail})

@app.route('/refresh_webview', methods=['GET', 'POST'])
def refresh_webview():
    """External hook to refresh the running WebView app."""
    global timer_reload_timestamp, force_reload_token
    now = time.time()
    timer_reload_timestamp = now
    force_reload_token = now

    refreshed, detail = refresh_webview_window()
    return jsonify({'status': 'success', 'webview_refreshed': refreshed, 'detail': detail})


@app.after_request
def auto_refresh_on_external_call(response):
    global timer_reload_timestamp, force_reload_token, external_call_token, last_external_call
    if _is_external_browser_call(request) and _should_auto_refresh(request):
        now = time.time()
        timer_reload_timestamp = now
        force_reload_token = now
        external_call_token = now
        last_external_call = {
            "path": request.path,
            "method": request.method,
            "remote_addr": request.remote_addr or "",
            "timestamp": now,
        }
        refresh_webview_window()
    return response


# CLOCK CONTROLS
@app.route('/start_countdown')
def start_countdown():
    global countdown_running, start_time, elapsed_time, start_shot, elapsed_shot
    countdown_running = True
    start_time = time.time() - elapsed_time
    start_shot = time.time() - elapsed_shot
    broadcast_refresh_event()
    return jsonify({'status': 'success'})


@app.route('/stop_countdown')
def stop_countdown():
    global countdown_running, start_time, elapsed_time, start_shot, elapsed_shot, clock_shot
    countdown_running = False
    clock_shot = Config.SHOT_CLOCK
    start_time = 0
    elapsed_time = 0
    start_shot = 0
    elapsed_shot = 0
    broadcast_refresh_event()
    return jsonify({'status': 'success'})


@app.route('/pause_countdown')
def pause_countdown():
    global countdown_running, start_time, elapsed_time, start_shot, elapsed_shot

    if countdown_running:
        countdown_running = False
        elapsed_time = time.time() - start_time
        elapsed_shot = time.time() - start_shot
    else:
        countdown_running = True
        start_time = time.time() - elapsed_time
        start_shot = time.time() - elapsed_shot
    broadcast_refresh_event()
    return jsonify({'status': 'success'})


@app.route('/resume_countdown')
def resume_countdown():
    global countdown_running, start_time , start_shot
    countdown_running = True
    start_time = time.time() - elapsed_time
    start_shot = time.time() - elapsed_shot
    return jsonify({'status': 'success'})

@app.route('/return_countdown')
def return_countdown():
    global countdown_running, start_time , start_shot
    countdown_running = True
    start_time = time.time() - elapsed_time
    start_shot = time.time() - elapsed_shot
    return jsonify({'status': 'success'})


@app.route('/get_countdown_status')
def get_countdown_status():
    values = getCountdownDisplayValues()
    return jsonify({
        'countdown_running': values['countdown_running'],
        'elapsed_time': values['remaining_time'],
        'elapsed_shot': values['remaining_shot'],
    })


def getCountdownDisplayValues() -> dict:
    """Remaining game/shot clock values for API responses and template rendering."""
    global countdown_running, start_time, elapsed_time, start_shot, elapsed_shot, clock_shot

    if countdown_running:
        remaining_time = max((Config.GAME_TIME * 30) - (time.time() - start_time), 0)
        remaining_shot = max(clock_shot - (time.time() - start_shot), 0)
    else:
        remaining_time = max((Config.GAME_TIME * 30) - elapsed_time, 0)
        remaining_shot = max(clock_shot - elapsed_shot, 0)

    game_minutes = int(remaining_time // 60)
    game_seconds = int(remaining_time % 60)
    shot_seconds = int(remaining_shot % 60)
    return {
        'countdown_running': countdown_running,
        'remaining_time': remaining_time,
        'remaining_shot': remaining_shot,
        'game_clock': f'{game_minutes}:{game_seconds:02d}',
        'shot_clock': f'{shot_seconds:02d}',
    }


def syncRemainingShot() -> float:
    """Synchronize the cached global shot clock value with elapsed state."""
    global remaining_shot

    remaining_shot = max(clock_shot - elapsed_shot, 0)
    return remaining_shot


def getScoreboardSnapshot() -> dict:
    """Live scoreboard state for display pages that refresh without a full reload."""
    period_data = {}
    for team_id, team_scores in periodscores.items():
        period_data[team_id] = dict(team_scores)

    clock_display = getCountdownDisplayValues()
    return {
        'home_goals': scores['Home']['goals'],
        'away_goals': scores['Away']['goals'],
        'home_majors': scores['Home']['majors'],
        'away_majors': scores['Away']['majors'],
        'hometimeoutv': hometimeoutv,
        'awaytimeoutv': awaytimeoutv,
        'quarter': quarter,
        'home_team': Config.DEFAULT_HOME_TEAM,
        'away_team': Config.DEFAULT_AWAY_TEAM,
        'location': Config.DEFAULT_LOCATION,
        'home_team_red': home_team_red.get('red', 0),
        'home_team_yellow': home_team_red.get('yellow', 0),
        'away_team_red': away_team_red.get('red', 0),
        'away_team_yellow': away_team_red.get('yellow', 0),
        'periodscores': period_data,
        'game_clock': clock_display['game_clock'],
        'shot_clock': clock_display['shot_clock'],
    }


def _shot_clock_apply_delta(delta):
    """Set shot remaining to current_remaining + delta (clamped). Fixes 00-display where elapsed > clock."""
    global countdown_running, start_time, elapsed_time, start_shot, elapsed_shot, remaining_shot, clock_shot

    if delta not in (-1, 1):
        return jsonify({'status': 'error', 'message': 'delta must be -1 or 1'}), 400

    max_shot_remaining = 60

    if countdown_running:
        elapsed_time = time.time() - start_time
        elapsed_shot = time.time() - start_shot
        remaining_shot = max(clock_shot - elapsed_shot, 0)
    else:
        remaining_shot = max(clock_shot - elapsed_shot, 0)

    new_remaining = max(0, min(max_shot_remaining, remaining_shot + delta))
    if new_remaining == remaining_shot:
        return jsonify({'status': 'success'})

    now = time.time()
    if countdown_running:
        # remaining = clock_shot - (now - start_shot)  =>  start_shot = now - (clock_shot - new_remaining)
        start_shot = now - (clock_shot - new_remaining)
        elapsed_shot = now - start_shot
        remaining_shot = max(clock_shot - elapsed_shot, 0)
    else:
        # remaining = clock_shot - elapsed_shot  =>  clock_shot = elapsed_shot + new_remaining
        clock_shot = elapsed_shot + new_remaining
        remaining_shot = max(clock_shot - elapsed_shot, 0)

    command = str(remaining_shot)
    ble_send_int(command)
    broadcast_refresh_event()
    return jsonify({'status': 'success'})


@app.route('/shot_clock_plus')
def shot_clock_plus():
    """Shot clock +1s (no negative path segment; reliable in all browsers)."""
    return _shot_clock_apply_delta(1)


@app.route('/shot_clock_minus')
def shot_clock_minus():
    """Shot clock -1s."""
    return _shot_clock_apply_delta(-1)


@app.route('/reset30')
def reset30():
    global countdown_running, start_time, elapsed_time, remaining_time , start_shot, elapsed_shot , remaining_shot, clock_shot
    if countdown_running:
        pause_countdown()
    clock_shot = max((Config.SHOT_CLOCK),0)
    remaining_shot = max((clock_shot) , 0)
    elapsed_shot = 0
    start_shot = 0
    # start_countdown()
    command = str(remaining_shot)
    # print(f"Sent command to int: {command}")
    ble_send_int(command)

    return jsonify({'status': 'success'})


@app.route('/possession')
def possession():
    global countdown_running, start_time, elapsed_time, remaining_time , start_shot, elapsed_shot , remaining_shot, clock_shot
    pause_countdown()
    clock_shot = max((Config.SHOT_CLOCK),0)+1
    remaining_shot = max((clock_shot) , 0)
    elapsed_shot = 0
    start_shot = 0
    start_countdown()
    command = str(remaining_shot -1)
    # print(f"Sent command to int: {command}")
    ble_send_int(command)

    return jsonify({'status': 'success'})


@app.route('/reset20')
def reset20():
    global countdown_running, start_time, elapsed_time, remaining_time , start_shot, elapsed_shot , remaining_shot, clock_shot
    if countdown_running:
        pause_countdown()
        if syncRemainingShot() < Config.FOUL_CLOCK:
            clock_shot = max((Config.FOUL_CLOCK),0)+1
            remaining_shot = max((clock_shot) , 0)
            elapsed_shot = 0
            start_shot = 0
        start_countdown()
    else:
        if syncRemainingShot() < Config.FOUL_CLOCK:
            clock_shot = max((Config.FOUL_CLOCK),0)+1
            remaining_shot = max((clock_shot) , 0)
            elapsed_shot = 0
            start_shot = 0
        start_countdown()
    command = str(remaining_shot-1)
    # print(f"Sent command to int: {command}")
    ble_send_int(command)
    return jsonify({'status': 'success'})

@app.route('/pause20')
def pause20():
    global countdown_running, start_time, elapsed_time, remaining_time , start_shot, elapsed_shot , remaining_shot, clock_shot
    if countdown_running:
        pause_countdown()
        if syncRemainingShot() < Config.FOUL_CLOCK:
            clock_shot = max((Config.FOUL_CLOCK),0)
            remaining_shot = max((clock_shot) , 0)
            elapsed_shot = 0
            start_shot = 0
    else:
        if syncRemainingShot() < Config.FOUL_CLOCK:
            clock_shot = max((Config.FOUL_CLOCK),0)
            remaining_shot = max((clock_shot) , 0)
            elapsed_shot = 0
            start_shot = 0
    command = str(remaining_shot)
    # print(f"Sent command to int: {command}")
    ble_send_int(command)
    return jsonify({'status': 'success'})
    # return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time, 'elapsed_shot': remaining_shot })



@app.route('/force20')
def force20():
    global countdown_running, start_time, elapsed_time, remaining_time , start_shot, elapsed_shot , remaining_shot, clock_shot
    if countdown_running:
        pause_countdown()
    clock_shot = max((Config.FOUL_CLOCK),0)
    remaining_shot = max((clock_shot) , 0)
    elapsed_shot = 0
    start_shot = 0
    command = str(remaining_shot)
    # print(f"Sent command to int: {command}")
    ble_send_int(command)
    return jsonify({'status': 'success'})

@app.route('/pause30')
def pause30():
    global countdown_running, start_time, elapsed_time, remaining_time , start_shot, elapsed_shot , remaining_shot, clock_shot
    if countdown_running:
        pause_countdown()
    clock_shot = max((Config.SHOT_CLOCK),0)
    remaining_shot = max((clock_shot) , 0)
    elapsed_shot = 0
    start_shot = 0
    command = str(remaining_shot)
    # print(f"Sent command to int: {command}")
    ble_send_int(command)
    return jsonify({'status': 'success'})

@app.route('/start_timeout')
def start_timeout():
    global timeoutrunning, starttimeout, elapsedtimeout
    timeoutrunning = True
    elapsedtimeout = 0
    starttimeout = time.time() - elapsedtimeout
    return jsonify({'status': 'success'})

@app.route('/stop_timeout')
def stop_timeout():
    global timeoutrunning, starttimeout, elapsedtimeout
    timeoutrunning = False
    starttimeout = 0
    elapsedtimeout = 0
    return jsonify({'status': 'success'})

@app.route('/pause_timeout')
def pause_timeout():
    global timeoutrunning, starttimeout, elapsedtimeout
    timeoutrunning = False
    elapsedtimeout = time.time() - starttimeout
    return jsonify({'status': 'success'})

@app.route('/resume_timeout')
def resume_timeout():
    global timeoutrunning, starttimeout
    timeoutrunning = True
    starttimeout = time.time() - elapsedtimeout
    return jsonify({'status': 'success'})

@app.route('/get_timeout_status')
def get_timeout_status():
    global timeoutrunning, starttimeout, elapsedtimeout
    if timeoutrunning:
        elapsedtimeout = time.time() - starttimeout
        remainingtimeout = max((timeout*30) - elapsedtimeout, 0)
        return jsonify({'timeout_running': timeoutrunning, 'elapsed_timeout': remainingtimeout})
    else:
        return jsonify({'timeout_running': timeoutrunning, 'elapsed_timeout': elapsedtimeout})


# END CLOCK CONTROLS

@app.route('/addmin')
def addmin():
    global countdown_running, start_time, elapsed_time
    if countdown_running:
        elapsed_time = time.time() - start_time
        remaining_time = max((Config.GAME_TIME*30) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})
    else:
        elapsed_time = elapsed_time - 60
        remaining_time = max((Config.GAME_TIME*30) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})

@app.route('/minmin')
def minmin():
    global countdown_running, start_time, elapsed_time
    if countdown_running:
        elapsed_time = time.time() - start_time
        remaining_time = max((Config.GAME_TIME*30) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})
    else:
        elapsed_time = elapsed_time + 60
        remaining_time = max((Config.GAME_TIME*30) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})

@app.route('/addsec')
def addsec():
    global countdown_running, start_time, elapsed_time
    if countdown_running:
        elapsed_time = time.time() - start_time
        remaining_time = max((Config.GAME_TIME*30) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})
    else:
        # return jsonify({'countdown_running': countdown_running, 'elapsed_time': elapsed_time})
        # elapsed_time = time.time() - start_time
        elapsed_time = elapsed_time - 1
        remaining_time = max((Config.GAME_TIME*30) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})

@app.route('/minsec')
def minsec():
    global countdown_running, start_time, elapsed_time
    if countdown_running:
        elapsed_time = time.time() - start_time
        remaining_time = max((Config.GAME_TIME*30) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})
    else:
        elapsed_time = elapsed_time + 1
        remaining_time = max((Config.GAME_TIME*30) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})



###### MAIN APP

@app.route('/card')
def card():
    if quarter == 0 :
        return redirect(url_for('index'))
    if countdown_running:
        if runningclock == "no":
            pause_countdown()

    return render_template('card.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)

@app.route('/homecard')
def homecard():
    if quarter == 0 :
        return redirect(url_for('index'))
    if countdown_running:
        if runningclock == "no":
            pause_countdown()

    return render_template('homecard.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)


@app.route('/awaycard')
def awaycard():
    if quarter == 0 :
        return redirect(url_for('index'))
    if countdown_running:
        if runningclock == "no":
            pause_countdown()


    return render_template('awaycard.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)



@app.route('/goal')
def goal():
    if quarter == 0 :
        return redirect(url_for('index'))
    if countdown_running:
        if runningclock == "no":
            reset30()
        else:
            reset30()
            resume_countdown()
    else:
        reset30()
    return render_template('goal.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)


@app.route('/goalint')
def goalint():
    if countdown_running:
        if runningclock == "no":
            reset30()
        else:
            reset30()
            return_countdown()
    else:
        reset30()
    return render_template('goalint.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)





@app.route('/major')
def major():
    if quarter == 0 :
        return redirect(url_for('index'))
    if countdown_running:
        if runningclock == "no":
            pause20()
        else:
            reset20()
            resume_countdown()
    else:
        pause20()

    return render_template('major.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)


@app.route('/penalty')
def penalty():
    if quarter == 0 :
        return redirect(url_for('index'))
    if countdown_running:
        if runningclock == "no":
            pause20()
        else:
            reset20()
            resume_countdown()
    else:
        pause20()

    return render_template('penalty.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)





@app.route('/updateteamacoach/<direction>/<int:id>', methods=['GET', 'POST'])
def updateteamacoach(direction,id):

    global quarter
    global countdown_running, start_time, elapsed_time, home_coach, away_coach
    if quarter == 0 :
        return redirect(url_for('index'))
    if request.method == 'POST':
        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))
        # print('help1')
        # action = request.form['action']
        direction = str(direction)
        # action = "increment"

        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')
        f = open(running_file, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'Min','Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]


        if direction == 'increment':
            # print('help2')
            if id == 1 :
                home_coach['yellow'] = 1
                home_team_red['yellow'] = home_team_red['yellow'] + 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'YELLOW',  'Home', '', 'Team Yellow' ,'','','']
                writer.writerow(data)
            elif id == 2 :
                home_coach['HC'] = 1
                home_team_red['red'] = home_team_red['red'] + 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED',  'Home', '', 'Head Coach' ,'','','']
                writer.writerow(data)
            elif id == 3 :
                home_coach['AC'] = 1
                home_team_red['red'] = home_team_red['red'] + 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED',  'Home', '', 'Assist Coach' ,'','','']
                writer.writerow(data)
            elif id == 4 :
                home_coach['TM'] = 1
                home_team_red['red'] = home_team_red['red'] + 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED',  'Home', '', 'Team, Manager' ,'','','']
                writer.writerow(data)   

        elif direction == 'decrement':
            if id == 1 :
                home_coach['yellow'] = 0
                home_team_red['yellow'] = home_team_red['yellow'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL Yellow',  'Home', '', 'Team Yellow' ,'','','']
                writer.writerow(data)
            elif id == 2 :
                home_coach['HC'] = 0
                home_team_red['red'] = home_team_red['red'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED',  'Home', '', 'Head Coach','','','']
                writer.writerow(data)
            elif id == 3 :
                home_coach['AC'] = 0
                home_team_red['red'] = home_team_red['red'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED',  'Home', '', 'Assist Coach','','','']
                writer.writerow(data)
            elif id == 4 :
                home_coach['TM'] = 0
                home_team_red['red'] = home_team_red['red'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED',  'Home', '', 'Team Manager','','','']
                writer.writerow(data)
            direction = "increment"

        f.close()

    return redirect(url_for('index'))


@app.route('/updateteambcoach/<direction>/<int:id>', methods=['GET', 'POST'])
def updateteambcoach(direction,id):
    global quarter
    global countdown_running, start_time, elapsed_time, home_coach, away_coach
    if quarter == 0 :
        return redirect(url_for('index'))
    if request.method == 'POST':


        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))
        # print('help1')
        # action = request.form['action']
        direction = str(direction)
        # action = "increment"

        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')
        f = open(running_file, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'Min','Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]

        if direction == 'increment':
            # print('help2')
            if id == 1 :
                away_coach['yellow'] = 1
                away_team_red['yellow'] = away_team_red['yellow'] + 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'YELLOW',  'Away', '', 'Team Yellow' ,'','','']
                writer.writerow(data)
            elif id == 2 :
                away_coach['HC'] = 1
                away_team_red['red'] = away_team_red['red'] + 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED',  'Away', '', 'Head Coach' ,'','','']
                writer.writerow(data)
            elif id == 3 :
                away_coach['AC'] = 1
                away_team_red['red'] = away_team_red['red'] + 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED',  'Away', '', 'Assist Coach' ,'','','']
                writer.writerow(data)
            elif id == 4 :
                away_coach['TM'] = 1
                away_team_red['red'] = away_team_red['red'] + 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED',  'Away', '', 'Team, Manager' ,'','','']
                writer.writerow(data)

        elif direction == 'decrement':
            if id == 1 :
                away_coach['yellow'] = 0
                away_team_red['yellow'] = away_team_red['yellow'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL Yellow',  'Away', '', 'Team Yellow' ,'','','']
                writer.writerow(data)
            elif id == 2 :
                away_coach['HC'] = 0
                away_team_red['red'] = away_team_red['red'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED',  'Away', '', 'Head Coach','','','']
                writer.writerow(data)
            elif id == 3 :
                away_coach['AC'] = 0
                away_team_red['red'] = away_team_red['red'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED',  'Away', '', 'Assist Coach','','','']
                writer.writerow(data)
            elif id == 4 :
                away_coach['TM'] = 0
                away_team_red['red'] = away_team_red['red'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED',  'Away', '', 'Team Manager','','','']
                writer.writerow(data)
            direction = "increment"

        f.close()

    return redirect(url_for('index'))



@app.route('/updateteamacard/<direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteamacard(direction,user_id):
    global quarter
    global countdown_running, start_time, elapsed_time
    if quarter == 0 :
        return redirect(url_for('index'))
    if request.method == 'POST':



        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))
        # print('help1')
        # action = request.form['action']
        direction = str(direction)
        # action = "increment"
        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')
        f = open(running_file, 'a')
        writer = csv.writer(f)
        # print(teama)
        if direction == 'increment':
            # print('help2')
            teama[user_id]['reds'] = 1
            home_team_red['red'] = home_team_red['red'] + 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED', 'Home', user_id, home_data['home'][user_id - 1][1], teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            teama[user_id]['reds'] = 0
            home_team_red['red'] = home_team_red['red'] - 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED', 'Home', user_id, home_data['home'][user_id - 1][1], teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
            writer.writerow(data)

            direction = "increment"
        f.close()

    return redirect(url_for('index'))

@app.route('/updateteamabrut/<direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteamabrut(direction,user_id):
    global quarter
    global countdown_running, start_time, elapsed_time
    if quarter == 0 :
        return redirect(url_for('index'))
    if request.method == 'POST':



        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))
        # print('help1')
        # action = request.form['action']
        direction = str(direction)
        # action = "increment"
        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')
        f = open(running_file, 'a')
        writer = csv.writer(f)
        # print(teama)
        if direction == 'increment':
            # print('help2')
            teama[user_id]['reds'] = 1
            home_team_red['red'] = home_team_red['red'] + 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED BRUT', 'Home', user_id, home_data['home'][user_id - 1][1], teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            teama[user_id]['reds'] = 0
            home_team_red['red'] = home_team_red['red'] - 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED', 'Home', user_id, home_data['home'][user_id - 1][1], teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
            writer.writerow(data)
            direction = "increment"
        f.close()

    return redirect(url_for('index'))

@app.route('/updateteambcard/<direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteambcard(direction, user_id):
    global quarter
    global countdown_running, start_time, elapsed_time
    if quarter == 0 :
        return redirect(url_for('index'))
    if request.method == 'POST':



        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))
        # print('help1')
        # action = request.form['action']
        direction = str(direction)
        # action = "increment"
        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')
        f = open(running_file, 'a')
        writer = csv.writer(f)
        # print(teamb)
        if direction == 'increment':
            # print('help2')
            teamb[user_id]['reds'] = 1
            away_team_red['red'] = away_team_red['red'] + 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED', 'Away', user_id, away_data['away'][user_id - 1][1], teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            teamb[user_id]['reds'] = 0
            away_team_red['red'] = away_team_red['red'] - 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED', 'Away', user_id, away_data['away'][user_id - 1][1], teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)

            direction = "increment"
        f.close()


    return redirect(url_for('index'))

@app.route('/updateteambbrut/<direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteambbrut(direction, user_id):
    global quarter
    global countdown_running, start_time, elapsed_time
    if quarter == 0 :
        return redirect(url_for('index'))
    if request.method == 'POST':



        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))
        # print('help1')
        # action = request.form['action']
        direction = str(direction)
        # action = "increment"
        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')
        f = open(running_file, 'a')
        writer = csv.writer(f)
        # print(teamb)
        if direction == 'increment':
            # print('help2')
            teamb[user_id]['reds'] = 1
            away_team_red['red'] = away_team_red['red'] + 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED BRUT', 'Away', user_id, away_data['away'][user_id - 1][1], teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            teamb[user_id]['reds'] = 0
            away_team_red['red'] = away_team_red['red'] - 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED', 'Away', user_id, away_data['away'][user_id - 1][1], teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)

            direction = "increment"
        f.close()


    return redirect(url_for('index'))

@app.route('/updateteamagoal/<int:user_id>', methods=['GET', 'POST'])
def updateteamagoal(user_id):
    """
    Update goal count for a home team player.
    
    Args:
        user_id: Integer player number (1-14)
        
    Returns:
        Redirect to index page
    """
    global quarter, direction
    global countdown_running, start_time, elapsed_time
    if request.method == 'POST':



        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))
        direction = str(direction)
        if direction == 'increment':
            teama[user_id]['goals'] = teama[user_id]['goals'] + 1
            scores['Home']['goals'] = scores['Home']['goals'] + 1
            if quarter == 1:
                periodscores['Home']['goals1'] = periodscores['Home']['goals1'] + 1
            elif quarter == 2:
                periodscores['Home']['goals2'] = periodscores['Home']['goals2'] + 1
            elif quarter == 3:
                periodscores['Home']['goals3'] = periodscores['Home']['goals3'] + 1
            elif quarter == 4:
                periodscores['Home']['goals4'] = periodscores['Home']['goals4'] + 1
        elif direction == 'decrement':
            teama[user_id]['goals'] = teama[user_id]['goals'] - 1
            scores['Home']['goals'] = scores['Home']['goals'] - 1
            if quarter == 1:
                periodscores['Home']['goals1'] = periodscores['Home']['goals1'] - 1
            elif quarter == 2:
                periodscores['Home']['goals2'] = periodscores['Home']['goals2'] - 1
            elif quarter == 3:
                periodscores['Home']['goals3'] = periodscores['Home']['goals3'] - 1
            elif quarter == 4:
                periodscores['Home']['goals4'] = periodscores['Home']['goals4'] - 1
            direction = "increment"
        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')
        f = open(running_file, 'a')
        writer = csv.writer(f)
        if direction == 'increment':
            data = [ quarter , x[1],x[2], scores['Home']['goals'] , scores['Away']['goals'] , 'Goal' ,  'Home',  user_id , home_data['home'][user_id - 1][1], teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds'] ]
            writer.writerow(data)
        elif direction == 'decrement':
            data = [ quarter , x[1],x[2], scores['Home']['goals'] , scores['Away']['goals'] , 'Remove Goal' ,  'Home',  user_id , home_data['home'][user_id - 1][1], teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds'] ]
            writer.writerow(data)
        f.close()


    return redirect(url_for('index'))

@app.route('/updateteamagoal/<string:direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteamagoal_direction(direction,user_id):
    """
    Update goal count for a home team player.
    
    Args:
        user_id: Integer player number (1-14)
        
    Returns:
        Redirect to index page
    """
    global quarter
    global countdown_running, start_time, elapsed_time
    if request.method == 'POST':
        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))
        direction = str(direction)
        if direction == 'increment':
            teama[user_id]['goals'] = teama[user_id]['goals'] + 1
            scores['Home']['goals'] = scores['Home']['goals'] + 1
            if quarter == 1:
                periodscores['Home']['goals1'] = periodscores['Home']['goals1'] + 1
            elif quarter == 2:
                periodscores['Home']['goals2'] = periodscores['Home']['goals2'] + 1
            elif quarter == 3:
                periodscores['Home']['goals3'] = periodscores['Home']['goals3'] + 1
            elif quarter == 4:
                periodscores['Home']['goals4'] = periodscores['Home']['goals4'] + 1
        elif direction == 'decrement':
            teama[user_id]['goals'] = teama[user_id]['goals'] - 1
            scores['Home']['goals'] = scores['Home']['goals'] - 1
            if quarter == 1:
                periodscores['Home']['goals1'] = periodscores['Home']['goals1'] - 1
            elif quarter == 2:
                periodscores['Home']['goals2'] = periodscores['Home']['goals2'] - 1
            elif quarter == 3:
                periodscores['Home']['goals3'] = periodscores['Home']['goals3'] - 1
            elif quarter == 4:
                periodscores['Home']['goals4'] = periodscores['Home']['goals4'] - 1
            direction = "increment"
        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')
        f = open(running_file, 'a')
        writer = csv.writer(f)
        if direction == 'increment':
            data = [ quarter , x[1],x[2], scores['Home']['goals'] , scores['Away']['goals'] , 'Goal' , 'Home',  user_id , home_data['home'][user_id - 1][1],  teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds'] ]
            writer.writerow(data)
        elif direction == 'decrement':
            data = [ quarter , x[1],x[2], scores['Home']['goals'] , scores['Away']['goals'] , 'Remove Goal' , 'Home',  user_id , home_data['home'][user_id - 1][1],  teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds'] ]
            writer.writerow(data)
        f.close()


    return redirect(url_for('index'))


@app.route('/updateteamaintgoal/<direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteamaintgoal(direction,user_id):
    global quarter
    global countdown_running, start_time, elapsed_time
    if request.method == 'POST':

        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))
        direction = str(direction)
        if direction == 'increment':
            teama[user_id]['goals'] = teama[user_id]['goals'] + 1
            scores['Home']['goals'] = scores['Home']['goals'] + 1
            if quarter == 1:
                periodscores['Home']['goals1'] = periodscores['Home']['goals1'] + 1
            elif quarter == 2:
                periodscores['Home']['goals2'] = periodscores['Home']['goals2'] + 1
            elif quarter == 3:
                periodscores['Home']['goals3'] = periodscores['Home']['goals3'] + 1
            elif quarter == 4:
                periodscores['Home']['goals4'] = periodscores['Home']['goals4'] + 1
        elif direction == 'decrement':
            teama[user_id]['goals'] = teama[user_id]['goals'] - 1
            scores['Home']['goals'] = scores['Home']['goals'] - 1
            if quarter == 1:
                periodscores['Home']['goals1'] = periodscores['Home']['goals1'] - 1
            elif quarter == 2:
                periodscores['Home']['goals2'] = periodscores['Home']['goals2'] - 1
            elif quarter == 3:
                periodscores['Home']['goals3'] = periodscores['Home']['goals3'] - 1
            elif quarter == 4:
                periodscores['Home']['goals4'] = periodscores['Home']['goals4'] - 1
            direction = "increment"

        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')
        f = open(running_file, 'a')
        writer = csv.writer(f)
        if direction == 'increment':
            data = [ quarter , x[1],x[2], scores['Home']['goals'] , scores['Away']['goals'] , 'Goal' ,'Home',  user_id , home_data['home'][user_id - 1][1],  teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds'] ]
            writer.writerow(data)
        elif direction == 'decrement':
            data = [ quarter , x[1],x[2], scores['Home']['goals'] , scores['Away']['goals'] , 'Remove Goal' ,'Home',  user_id , home_data['home'][user_id - 1][1],  teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds'] ]
            writer.writerow(data)
        f.close()

    # callintervalgoal
    return redirect(url_for('callintervalgoal'))
    # return redirect(url_for('interval'))

@app.route('/updateteamamajor/<string:direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteamamajor(direction,user_id):
    global quarter
    global countdown_running, start_time, elapsed_time
    if request.method == 'POST':
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))
        if direction == 'increment':
            if teama[user_id]['majors'] == Config.MAJORS:
                teama[user_id]['majors'] = 0
                scores['Home']['majors'] = scores['Home']['majors'] - Config.MAJORS
                if quarter == 1:
                    periodscores['Home']['majors1'] = periodscores['Home']['majors1'] -3
                elif quarter == 2:
                    periodscores['Home']['majors2'] = periodscores['Home']['majors2'] - 3
                elif quarter == 3:
                    periodscores['Home']['majors3'] = periodscores['Home']['majors3'] - 3
                elif quarter == 4:
                    periodscores['Home']['majors4'] = periodscores['Home']['majors4'] - 3
            else:
                teama[user_id]['majors'] = teama[user_id]['majors'] + 1
                scores['Home']['majors'] = scores['Home']['majors'] + 1
                if quarter == 1:
                    periodscores['Home']['majors1'] = periodscores['Home']['majors1'] + 1
                elif quarter == 2:
                    periodscores['Home']['majors2'] = periodscores['Home']['majors2'] + 1
                elif quarter == 3:
                    periodscores['Home']['majors3'] = periodscores['Home']['majors3'] + 1
                elif quarter == 4:
                    periodscores['Home']['majors4'] = periodscores['Home']['majors4'] + 1

        elif direction == 'decrement':
            teama[user_id]['majors'] = teama[user_id]['majors'] - 1
            scores['Home']['majors'] = scores['Home']['majors'] - 1
            if quarter == 1:
                periodscores['Home']['majors1'] = periodscores['Home']['majors1'] - 1
            elif quarter == 2:
                periodscores['Home']['majors2'] = periodscores['Home']['majors2'] - 1
            elif quarter == 3:
                periodscores['Home']['majors3'] = periodscores['Home']['majors3'] - 1
            elif quarter == 4:
                periodscores['Home']['majors4'] = periodscores['Home']['majors4'] - 1
            direction = "increment"

        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')

        f = open(running_file, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
        if direction == 'increment':
            data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Majors',  'Home', user_id, home_data['home'][user_id - 1][1],  teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Remove Majors',  'Home', user_id, home_data['home'][user_id - 1][1],  teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
            writer.writerow(data)
        f.close()

    return redirect(url_for('index'))


@app.route('/updateteamapenalty/<string:direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteamapenalty(direction,user_id):
    global quarter
    global countdown_running, start_time, elapsed_time
    if request.method == 'POST':
        # action = request.form['action']

        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME * 30 - elapsed_time, 0))
        if direction == 'increment':
            if teama[user_id]['majors'] == Config.MAJORS:
                teama[user_id]['majors'] = 0
                scores['Home']['majors'] = scores['Home']['majors'] - Config.MAJORS
                if quarter == 1:
                    periodscores['Home']['majors1'] = periodscores['Home']['majors1'] - 3
                elif quarter == 2:
                    periodscores['Home']['majors2'] = periodscores['Home']['majors2'] - 3
                elif quarter == 3:
                    periodscores['Home']['majors3'] = periodscores['Home']['majors3'] - 3
                elif quarter == 4:
                    periodscores['Home']['majors4'] = periodscores['Home']['majors4'] - 3
            else:
                teama[user_id]['majors'] = teama[user_id]['majors'] + 1
                scores['Home']['majors'] = scores['Home']['majors'] + 1
                if quarter == 1:
                    periodscores['Home']['majors1'] = periodscores['Home']['majors1'] + 1
                elif quarter == 2:
                    periodscores['Home']['majors2'] = periodscores['Home']['majors2'] + 1
                elif quarter == 3:
                    periodscores['Home']['majors3'] = periodscores['Home']['majors3'] + 1
                elif quarter == 4:
                    periodscores['Home']['majors4'] = periodscores['Home']['majors4'] + 1

        elif direction == 'decrement':
            teama[user_id]['majors'] = teama[user_id]['majors'] - 1
            scores['Home']['majors'] = scores['Home']['majors'] - 1
            if quarter == 1:
                periodscores['Home']['majors1'] = periodscores['Home']['majors1'] - 1
            elif quarter == 2:
                periodscores['Home']['majors2'] = periodscores['Home']['majors2'] - 1
            elif quarter == 3:
                periodscores['Home']['majors3'] = periodscores['Home']['majors3'] - 1
            elif quarter == 4:
                periodscores['Home']['majors4'] = periodscores['Home']['majors4'] - 1
            direction = "increment"

        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')

        f = open(running_file, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
        if direction == 'increment':
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Penalty', 'Home', user_id, home_data['home'][user_id - 1][1], teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Remove Penalty', 'Home', user_id, home_data['home'][user_id - 1][1], teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
            writer.writerow(data)
        f.close()

    return redirect(url_for('index'))

# @app.route('/updateteambgoal/<int:user_id>', methods=['GET', 'POST'])
# def updateteambgoal(user_id):
#     global quarter
#     global direction
#     global countdown_running, start_time, elapsed_time
#     if request.method == 'POST':
#         # action = request.form['action']

#         # elapsed_time = time.time() - start_time
#         remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))

#         if direction == 'increment':
#             teamb[user_id]['goals'] = teamb[user_id]['goals'] + 1
#             scores['Away']['goals'] = scores['Away']['goals'] + 1
#             if quarter == 1:
#                 periodscores['Away']['goals1'] = periodscores['Away']['goals1'] + 1
#             elif quarter == 2:
#                 periodscores['Away']['goals2'] = periodscores['Away']['goals2'] + 1
#             elif quarter == 3:
#                 periodscores['Away']['goals3'] = periodscores['Away']['goals3'] + 1
#             elif quarter == 4:
#                 periodscores['Away']['goals4'] = periodscores['Away']['goals4'] + 1
#         elif direction == 'decrement':
#             teamb[user_id]['goals'] = teamb[user_id]['goals'] - 1
#             scores['Away']['goals'] = scores['Away']['goals'] - 1
#             if quarter == 1:
#                 periodscores['Away']['goals1'] = periodscores['Away']['goals1'] - 1
#             elif quarter == 2:
#                 periodscores['Away']['goals2'] = periodscores['Away']['goals2'] - 1
#             elif quarter == 3:
#                 periodscores['Away']['goals3'] = periodscores['Away']['goals3'] - 1
#             elif quarter == 4:
#                 periodscores['Away']['goals4'] = periodscores['Away']['goals4'] - 1
#             direction = "increment"

#         td_str = str(timedelta(seconds=remaining_time))
#         x = td_str.split(':')

#         f = open(running_file, 'a')
#         writer = csv.writer(f)
#         # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
#         data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Goal', user_id, away_data['away'][user_id - 1][1], 'Away',
#         teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
#         writer.writerow(data)
#         f.close()

#     return redirect(url_for('index'))

@app.route('/updateteambgoal/<string:direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteambgoal_direction(direction, user_id):
    global quarter
    global countdown_running, start_time, elapsed_time
    if request.method == 'POST':
        # action = request.form['action']

        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))

        if direction == 'increment':
            teamb[user_id]['goals'] = teamb[user_id]['goals'] + 1
            scores['Away']['goals'] = scores['Away']['goals'] + 1
            if quarter == 1:
                periodscores['Away']['goals1'] = periodscores['Away']['goals1'] + 1
            elif quarter == 2:
                periodscores['Away']['goals2'] = periodscores['Away']['goals2'] + 1
            elif quarter == 3:
                periodscores['Away']['goals3'] = periodscores['Away']['goals3'] + 1
            elif quarter == 4:
                periodscores['Away']['goals4'] = periodscores['Away']['goals4'] + 1
        elif direction == 'decrement':
            teamb[user_id]['goals'] = teamb[user_id]['goals'] - 1
            scores['Away']['goals'] = scores['Away']['goals'] - 1
            if quarter == 1:
                periodscores['Away']['goals1'] = periodscores['Away']['goals1'] - 1
            elif quarter == 2:
                periodscores['Away']['goals2'] = periodscores['Away']['goals2'] - 1
            elif quarter == 3:
                periodscores['Away']['goals3'] = periodscores['Away']['goals3'] - 1
            elif quarter == 4:
                periodscores['Away']['goals4'] = periodscores['Away']['goals4'] - 1
            direction = "increment"

        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')

        f = open(running_file, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
        if direction == 'increment':
            data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Goal', 'Away', user_id, away_data['away'][user_id - 1][1], teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Remove Goal', 'Away', user_id, away_data['away'][user_id - 1][1], teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)
        f.close()

    return redirect(url_for('index'))



@app.route('/updateteambintgoal/<string:direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteambintgoal(direction,user_id):
    global quarter
    global countdown_running, start_time, elapsed_time
    if request.method == 'POST':
        # action = request.form['action']

        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))

        if direction == 'increment':
            teamb[user_id]['goals'] = teamb[user_id]['goals'] + 1
            scores['Away']['goals'] = scores['Away']['goals'] + 1
            if quarter == 1:
                periodscores['Away']['goals1'] = periodscores['Away']['goals1'] + 1
            elif quarter == 2:
                periodscores['Away']['goals2'] = periodscores['Away']['goals2'] + 1
            elif quarter == 3:
                periodscores['Away']['goals3'] = periodscores['Away']['goals3'] + 1
            elif quarter == 4:
                periodscores['Away']['goals4'] = periodscores['Away']['goals4'] + 1
        elif direction == 'decrement':
            teamb[user_id]['goals'] = teamb[user_id]['goals'] - 1
            scores['Away']['goals'] = scores['Away']['goals'] - 1
            if quarter == 1:
                periodscores['Away']['goals1'] = periodscores['Away']['goals1'] - 1
            elif quarter == 2:
                periodscores['Away']['goals2'] = periodscores['Away']['goals2'] - 1
            elif quarter == 3:
                periodscores['Away']['goals3'] = periodscores['Away']['goals3'] - 1
            elif quarter == 4:
                periodscores['Away']['goals4'] = periodscores['Away']['goals4'] - 1
            direction = "increment"

        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')

        f = open(running_file, 'a')
        writer = csv.writer(f)
        if direction == 'increment':
            data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Goal', 'Away', user_id, away_data['away'][user_id - 1][1],             teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Remove Goal', 'Away', user_id, away_data['away'][user_id - 1][1],             teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)
        f.close()

    return redirect(url_for('runintervalgoal'))


@app.route('/updateteambmajor/<string:direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteambmajor(direction,user_id):
    global quarter
    global countdown_running, start_time, elapsed_time
    if request.method == 'POST':
        # direction = request.form['action']


        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME*30 - elapsed_time, 0))

        if direction == 'increment':
            if teamb[user_id]['majors'] == Config.MAJORS:
                teamb[user_id]['majors'] = 0
                scores['Away']['majors'] = scores['Away']['majors'] - Config.MAJORS
                if quarter == 1:
                    periodscores['Away']['majors1'] = periodscores['Away']['majors1'] -3
                elif quarter == 2:
                    periodscores['Away']['majors2'] = periodscores['Away']['majors2'] - 3
                elif quarter == 3:
                    periodscores['Away']['majors3'] = periodscores['Away']['majors3'] - 3
                elif quarter == 4:
                    periodscores['Away']['majors4'] = periodscores['Away']['majors4'] - 3
            else:
                teamb[user_id]['majors'] = teamb[user_id]['majors'] + 1
                scores['Away']['majors'] = scores['Away']['majors'] + 1
                if quarter == 1:
                    periodscores['Away']['majors1'] = periodscores['Away']['majors1'] + 1
                elif quarter == 2:
                    periodscores['Away']['majors2'] = periodscores['Away']['majors2'] + 1
                elif quarter == 3:
                    periodscores['Away']['majors3'] = periodscores['Away']['majors3'] + 1
                elif quarter == 4:
                    periodscores['Away']['majors4'] = periodscores['Away']['majors4'] + 1
        elif direction == 'decrement':
            teamb[user_id]['majors'] = teamb[user_id]['majors'] - 1
            scores['Away']['majors'] = scores['Away']['majors'] - 1
            if quarter == 1:
                periodscores['Away']['majors1'] = periodscores['Away']['majors1'] - 1
            elif quarter == 2:
                periodscores['Away']['majors2'] = periodscores['Away']['majors2'] - 1
            elif quarter == 3:
                periodscores['Away']['majors3'] = periodscores['Away']['majors3'] - 1
            elif quarter == 4:
                periodscores['Away']['majors4'] = periodscores['Away']['majors4'] - 1
            direction = "increment"

        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')

        f = open(running_file, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
        if direction == 'increment':
            data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Major', 'Away', user_id, away_data['away'][user_id - 1][1], teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Remove Major', 'Away', user_id, away_data['away'][user_id - 1][1], teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)
        f.close()

    return redirect(url_for('index'))

@app.route('/updateteambpenalty/<string:direction>/<int:user_id>', methods=['GET', 'POST'])
def updateteambpenalty(direction,user_id):
    global quarter
    global countdown_running, start_time, elapsed_time
    if request.method == 'POST':
        # action = request.form['action']

        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(Config.GAME_TIME * 30 - elapsed_time, 0))
        if direction == 'increment':
            if teamb[user_id]['majors'] == Config.MAJORS:
                teamb[user_id]['majors'] = 0
                scores['Away']['majors'] = scores['Away']['majors'] - Config.MAJORS
                if quarter == 1:
                    periodscores['Away']['majors1'] = periodscores['Away']['majors1'] - 3
                elif quarter == 2:
                    periodscores['Away']['majors2'] = periodscores['Away']['majors2'] - 3
                elif quarter == 3:
                    periodscores['Away']['majors3'] = periodscores['Away']['majors3'] - 3
                elif quarter == 4:
                    periodscores['Away']['majors4'] = periodscores['Away']['majors4'] - 3
            else:
                teamb[user_id]['majors'] = teamb[user_id]['majors'] + 1
                scores['Away']['majors'] = scores['Away']['majors'] + 1
                if quarter == 1:
                    periodscores['Away']['majors1'] = periodscores['Away']['majors1'] + 1
                elif quarter == 2:
                    periodscores['Away']['majors2'] = periodscores['Away']['majors2'] + 1
                elif quarter == 3:
                    periodscores['Away']['majors3'] = periodscores['Away']['majors3'] + 1
                elif quarter == 4:
                    periodscores['Away']['majors4'] = periodscores['Away']['majors4'] + 1

        elif direction == 'decrement':
            teamb[user_id]['majors'] = teamb[user_id]['majors'] - 1
            scores['Away']['majors'] = scores['Away']['majors'] - 1
            if quarter == 1:
                periodscores['Away']['majors1'] = periodscores['Away']['majors1'] - 1
            elif quarter == 2:
                periodscores['Away']['majors2'] = periodscores['Away']['majors2'] - 1
            elif quarter == 3:
                periodscores['Away']['majors3'] = periodscores['Away']['majors3'] - 1
            elif quarter == 4:
                periodscores['Away']['majors4'] = periodscores['Away']['majors4'] - 1
            direction = "increment"

        td_str = str(timedelta(seconds=remaining_time))
        x = td_str.split(':')

        f = open(running_file, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
        if direction == 'increment':
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Penalty', 'Away', user_id, away_data['away'][user_id - 1][1], teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Remove Penalty', 'Away', user_id, away_data['away'][user_id - 1][1], teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
            writer.writerow(data)
        f.close()

    return redirect(url_for('index'))



@app.route('/period', methods=['GET', 'POST'])
def period():
    if request.method == 'POST':
        global quarter, direction
        if direction == 'increment':
            quarter = quarter + 1
            # timestamp = datetime.now()

            # f = open(running_file, 'a')
            # writer = csv.writer(f)
            # header = ['Game Status at ', Config.DEFAULT_LOCATION, ' on the ', timestamp, 'end of quarter :' ,quarter -1, ]
            # writer.writerow(header)

            # # header1 = ['HomeScore', 'AwayScore', 'HomeMajors', 'AwayMajors']
            # # writer.writerow(header1)

            # data = ['Home score:', scores['Home']['goals'], 'Away score :', scores['Away']['goals'],'Home Majors:',  scores['Home']['majors'], 'Away Majors :', scores['Away']['majors']]
            # writer.writerow(data)

            # header = ['Quarter', 'Min', 'Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'name', 'team', 'goals', 'majors', 'reds']
            # writer.writerow(header)

            # f.close()
        elif direction == 'decrement':
            quarter = quarter - 1
            # timestamp = datetime.now()

            # f = open(running_file, 'a')
            # writer = csv.writer(f)
            # header = ['Game Status at ', Config.DEFAULT_LOCATION, ' on the ', timestamp, 'end of quarter :' ,quarter -1, ]
            # writer.writerow(header)

            # # header1 = ['HomeScore', 'AwayScore', 'HomeMajors', 'AwayMajors']
            # # writer.writerow(header1)

            # data = ['Home score:', scores['Home']['goals'], 'Away score :', scores['Away']['goals'],'Home Majors:',  scores['Home']['majors'], 'Away Majors :', scores['Away']['majors']]
            # writer.writerow(data)

            # header = ['Quarter', 'Min', 'Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'name', 'team', 'goals', 'majors', 'reds']
            # writer.writerow(header)

            # f.close()
            direction = "increment"

    return redirect(url_for('index'))

@app.route('/clear', methods=['GET', 'POST'])
def clear_direction():
    global direction
    direction = "decrement"
    return redirect(url_for('index'))

@app.route('/connectble', methods=['GET', 'POST'])
def connectble():
    """Connect to all configured BLE devices.

    Always disconnects existing sessions first (exit + dis_ble), waits one
    second, then runs init_ble(), so reconnecting does not fight the prior link.

    Historically this redirected to the index page. It now returns JSON so
    the Connect button on setup.html can show a spinner and stay on the
    settings page; a plain GET from a browser address bar still works.
    """
    global BLUETOOTH_CONNECT
    error = None
    try:
        # Clean slate: notify devices, drop links, wait for the stack to settle,
        # then scan/connect (avoids messy overlap when a device was already connected).
        try:
            ble_send_command("exit")
        except Exception as e:
            print(f"[BLE] exit command before connect failed: {e}")
        BLUETOOTH_CONNECT = 0
        _run_ble_coro(dis_ble(), reraise=True)
        sleep(1)
        BLUETOOTH_CONNECT = 1
        _run_ble_coro(init_ble(), reraise=True)
        sleep(1)
        if not ble_any_live_client():
            error = "No BLE devices connected after scan/connect."
            print(f"[BLE] /connectble: {error}")
        else:
            ble_send_command("TEST")
    except FuturesTimeoutError:
        error = "BLE operation timed out."
        print(f"[BLE] /connectble failed: {error}")
    except Exception as e:
        error = str(e)
        print(f"[BLE] /connectble failed: {e}")

    # If the client explicitly asked for JSON (fetch from setup.html) or this
    # is a POST, return JSON. Otherwise keep the old redirect behaviour.
    wants_json = (
        request.method == 'POST'
        or 'application/json' in (request.headers.get('Accept') or '')
        or request.args.get('format') == 'json'
    )
    if wants_json:
        payload = {
            'status': 'error' if error else 'success',
            'flags': get_device_connection_flags(),
        }
        if error:
            payload['message'] = error
        return jsonify(payload), (500 if error else 200)
    return redirect(url_for('index'))


@app.route('/reconnectble', methods=['GET', 'POST'])
def reconnectble():
    """Manual reconnect trigger: re-scan and reconnect any missing/dropped BLE clients."""
    global BLUETOOTH_CONNECT
    try:
        if not ble_clients:
            # Nothing known yet -> behave like a fresh connect.
            BLUETOOTH_CONNECT = 1
            _run_ble_coro(init_ble(), reraise=True)
        else:
            _run_ble_coro(reconnect_ble(), reraise=True)
        if not ble_any_live_client():
            msg = "No BLE devices connected."
            print(f"[BLE] /reconnectble: {msg}")
            return jsonify(
                {
                    'status': 'error',
                    'message': msg,
                    'flags': get_device_connection_flags(),
                }
            ), 500
        ble_send_command("TEST")
        return jsonify({'status': 'success', 'flags': get_device_connection_flags()})
    except FuturesTimeoutError:
        msg = "BLE operation timed out."
        print(f"[BLE] /reconnectble failed: {msg}")
        return jsonify(
            {
                'status': 'error',
                'message': msg,
                'flags': get_device_connection_flags(),
            }
        ), 500
    except Exception as e:
        print(f"[BLE] /reconnectble failed: {e}")
        return jsonify(
            {
                'status': 'error',
                'message': str(e),
                'flags': get_device_connection_flags(),
            }
        ), 500


@app.route('/disconnectble', methods=['GET', 'POST'])
def disconnectble():
    global BLUETOOTH_CONNECT
    try:
        ble_send_command("exit")
    except Exception as e:
        print(f"[BLE] exit command failed: {e}")
    BLUETOOTH_CONNECT = 0
    # Watchdog will go idle on its own because BLUETOOTH_CONNECT == 0.
    _run_ble_coro(dis_ble())
    return redirect(url_for('settings'))


@app.route('/connectserial', methods=['GET', 'POST'])
def connectserial():
    """Open the COM port saved in settings (JSON for setup.html fetch)."""
    requested_port = (request.args.get("port") or request.form.get("port") or "").strip()
    if requested_port:
        Config.SERIAL_PORT = requested_port
    error = connect_serial()
    wants_json = (
        request.method == 'POST'
        or 'application/json' in (request.headers.get('Accept') or '')
        or request.args.get('format') == 'json'
    )
    if wants_json:
        payload = {
            'status': 'error' if error else 'success',
            'flags': get_device_connection_flags(),
        }
        if error:
            payload['message'] = error
        return jsonify(payload), (500 if error else 200)
    return redirect(url_for('settings'))


@app.route('/disconnectserial', methods=['GET', 'POST'])
def disconnectserial():
    """Close the serial relay port."""
    disconnect_serial()
    wants_json = (
        request.method == 'POST'
        or 'application/json' in (request.headers.get('Accept') or '')
        or request.args.get('format') == 'json'
    )
    if wants_json:
        return jsonify({'status': 'success', 'flags': get_device_connection_flags()})
    return redirect(url_for('settings'))

    
@app.route('/start', methods=['GET', 'POST'])
def start():
    global quarter, scores, TeamHome, TeamAway, periodscores, teama, teamb
    global direction, hometimeoutv, awaytimeoutv, filename, filenamebak, running_file, compress_file
    if request.method == 'POST':


        ble_send_command("TEST")

        ensureResultsDirs()
        filename = str(buildGameCsvPath())
        filenamebak = filename + '.bak'
        running_file = str(buildTempCsvPath())
        compress_file = buildCompressCsvBasename()
        now = datetime.now()  # current date and time
        timestamp = now.strftime("%d/%m/%Y, %H:%M:%S")

        direction = "increment"
        # print(direction)
        quarter = int(1)

        scores = {
        'Home': {'goals': 0, 'majors': 0},
        'Away': {'goals': 0, 'majors': 0}
        }
        TeamHome = scores['Home']
        TeamAway = scores['Away']

        periodscores = {
        'Home': {'goals1': 0, 'majors1': 0, 'goals2': 0, 'majors2': 0, 'goals3': 0, 'majors3': 0, 'goals4': 0,
        'majors4': 0},
        'Away': {'goals1': 0, 'majors1': 0, 'goals2': 0, 'majors2': 0, 'goals3': 0, 'majors3': 0, 'goals4': 0,
        'majors4': 0}
        }

        teama = {
        1: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        2: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        3: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        4: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        5: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        6: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        7: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        8: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        9: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        10: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        11: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        12: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        13: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        14: {'assists': 0, 'goals': 0, 'majors': 0, 'reds': 0}
        }

        teamb = {
        1: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        2: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        3: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        4: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        5: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        6: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        7: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        8: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        9: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        10: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        11: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        12: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        13: {'assists': 0, 'goals': 0, 'majors': 0 , 'reds': 0 },
        14: {'assists': 0, 'goals': 0, 'majors': 0, 'reds': 0}
        }
        hometimeoutv = 0
        awaytimeoutv = 0

        header = ['New Game Held at ',Config.DEFAULT_LOCATION,' on the ',timestamp]
        f = open(filename, 'w')
        writer = csv.writer(f)
        writer.writerow(header)

        f.close()

        f = open(filenamebak, 'w')
        writer = csv.writer(f)

        header2 = ['Home Team: ', Config.DEFAULT_HOME_TEAM]
        writer.writerow(header2)
        header2 = ['Home Player', 'name', 'goals', 'majors', 'reds']

        writer.writerow(header2)
        for user_id in teama:
            data = [user_id, home_data['home'][user_id - 1][1], teama[user_id]['goals'], teama[user_id]['majors'],
                    teama[user_id]['reds']]
            writer.writerow(data)

        header2 = ['Away Team: ', Config.DEFAULT_AWAY_TEAM]
        writer.writerow(header2)
        header2 = ['Away Player', 'name', 'goals', 'majors', 'reds']
        writer.writerow(header2)
        for user_id in teamb:
            data = [user_id, away_data['away'][user_id - 1][1], teamb[user_id]['goals'], teamb[user_id]['majors'],
                    teamb[user_id]['reds']]
            writer.writerow(data)

        header2 = ['Referees: ']
        writer.writerow(header2)
        header2 = ['Hatnumber', 'Name', 'Club', 'Expences']
        writer.writerow(header2)
        for i in ref_data['referee']:
            data = i[0], i[1], i[2], i[3]
            writer.writerow(data)
        f.close()


    return redirect(url_for('index'))


@app.route('/finish', methods=['GET', 'POST'])
def finish():
    global quarter
    if  request.method == 'GET' or request.method == 'POST':

        # command = str(0)
        # ble_send_int(command)
        # ble_send_command("exit")

        # now = datetime.now()  # current date and time
        # timestamp = now.strftime("%d/%m/%Y, %H:%M:%S")

        # f = open(filename, 'a')
        # writer = csv.writer(f)
        # header = ['Game Over at ', Config.DEFAULT_LOCATION, ' on the ', timestamp]
        # writer.writerow(header)
        # header = ['Home: ', scores['Home']['goals'] , 'Away :' , scores['Away']['goals']]
        # writer.writerow(header)

        # header = ['breakdown']
        # writer.writerow(header)
        # header = ['Team','Event','P1','P2','P3','P4']
        # writer.writerow(header)

        # for team in periodscores:
        #     data = [team , 'Goals', periodscores[team]['goals1'], periodscores[team]['goals2'], periodscores[team]['goals3'], periodscores[team]['goals4']]
        #     writer.writerow(data)
        # for team in periodscores:
        #     data = [team , 'Majors', periodscores[team]['majors1'], periodscores[team]['majors2'], periodscores[team]['majors3'], periodscores[team]['majors4']]
        #     writer.writerow(data)

        # header2 = ['Home Team: ', Config.DEFAULT_HOME_TEAM ]
        # writer.writerow(header2)
        # header2 = ['Home Player','name', 'goals', 'majors', 'reds']

        # writer.writerow(header2)
        # for user_id in teama:

        #     data = [user_id ,home_data['home'][user_id-1][1], teama[user_id]['goals'],teama[user_id]['majors'],teama[user_id]['reds'] ]
        #     writer.writerow(data)


        # header2 = ['Away Team: ', Config.DEFAULT_AWAY_TEAM ]
        # writer.writerow(header2)
        # header2 = ['Away Player','name', 'goals', 'majors', 'reds']
        # writer.writerow(header2)
        # for user_id in teamb:
        #     data = [user_id ,away_data['away'][user_id-1][1], teamb[user_id]['goals'],teamb[user_id]['majors'],teamb[user_id]['reds'] ]
        #     writer.writerow(data)

        # header2 = ['Referees: ' ]
        # writer.writerow(header2)
        # header2 = ['Hatnumber','Name', 'Club', 'Expences']
        # writer.writerow(header2)
        # for i in ref_data['referee'] :
        #     data = i[0],i[1],i[2],i[3]
        #     writer.writerow(data)

        # header = ['Quarter', 'Min', 'Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'name', 'team', 'goals',
        #           'majors', 'reds']
        # writer.writerow(header)

        # f.close()

        # try:
        #     with open(running_file, newline='') as in_file:
        #         with open(filename, 'a', newline='') as out_file:
        #             writer = csv.writer(out_file)
        #             for row in csv.reader(in_file):
        #                 if row:
        #                     writer.writerow(row)
        #     f.close()
        # except :
        #     print('finish')
        # try:
        #     with open(filename, newline='') as in_file:
        #         with open(compress_file, 'w', newline='') as out_file:
        #             writer = csv.writer(out_file)
        #             for row in csv.reader(in_file):
        #                 if row:
        #                     writer.writerow(row)
        #     f.close()
        # except :
        #     print('finish')

        # try:
        #     os.remove(running_file)
        # except OSError as e:  # this would be "except OSError, e:" before Python 2.6
        #     if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
        #         raise  # re-raise exception if a different error occurred...

        # try:
        #     os.remove(filename)
        # except OSError as e:  # this would be "except OSError, e:" before Python 2.6
        #     if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
        #         raise  # re-raise exception if a different error occurred...

        return redirect(url_for('convert_csv_to_pdf'))

    return redirect(url_for('index'))


@app.route('/hometimeout')
def hometimeout():
    global hometimeoutv
    global quarter
    global direction
    global countdown_running, start_time, elapsed_time
    global timeout, reason
    if quarter == 0 :
        return redirect(url_for('index'))
    reason = 'Home Timeout'
    timeout = Config.TIMEOUT_TIME
    # elapsed_time = time.time() - start_time
    remaining_time = math.floor(max(Config.GAME_TIME * 30 - elapsed_time, 0))
    if countdown_running:
        if direction == 'increment':
            pause_countdown()
            hometimeoutv = int(hometimeoutv) + 1
            # print(hometimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout',
            'Home', hometimeoutv,'','','','']
            writer.writerow(data)
            f.close()
            # pause_countdown()
            time.sleep(1)
            start_timeout()
            return redirect(url_for('timeout_page'))

        elif direction == 'decrement':
            hometimeoutv = int(hometimeoutv) - 1
            # print(hometimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout removed',
            'Home', hometimeoutv,'','','','']
            writer.writerow(data)
            f.close()
            direction = "increment"

    else:
        # msg = 'clock was not running'
        # flash(msg, "warning")
        if direction == 'increment':
            hometimeoutv = int(hometimeoutv) + 1
            # print(hometimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout', 'Home',
            hometimeoutv,'','','','']
            writer.writerow(data)
            f.close()
            # pause_countdown()
            time.sleep(1)
            start_timeout()
            return redirect(url_for('timeout_page'))

        elif direction == 'decrement':
            hometimeoutv = int(hometimeoutv) - 1
            # print(hometimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout removed',
            'Home', hometimeoutv,'','','','']
            writer.writerow(data)
            f.close()
            direction = "increment"

    return redirect(url_for('index'))


@app.route('/awaytimeout')
def awaytimeout():
    global awaytimeoutv
    global quarter
    global direction
    global countdown_running, start_time, elapsed_time
    global timeout, reason
    if quarter == 0 :
        return redirect(url_for('index'))
    reason = 'Away Timeout'
    timeout = Config.TIMEOUT_TIME
    # print(timeout)
    # print(timeouttime)
    # elapsed_time = time.time() - start_time
    remaining_time = math.floor(max(Config.GAME_TIME * 30 - elapsed_time, 0))
    if countdown_running:
        if direction == 'increment':
            awaytimeoutv = int(awaytimeoutv) + 1
            # print(awaytimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout','Away', awaytimeoutv,'','','','']
            writer.writerow(data)
            f.close()
            pause_countdown()
            time.sleep(1)
            stop_timeout()
            return redirect(url_for('timeout_page'))

        elif direction == 'decrement':
            awaytimeoutv = int(awaytimeoutv) - 1
            # print(awaytimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout','Away', awaytimeoutv,'','','','']
            writer.writerow(data)
            f.close()
            direction = "increment"

    else:
        # msg = 'clock was not running'
        # flash(msg, "warning")
        if direction == 'increment':
            awaytimeoutv = int(awaytimeoutv) + 1
            # print(hometimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout', 'Away',  awaytimeoutv,'','','','']
            writer.writerow(data)
            f.close()
            # pause_countdown()
            time.sleep(1)
            start_timeout()
            return redirect(url_for('timeout_page'))
        
        elif direction == 'decrement':
            awaytimeoutv = int(awaytimeoutv) - 1
            # print(awaytimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout', 'Away', awaytimeoutv,'','','','']
            writer.writerow(data)
            f.close()
            direction = "increment"

    return redirect(url_for('index'))



@app.route('/timeout')
def timeout_page():
    global timeout
    timeout = Config.TIMEOUT_TIME
    start_timeout()
    remaining_time = math.floor(max(Config.GAME_TIME * 30 - elapsed_time, 0))
    return render_template('timeout.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red,                        
                           elapsed_timeout=elapsedtimeout, clocktime=remaining_time)
@app.route('/runinterval')
def runinterval():
    global timeout
    if quarter == 3 :
        timeout = Config.HALFTIME
    else:
        timeout = Config.INTERVAL_TIME

    start_timeout()
    return render_template('interval.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)



@app.route('/runintervalgoal')
def runintervalgoal():
    global timeout
    # if quarter == 3 :
    #     timeout = Config.HALFTIME
    # else:
    #     timeout = Config.INTERVAL_TIME

    # start_timeout()
    return render_template('interval.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)


@app.route('/interval')
def interval():
    start_timeout()
    return render_template('interval.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)



@app.route('/returninterval')
def returninterval():
    global quarter, interval_active
    if not interval_active:
        return redirect(url_for('index'))

    interval_active = False
    stop_countdown()

    timestamp = datetime.now()

    # f = open(running_file, 'a')
    # writer = csv.writer(f)
    # header = ['Game Status at ', Config.DEFAULT_LOCATION, ' on the ', timestamp, 'end of quarter :', quarter, ]
    # writer.writerow(header)

    # # header1 = ['HomeScore', 'AwayScore', 'HomeMajors', 'AwayMajors']
    # # writer.writerow(header1)

    # data = ['Home score:', scores['Home']['goals'], 'Away score :', scores['Away']['goals'], 'Home Majors:',
    #         scores['Home']['majors'], 'Away Majors :', scores['Away']['majors']]
    # writer.writerow(data)

    # header = ['Quarter', 'Min', 'Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'name', 'team', 'goals', 'majors',
    #           'reds']
    # writer.writerow(header)

    # f.close()
    quarter=quarter +1
    return redirect(url_for('index'))


@app.route('/callinterval', methods=['GET', 'POST'])
def callinterval():
    if request.method == 'GET':
        global quarter, interval_active
        global countdown_running, start_time, elapsed_time
        global timeout, reason ,intervaltime
        if interval_active:
            return redirect(url_for('runinterval'))

        interval_active = True
        reason = 'Break'
        timeout = Config.TIMEOUT_TIME
        # elapsed_time = time.time() - start_time
        # remaining_time = math.floor(max(gametime * 30 - elapsed_time, 0))

        if countdown_running:
            pause_countdown()
        time.sleep(1)
        stop_timeout()
        return redirect(url_for('runinterval'))

    return redirect(url_for('index'))

@app.route('/callintervalgoal', methods=['GET', 'POST'])
def callintervalgoal():
    if request.method == 'GET':
        global quarter
        global countdown_running, start_time, elapsed_time
        global timeout, reason ,intervaltime
        # reason = 'Break'
        # timeout = Config.TIMEOUT_TIME
        # # elapsed_time = time.time() - start_time
        # # remaining_time = math.floor(max(gametime * 30 - elapsed_time, 0))
        # quarter=quarter +1
        # pause_countdown()
        # time.sleep(1)
        # stop_timeout()
        return redirect(url_for('runintervalgoal'))

    return redirect(url_for('index'))

@app.route('/settings')
def settings():
    return render_template(
        'setup.html',
        HomeTeam=Config.DEFAULT_HOME_TEAM,
        AwayTeam=Config.DEFAULT_AWAY_TEAM,
        location=Config.DEFAULT_LOCATION,
        ble_clients=ble_clients,
        serial_port=Config.SERIAL_PORT,
        com_ports=list_com_ports(),
        listen_ip=_preferred_listening_ipv4_address(),
    )

@app.route('/help')
def help():
    return render_template('help.html')

@app.route('/save' , methods=['GET', 'POST'])
def save():

    Config.GAME_TIME = int(request.form['game'])
    Config.INTERVAL_TIME = int(request.form['interval'])
    Config.HALFTIME = int(request.form['half'])
    Config.DEFAULT_LOCATION = (request.form['Location'])
    Config.DEFAULT_HOME_TEAM = (request.form['Home'])
    Config.DEFAULT_AWAY_TEAM = (request.form['Away'])
    Config.SHOT_CLOCK = int(request.form['shotclock'])
    Config.FOUL_CLOCK = max(Config.SHOT_CLOCK - 10, 0)
    Config.MAJORS = int(request.form['majors'])
    Config.SERIAL_PORT = (request.form.get('serial_port') or '').strip()
    # Config.BLUETOOTH_NAME = str(request.form['ble'])

    if Config.SERIAL_PORT:
        try_autoconnect_serial()
    else:
        disconnect_serial()

    return redirect(url_for('index'))


@app.route('/savehomeplayers/<user_id>' , methods=['GET', 'POST'])
def savehomeplayers(user_id):
    global home_data, home_staff
    user_id = (user_id or "").strip()
    if user_id not in home_staff:
        home_staff[user_id] = [['HC', ''], ['AC', ''], ['TM', '']]
    staff_rows = home_staff[user_id]

    if request.method == 'POST':
        # Clear the existing data for the user ID
        home_data[user_id] = []

        # Get the number of entries
        num_entries = int(request.form.get('num_entries') or 0)

        # Update the user's data with the new entries
        for i in range(num_entries):
            hatnum = request.form.get(f'hatnum_{i}')
            name = request.form.get(f'name_{i}')

            form_data = [hatnum or "", name or ""]

            home_data[user_id].append(form_data)

        for row in staff_rows:
            role = row[0]
            row[1] = (request.form.get(f'staff_{role}', '') or '').strip()
        # print(home_data)
        return redirect(url_for('index'))

    # For GET requests, render the form with existing data
    existing_data = home_data.get(user_id, [])

    return render_template(
        'hometeamsetup.html',
        user_id=user_id,
        data=existing_data,
        staff_data=staff_rows,
        club_name=Config.DEFAULT_HOME_TEAM,
    )


# Characters not allowed in filenames on Windows/macOS/Linux. Spaces collapse to underscores.
_FILENAME_STRIP_RE = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def _safeRosterFilename(raw_name: str, default_stem: str = "home_roster") -> str:
    """Reduce a user-provided filename to a safe basename with a .csv extension.

    Strips path separators and reserved characters, collapses whitespace, blocks
    parent-directory traversal, and clamps length. Always returns a `.csv` file.
    """
    fallback = default_stem if (default_stem or "").strip() else "home_roster"

    base = Path((raw_name or "").strip()).name
    base = _FILENAME_STRIP_RE.sub("", base)
    base = re.sub(r"\s+", "_", base).strip("._")
    if not base or base in {".", ".."}:
        base = fallback
    if not base.lower().endswith(".csv"):
        base = f"{base}.csv"
    return base[:120]


@app.route('/exporthomeplayers/<user_id>', methods=['POST'])
def exporthomeplayers(user_id):
    """Write the supplied roster CSV to the same directory as start.py.

    The browser cannot save to an arbitrary OS folder, so the page POSTs the
    already-built CSV here and the server writes it next to this script.
    """
    payload = request.get_json(silent=True) or {}
    csv_text = payload.get("csv", "")
    requested_name = payload.get("filename", "")

    if not isinstance(csv_text, str) or not csv_text.strip():
        return jsonify({"ok": False, "error": "Roster is empty."}), 400

    safe_name = _safeRosterFilename(requested_name)
    target_dir = Path(__file__).resolve().parent
    target_path = (target_dir / safe_name).resolve()

    if target_dir not in target_path.parents and target_path != target_dir / safe_name:
        return jsonify({"ok": False, "error": "Invalid filename."}), 400

    try:
        target_path.write_text(csv_text, encoding="utf-8", newline="")
    except OSError as exc:
        return jsonify({"ok": False, "error": f"Failed to write file: {exc}"}), 500

    return jsonify({
        "ok": True,
        "filename": safe_name,
        "path": str(target_path),
        "user_id": user_id,
    })


@app.route('/exportawayplayers/<user_id>', methods=['POST'])
def exportawayplayers(user_id):
    """Write away roster CSV next to start.py (same contract as exporthomeplayers)."""
    payload = request.get_json(silent=True) or {}
    csv_text = payload.get("csv", "")
    requested_name = payload.get("filename", "")

    if not isinstance(csv_text, str) or not csv_text.strip():
        return jsonify({"ok": False, "error": "Roster is empty."}), 400

    safe_name = _safeRosterFilename(requested_name, default_stem="away_roster")
    target_dir = Path(__file__).resolve().parent
    target_path = (target_dir / safe_name).resolve()

    if target_dir not in target_path.parents and target_path != target_dir / safe_name:
        return jsonify({"ok": False, "error": "Invalid filename."}), 400

    try:
        target_path.write_text(csv_text, encoding="utf-8", newline="")
    except OSError as exc:
        return jsonify({"ok": False, "error": f"Failed to write file: {exc}"}), 500

    return jsonify({
        "ok": True,
        "filename": safe_name,
        "path": str(target_path),
        "user_id": user_id,
    })


@app.route('/saveawayplayers/<user_id>' , methods=['GET', 'POST'])
def saveawayplayers(user_id):
    global away_data, away_staff
    user_id = (user_id or "").strip()
    if user_id not in away_staff:
        away_staff[user_id] = [['HC', ''], ['AC', ''], ['TM', '']]
    staff_rows = away_staff[user_id]

    if request.method == 'POST':
        # Clear the existing data for the user ID
        away_data[user_id] = []

        # Get the number of entries
        num_entries = int(request.form.get('num_entries') or 0)

        # Update the user's data with the new entries
        for i in range(num_entries):
            hatnum = request.form.get(f'hatnum_{i}')
            name = request.form.get(f'name_{i}')

            form_data = [hatnum or "", name or ""]

            away_data[user_id].append(form_data)

        for row in staff_rows:
            role = row[0]
            row[1] = (request.form.get(f'staff_{role}', '') or '').strip()
        # print(away_data)
        return redirect(url_for('index'))

    # For GET requests, render the form with existing data
    existing_data = away_data.get(user_id, [])
    return render_template(
        'awayteamsetup.html',
        user_id=user_id,
        data=existing_data,
        staff_data=staff_rows,
        club_name=Config.DEFAULT_AWAY_TEAM,
    )

@app.route('/saverefdata/<user_id>' , methods=['GET', 'POST'])
def saverefdata(user_id):
    if request.method == 'POST':
        # Clear the existing data for the user ID
        ref_data[user_id] = []

        # Get the number of entries
        num_entries = int(request.form.get('num_entries') or 0)

        # Update the user's data with the new entries
        for i in range(num_entries):
            hatnum = request.form.get(f'hatnum_{i}')
            name = request.form.get(f'name_{i}')
            club = request.form.get(f'club_{i}')
            expences = request.form.get(f'expences_{i}')

            form_data = [hatnum or "", name or "", club or "", expences or ""]

            ref_data[user_id].append(form_data)
        # print(ref_data)
        return redirect(url_for('index'))

    # For GET requests, render the form with existing data
    existing_data = ref_data.get(user_id, [])

    return render_template('refdata.html', user_id=user_id, data=existing_data)

@app.route('/convert', methods=['GET'])
def convert_csv_to_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_font("helvetica", size=10)

    line_height = 6
    max_text_width = 190  # approx page width minus margins (A4 portrait)

    def write_line(text: str, *, bold: bool = False) -> None:
        pdf.set_font("helvetica", style="B" if bold else "", size=10)
        if pdf.get_string_width(text) > max_text_width:
            pdf.multi_cell(0, line_height, text=text, border=0)
        else:
            pdf.cell(0, line_height, text=text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def write_row(row) -> None:
        line_text = " | ".join("" if cell is None else str(cell) for cell in row)
        write_line(line_text)

    def write_scoretable() -> None:
        usable_w = pdf.w - pdf.l_margin - pdf.r_margin

        pdf.set_font("helvetica", style="B", size=11)
        pdf.cell(0, line_height + 1, text="Game Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

        # Score row (2 columns)
        col_w = usable_w / 2
        pdf.set_font("helvetica", style="B", size=10)
        pdf.cell(col_w, line_height, text="Home", border=1)
        pdf.cell(col_w, line_height, text="Away", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("helvetica", style="", size=10)
        home_label = f"{Config.DEFAULT_HOME_TEAM}: {scores['Home']['goals']}"
        away_label = f"{Config.DEFAULT_AWAY_TEAM}: {scores['Away']['goals']}"
        pdf.cell(col_w, line_height, text=home_label, border=1)
        pdf.cell(col_w, line_height, text=away_label, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(3)

    # 1) In-memory arrays (always include)
    write_scoretable()

    # Two-column layout: Home left, Away right
    def write_two_column_teams() -> None:
        left_x = pdf.l_margin
        gutter = 6
        usable_w = pdf.w - pdf.l_margin - pdf.r_margin
        col_w = (usable_w - gutter) / 2
        right_x = left_x + col_w + gutter

        # Columns: Player | Name | Goals | Majors | Reds
        player_w = 12
        goals_w = 12
        majors_w = 14
        reds_w = 12
        name_w = col_w - (player_w + goals_w + majors_w + reds_w)

        start_y = pdf.get_y()

        def ensure_space(y: float) -> float:
            bottom_limit = pdf.h - pdf.b_margin
            if y + (line_height * 2) > bottom_limit:
                pdf.add_page()
                return pdf.get_y()
            return y

        def draw_header(x: float, y: float, title: str) -> float:
            y = ensure_space(y)
            pdf.set_xy(x, y)
            pdf.set_font("helvetica", style="B", size=10)
            pdf.cell(col_w, line_height, text=title, border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.set_x(x)
            pdf.set_font("helvetica", style="B", size=10)
            pdf.cell(player_w, line_height, text="Hat", border=1)
            pdf.cell(name_w, line_height, text="Name", border=1)
            pdf.cell(goals_w, line_height, text="G", border=1, align="C")
            pdf.cell(majors_w, line_height, text="M", border=1, align="C")
            pdf.cell(reds_w, line_height, text="C", border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            return pdf.get_y()

        left_y = draw_header(left_x, start_y, f"Home Team: {Config.DEFAULT_HOME_TEAM}")
        right_y = draw_header(right_x, start_y, f"Away Team: {Config.DEFAULT_AWAY_TEAM}")

        left_ids = list(teama.keys()) if isinstance(teama, dict) else []
        right_ids = list(teamb.keys()) if isinstance(teamb, dict) else []
        n = max(len(left_ids), len(right_ids))

        for i in range(n):
            row_y = max(left_y, right_y)
            row_y = ensure_space(row_y)

            # Home row
            pdf.set_font("helvetica", style="", size=10)
            pdf.set_xy(left_x, row_y)
            if i < len(left_ids):
                user_id = left_ids[i]
                name = home_data.get("home", [])[int(user_id) - 1][1] if int(user_id) - 1 < len(home_data.get("home", [])) else ""
                stats = teama.get(user_id) or newPlayerStats()
                goals = stats.get("goals", "")
                majors = stats.get("majors", "")
                reds = stats.get("reds", "")
            else:
                user_id, name, goals, majors, reds = "", "", "", "", ""
            pdf.cell(player_w, line_height, text=str(user_id), border=1)
            pdf.cell(name_w, line_height, text=str(name), border=1)
            pdf.cell(goals_w, line_height, text=str(goals), border=1, align="C")
            pdf.cell(majors_w, line_height, text=str(majors), border=1, align="C")
            pdf.cell(reds_w, line_height, text=str(reds), border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            left_y = row_y + line_height

            # Away row
            pdf.set_xy(right_x, row_y)
            if i < len(right_ids):
                user_id = right_ids[i]
                name = away_data.get("away", [])[int(user_id) - 1][1] if int(user_id) - 1 < len(away_data.get("away", [])) else ""
                stats = teamb.get(user_id) or newPlayerStats()
                goals = stats.get("goals", "")
                majors = stats.get("majors", "")
                reds = stats.get("reds", "")
            else:
                user_id, name, goals, majors, reds = "", "", "", "", ""
            pdf.cell(player_w, line_height, text=str(user_id), border=1)
            pdf.cell(name_w, line_height, text=str(name), border=1)
            pdf.cell(goals_w, line_height, text=str(goals), border=1, align="C")
            pdf.cell(majors_w, line_height, text=str(majors), border=1, align="C")
            pdf.cell(reds_w, line_height, text=str(reds), border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            right_y = row_y + line_height

        def draw_staff_coach_column(x: float, y: float, staff_rows: list, coach_dict: dict) -> float:
            idx_w = 10
            key_w = 14
            val_w = 11
            name_w = max(18.0, col_w - idx_w - key_w - val_w)
            pdf.set_xy(x, y)
            pdf.set_font("helvetica", style="B", size=8)
            # pdf.cell(idx_w, line_height, text="#", border=1, align="C")
            pdf.cell(key_w, line_height, text="Key", border=1, align="C")
            pdf.cell(name_w, line_height, text="Name", border=1)
            pdf.cell(val_w, line_height, text="Card", border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            y = pdf.get_y()
            pdf.set_font("helvetica", style="", size=8)
            for i, row in enumerate(staff_rows):
                role_key = row[0] if len(row) > 0 else ""
                sname = row[1] if len(row) > 1 else ""
                y = ensure_space(y)
                pdf.set_xy(x, y)
                # pdf.cell(idx_w, line_height, text=str(i), border=1, align="C")
                pdf.cell(key_w, line_height, text=str(role_key), border=1, align="C")
                pdf.cell(name_w, line_height, text=str(sname), border=1)
                pdf.cell(val_w, line_height, text=str(coach_dict.get(role_key, "")), border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                y = pdf.get_y()
            i = len(staff_rows)
            y = ensure_space(y)
            pdf.set_xy(x, y)
            # pdf.cell(idx_w, line_height, text=str(i), border=1, align="C")
            pdf.cell(key_w, line_height, text="Yellow", border=1, align="C")
            pdf.cell(name_w, line_height, text="Team Yellow", border=1)
            pdf.cell(val_w, line_height, text=str(coach_dict.get("yellow", "")), border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            return pdf.get_y()

        coach_y = max(left_y, right_y)
        coach_y = ensure_space(coach_y)
        pdf.set_font("helvetica", style="B", size=9)
        pdf.set_xy(left_x, coach_y)
        pdf.cell(col_w, line_height, text="Coach", border=0)
        pdf.set_xy(right_x, coach_y)
        pdf.cell(col_w, line_height, text="Coach", border=0)
        table_y = coach_y + line_height

        table_y = ensure_space(table_y)
        left_bottom = draw_staff_coach_column(left_x, table_y, home_staff.get("home", []), home_coach)
        right_bottom = draw_staff_coach_column(right_x, table_y, away_staff.get("away", []), away_coach)
        pdf.set_y(max(left_bottom, right_bottom) + 2)

    write_two_column_teams()

    pdf.ln(2)
    write_line("Referees", bold=True)

    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    hat_w = 16
    club_w = 60
    exp_w = 25
    name_w = usable_w - (hat_w + club_w + exp_w)

    pdf.set_font("helvetica", style="B", size=10)
    pdf.cell(hat_w, line_height, text="Number", border=1)
    pdf.cell(name_w, line_height, text="Name", border=1)
    pdf.cell(club_w, line_height, text="Club", border=1)
    pdf.cell(exp_w, line_height, text="Expenses", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("helvetica", style="", size=10)
    for hat, name, club, expenses in ref_data.get("referee", []):
        pdf.cell(hat_w, line_height, text=str(hat), border=1)
        pdf.cell(name_w, line_height, text=str(name), border=1)
        pdf.cell(club_w, line_height, text=str(club), border=1)
        pdf.cell(exp_w, line_height, text=str(expenses), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


    pdf.ln(4)
    
    def write_breakdown_table() -> None:
        usable_w = pdf.w - pdf.l_margin - pdf.r_margin

        # Breakdown table
        pdf.set_font("helvetica", style="B", size=10)
        pdf.cell(0, line_height, text="Breakdown", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        team_w = 22
        event_w = 20
        per_w = (usable_w - team_w - event_w) / 4

        pdf.set_font("helvetica", style="B", size=9)
        pdf.cell(team_w, line_height, text="Team", border=1)
        pdf.cell(event_w, line_height, text="Event", border=1)
        pdf.cell(per_w, line_height, text="P1", border=1)
        pdf.cell(per_w, line_height, text="P2", border=1)
        pdf.cell(per_w, line_height, text="P3", border=1)
        pdf.cell(per_w, line_height, text="P4", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        def breakdown_row(team: str, event: str, p1, p2, p3, p4) -> None:
            pdf.set_font("helvetica", style="", size=9)
            pdf.cell(team_w, line_height, text=str(team), border=1)
            pdf.cell(event_w, line_height, text=str(event), border=1)
            pdf.cell(per_w, line_height, text=str(p1), border=1, align="C")
            pdf.cell(per_w, line_height, text=str(p2), border=1, align="C")
            pdf.cell(per_w, line_height, text=str(p3), border=1, align="C")
            pdf.cell(per_w, line_height, text=str(p4), border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        for team in periodscores:
            breakdown_row(
                team,
                "Goals",
                periodscores[team]["goals1"],
                periodscores[team]["goals2"],
                periodscores[team]["goals3"],
                periodscores[team]["goals4"],
            )

        for team in periodscores:
            breakdown_row(
                team,
                "Majors",
                periodscores[team]["majors1"],
                periodscores[team]["majors2"],
                periodscores[team]["majors3"],
                periodscores[team]["majors4"],
            )

        pdf.ln(5)

    # 1) In-memory arrays (always include)
    write_breakdown_table()

    # Game log table (running_file)
    pdf.ln(4)
    write_line("Game Log (running file)", bold=True)

    def fit_text(text: str, width: float) -> str:
        s = "" if text is None else str(text)
        if pdf.get_string_width(s) <= width:
            return s
        # Use plain ASCII for maximum compatibility with standard Helvetica fonts.
        ell = "..."
        if pdf.get_string_width(ell) > width:
            return ""
        # trim until it fits
        while s and pdf.get_string_width(s + ell) > width:
            s = s[:-1]
        return s + ell if s else ell

    def write_game_log_table(rows) -> None:
        usable_w2 = pdf.w - pdf.l_margin - pdf.r_margin
        # Use smaller font to fit many columns
        pdf.set_font("helvetica", style="", size=7)
        h = 4.5

        # Fixed widths; remainder goes to Name column
        w_q = 9
        w_m = 9
        w_s = 9
        w_hs = 13
        w_as = 13
        w_action = 18
        w_player = 10
        w_team = 12
        w_goals = 10
        w_majors = 12
        w_reds = 10
        w_name = usable_w2 - (w_q + w_m + w_s + w_hs + w_as + w_action + w_player + w_team + w_goals + w_majors + w_reds)
        if w_name < 22:
            # fall back: steal from action if needed
            steal = 22 - w_name
            w_action = max(10, w_action - steal)
            w_name = usable_w2 - (w_q + w_m + w_s + w_hs + w_as + w_action + w_player + w_team + w_goals + w_majors + w_reds)

        def header_row() -> None:
            pdf.set_font("helvetica", style="B", size=7)
            pdf.cell(w_q, h, text="Quar", border=1, align="C")
            pdf.cell(w_m, h, text="Min", border=1, align="C")
            pdf.cell(w_s, h, text="Sec", border=1, align="C")
            pdf.cell(w_hs, h, text="Home", border=1, align="C")
            pdf.cell(w_as, h, text="Away", border=1, align="C")
            pdf.cell(w_action, h, text="Action", border=1)
            pdf.cell(w_team, h, text="Team", border=1, align="C")
            pdf.cell(w_player, h, text="Hat", border=1, align="C")
            pdf.cell(w_name, h, text="Name", border=1)
            pdf.cell(w_goals, h, text="Goals", border=1, align="C")
            pdf.cell(w_majors, h, text="Majors", border=1, align="C")
            pdf.cell(w_reds, h, text="Card", border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("helvetica", style="", size=7)

        def ensure_table_space() -> None:
            if pdf.get_y() + (h * 2) > (pdf.h - pdf.b_margin):
                pdf.add_page()
                header_row()

        header_row()

        for row in rows:
            if not row:
                continue
            # Skip header lines if present in the file
            if row and str(row[0]).strip().lower() == "quarter":
                continue

            # Pad/truncate to expected 12 columns
            r = list(row)[:12]
            while len(r) < 12:
                r.append("")

            ensure_table_space()
            pdf.cell(w_q, h, text=fit_text(r[0], w_q), border=1, align="C")
            pdf.cell(w_m, h, text=fit_text(r[1], w_m), border=1, align="C")
            pdf.cell(w_s, h, text=fit_text(r[2], w_s), border=1, align="C")
            pdf.cell(w_hs, h, text=fit_text(r[3], w_hs), border=1, align="C")
            pdf.cell(w_as, h, text=fit_text(r[4], w_as), border=1, align="C")
            pdf.cell(w_action, h, text=fit_text(r[5], w_action), border=1)
            pdf.cell(w_team, h, text=fit_text(r[6], w_team), border=1)
            pdf.cell(w_player, h, text=fit_text(r[7], w_player), border=1, align="C")
            pdf.cell(w_name, h, text=fit_text(r[8], w_name), border=1)
            pdf.cell(w_goals, h, text=fit_text(r[9], w_goals), border=1, align="C")
            pdf.cell(w_majors, h, text=fit_text(r[10], w_majors), border=1, align="C")
            pdf.cell(w_reds, h, text=fit_text(r[11], w_reds), border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("helvetica", style="", size=10)

    if os.path.exists(running_file):
        with open(running_file, "r", encoding="utf-8", newline="") as f:
            write_game_log_table(csv.reader(f))
    else:
        write_line("(running_file not found; it may have been deleted at finish.)")

    # 2) CSV file rows (append if present)
    pdf.ln(4)
    # write_line(f"CSV Log: {compress_file}", bold=True)
    # if os.path.exists(compress_file):
    #     with open(compress_file, "r", encoding="utf-8", newline="") as f:
    #         csv_reader = csv.reader(f)
    #         for row in csv_reader:
    #             if row:
    #                 write_row(row)
    # else:
    #     write_line("(CSV file not found; only array data was exported.)")

    ensureResultsDirs()
    pdf_file_path = str(buildFinalPdfPath())
    pdf.output(pdf_file_path)
    return redirect(url_for('index'))


if __name__ == '__main__':
    config = load_scoreboard_config()
    listening_port = int(config.get("listening_port", Config.WEB_PORT))
    runtime_listening_port = listening_port
    browser_only = os.environ.get("SCOREBOARD_BROWSER_ONLY", "").lower() in ("1", "true", "yes")

    def run_flask():
        app.run(
            host=Config.WEB_HOST,
            port=listening_port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    if browser_only:
        app.run(
            host=Config.WEB_HOST,
            port=listening_port,
            debug=False,
            use_reloader=False,
        )
    else:
        threading.Thread(target=run_flask, daemon=True).start()
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{listening_port}/", timeout=0.25)
                break
            except OSError:
                time.sleep(0.05)

        import webview

        webview_window = webview.create_window("WaterPolo Scoreboard", f"http://127.0.0.1:{listening_port}")
        webview.start()
    


