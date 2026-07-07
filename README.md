# WaterPoloScoreBoard

A local (Windows) water polo scoreboard app with a web UI rendered inside a desktop window (via `pywebview`). It tracks timer/quarters, scoring (goals/majors/reds), player names, referees, and exports match logs to a CSV + PDF.

Typical setup uses two screens:

- An external display (scoreboard view) that players/spectators can see as the game clock.
- A phone or tablet (control view) for score table staff to manage timer, scoring, majors, and game flow.

You can use a Huion K20 on the table for quick key presses.

![Screenshot of layout keys.](/huion_k20/huion_layout.png)

In the `huion_k20` folder you can find the key layout image and cfg.

## Features

- Web UI for scoreboard control (timer, quarters, shot clock, timeouts)
- Display page can be shown full-screen on an external monitor/TV as the visible game clock
- Controls page works well on a mobile device for table-side game management
- Player setup (home/away) + referee setup
- Bluetooth integration (optional) for controlling the hardware scoreboard buzzer
- USB serial relay (optional) — mirror BLE-style text commands to a COM port (e.g. LoRa master); configure **Serial port** on the settings page (`/setup`) or via `Config.SERIAL_PORT`
- Export at game end:
  - CSV log file
  - PDF output created from the logged data (`/convert`)

## Tech Stack

- Flask (`start.py`)
- `pywebview` to show the UI as a desktop window (local Windows runs)
- `bleak` for Bluetooth (optional)
- `pyserial` for USB serial relay to hardware (optional; e.g. LoRa master on COM port)
- `fpdf2` for PDF generation

## Requirements

- **Python 3.12+** (3.12 is what the Docker image uses)
- Windows for the full desktop experience (`pywebview` + BLE + serial COM ports)

Install dependencies into a single virtual environment. Use **one** env for the project — either `.venv` or `venv`, not both:

```powershell
# From the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Runtime packages are pinned in `requirements.txt`:

| Package | Purpose |
| --- | --- |
| `flask` | Web UI and HTTP API |
| `pywebview` | Native desktop window around the Flask UI |
| `bleak` | BLE buzzer / scoreboard devices (optional) |
| `pyserial` | USB serial relay (`import serial`; optional) |
| `fpdf2` | PDF export at end of match |

If you see `ModuleNotFoundError: No module named 'serial'`, install deps into the **same** interpreter you use to run `start.py` (the module comes from the `pyserial` package).

### Tests (optional)

For local development, install the combined dev dependencies file:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-development.txt
```

This includes `requirements.txt` plus test and packaging tools like `pytest`, `pyinstaller`, and `auto-py-to-exe`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/
```

## Running

Start the app (use your venv’s Python so imports match):

```powershell
.\.venv\Scripts\python.exe start.py
```

Or, with the venv activated:

```powershell
python start.py
```

The app launches a `pywebview` window and serves the Flask app on port **5000** by default (`Config.WEB_PORT`). Override with env var `SCOREBOARD_LISTENING_PORT` if needed.

## Docker

The scoreboard runs in Docker via `docker-compose.yaml`. The container uses **browser-only mode** (`SCOREBOARD_BROWSER_ONLY=true`): Flask serves the UI on port 5000 and there is no desktop `pywebview` window. Bluetooth and USB serial are not available inside the container.

Container Python deps are listed in `requirements-docker.txt` (copied into the image as `requirements.txt`). Local Windows installs use the root `requirements.txt`, which additionally includes `pywebview` and `pyserial`.

`docker-compose.yaml` defines one service (`scoreboard`):

- **Image / container name:** `waterpolo-scoreboard`
- **Port:** host `10080` → container `5000` (Flask listens on 5000 inside the container only; override the host side with `SCOREBOARD_HOST_PORT`)
- **Volume:** `./results:/app/results` — match CSV logs and PDF exports persist on the host
- **Restart policy:** `unless-stopped`

Match exports land under `results/` on your machine (`results/temp/` for in-progress CSV logs, finished PDFs in `results/`).

Port mapping uses `HOST:CONTAINER`. The app always listens on port **5000 inside the container**; by default only host port **10080** is published to your machine — port 5000 is not exposed on the host unless you set `SCOREBOARD_HOST_PORT=5000`.

Run all commands from the repo root (where `docker-compose.yaml` lives). Replace `docker` with `podman` if you use Podman.

### Build / rebuild image

First build, or after changing Python code, templates, static files, or `requirements-docker.txt`:

```bash
docker compose build --no-cache
```

Build and start in one step:

```bash
docker compose up -d --build
```

### Start container

```bash
docker compose up -d
```

### Restart after config / page changes

Quick restart (same image — fine for env-only tweaks):

```bash
docker compose restart
```

After changes to app code, templates, or static assets, rebuild the image and recreate the container:

```bash
docker compose up -d --build
```

### Stop container

```bash
docker compose down
```

### Useful commands

```bash
docker compose ps
docker compose logs -f scoreboard
```

Open the scoreboard at [http://localhost:10080](http://localhost:10080). From another device on the same network, use `http://<host-ip>:10080/controls` for the control view and `http://<host-ip>:10080/display` for the scoreboard display.

### Local overrides (`docker-compose.override.yaml`)

Docker Compose automatically merges `docker-compose.override.yaml` with `docker-compose.yaml` when you run `docker compose` commands. Use it for **machine-specific settings** that should not be committed to git.

`docker-compose.override.yaml` and `docker-compose.override.yml` are listed in `.gitignore`, so each developer or host can keep their own copy locally.

Create the file in the repo root (same folder as `docker-compose.yaml`). You only need to include the keys you want to change — Compose deep-merges them onto the base service definition.

**When to use an override file**

- Windows or Podman volume paths that do not work with `./results`
- A different host port without editing the shared compose file
- Extra environment variables for one machine
- Local debugging (e.g. bind-mounting source for live edits — not recommended for production)

**Example — Windows results path**

If `./results:/app/results` fails on Windows PowerShell, create `docker-compose.override.yaml`:

```yaml
services:
  scoreboard:
    volumes:
      - ${PWD}/results:/app/results
```

Or use a fixed absolute path:

```yaml
services:
  scoreboard:
    volumes:
      - C:/Users/you/WaterPoloScoreBoard/results:/app/results
```

Use forward slashes in Windows paths inside the YAML.

**Example — custom host port**

Change the published port without touching `docker-compose.yaml`:

```yaml
services:
  scoreboard:
    ports:
      - "10080:5000"
```

Alternatively, set an env var when starting (no override file needed):

```powershell
$env:SCOREBOARD_HOST_PORT = "10080"
docker compose up -d
```

**Example — combine overrides**

```yaml
services:
  scoreboard:
    ports:
      - "10080:5000"
    volumes:
      - ${PWD}/results:/app/results
    environment:
      SCOREBOARD_LISTENING_PORT: "5000"
```

After creating or editing the override file, recreate the container so mounts and ports apply:

```bash
docker compose up -d
```

To confirm the merged config:

```bash
docker compose config
```

## Build (optional)

If you want an EXE, you can use `pyinstaller` or `auto-py-to-exe`.
See `Notes.txt` for your current workflow.

## Project layout and cleanup

Suggested layout (core app):

| Path | Purpose |
| --- | --- |
| `start.py`, `BLE.py` | Application code |
| `templates/`, `static/` | Web UI |
| `tests/` | Pytest suite |
| `results/` | Match CSV/PDF exports (runtime data; gitignored) |
| `docker-compose.yaml`, `Dockerfile` | Container deployment |

Optional / hardware-related folders:

| Path | Purpose |
| --- | --- |
| `huion_k20/` | Huion K20 keypad layout and config |
| `ard_ble_buzzer/`, `BLE_small_sample/` | Arduino / BLE / LoRa firmware samples (`BLE_small_sample/lora_setup_notes.md`) |

Things worth cleaning up locally:

1. **Root stray exports** — Move or delete `Kingston*`, `temp-*.csv`, and `*.bak` files in the repo root; keep exports under `results/` only.
2. **Duplicate virtual envs** — Pick one of `venv/` or `.venv/` and install `requirements.txt` into it (both are gitignored). The README examples use `.venv`.
3. **PyInstaller output** — `build/`, `dist/`, and `output/` are build artifacts. Prefer a single release folder (e.g. `dist/`) and publish EXEs via GitHub Releases instead of committing large binaries in `output/`.
4. **Personal build configs** — `WaterPoloPytoExe_personal.json` and `Notes.txt` are machine-specific; keep them local or under a `build/` folder rather than in the repo root.
5. **Backup files** — Remove `README.md.bak` and similar `.bak` files once you no longer need them.
6. **Firmware grouping (optional)** — Consider moving `ard_ble_buzzer/` and `BLE_small_sample/` under a single `firmware/` parent to keep the root tidy.

## Function / Route Examples

`start.py` exposes multiple Flask routes. The most relevant ones are:

### Start/Stop timer controls (examples)

- `GET /start_countdown`
- `GET /stop_countdown`
- `GET /pause_countdown`
- `GET /resume_countdown`

Example (from a browser):

`http://127.0.0.1:5000/start_countdown`

### Update scoring / events (examples)

Routes are used by the UI buttons, for example:

- `POST /updateteamagoal/<string:direction>/<int:user_id>`
- `POST /updateteamamajor/<string:direction>/<int:user_id>`
- `POST /updateteamapenalty/<string:direction>/<int:user_id>`

### Serial relay (optional)

When a USB serial device is configured (`Config.SERIAL_PORT` on the settings page), scoreboard commands are mirrored over the COM port as newline-delimited text — the same payloads used for BLE (`TEST`, `BUZZER`, integers, etc.). Useful for a LoRa master or other wired relay. Leave the port empty to disable serial output.

Connection status appears on the setup page alongside BLE device flags (`get_device_connection_flags()`).

### Bluetooth (BLE) controls

The app can drive a hardware scoreboard buzzer over BLE (via `bleak`). Devices
to connect to are configured through `Config.BLUETOOTH_NAME`. Three Flask
routes wrap three async helpers in `start.py`:

- `GET/POST /connectble` -> `init_ble()` (the "connect" action)
  - Scans for every configured BLE device and connects to each one.
  - Idempotent: if a device is already connected, the existing connection is
    reused instead of being dropped and reopened. Clicking Connect twice is
    safe.
  - Sends a `TEST` command after connecting so you see feedback on the device.
  - Returns JSON when called from the setup page (so the spinner works); a
    plain browser GET still redirects to the index.

- `GET/POST /reconnectble` -> `reconnect_ble()` (the "reconnect" action)
  - Only touches slots that currently report as disconnected; healthy
    connections are left alone.
  - Pass 1: tries to reconnect by the last-known address.
  - Pass 2: if that fails (for example because the device was power-cycled
    and came back with a slightly different address), it rescans and matches
    by device name.
  - If nothing is known yet, it falls back to a fresh `init_ble()`.
  - Use this after a device goes to sleep / loses power rather than fully
    disconnecting first.

- `GET/POST /disconnectble` -> `dis_ble()` (the "disconnect" action)
  - Sends an `exit` command, sets `BLUETOOTH_CONNECT = 0` (so the watchdog
    goes idle), then cleanly disconnects every known BLE client and clears
    `ble_clients` / `ble_client_names` / `ble_client_addresses`.
  - Redirects back to the settings page.

All three run on a single persistent BLE event loop and are serialised by an
internal lock (`_ble_op_lock`), so rapid double-clicks on Connect / Reconnect
/ Disconnect cannot corrupt the client list.

### Export at end of match

When you finish the game, the UI typically calls:

- `GET/POST /finish`

`/finish` writes the CSV log and also produces `running_file` and `compress_file` names used for export.

After that, generate the PDF:

- `GET /convert`

### PDF generation example

Once the match log CSV exists, opening:

`http://127.0.0.1:5000/convert`

creates a PDF in `results/` with a name derived from the match, for example:

- `results/<home team> vs <away team>_END_-YYYY-MM-DD-HH-MM.pdf`

## File Outputs

Exports depend on `Config.DEFAULT_HOME_TEAM` and `Config.DEFAULT_AWAY_TEAM`:

- Temp/working CSV logs: `results/temp/` (for example `temp-YYYY-MM-DD-HH-MM.csv` and per-game CSV files)
- Final PDF: `results/<home team> vs <away team>_END_-YYYY-MM-DD-HH-MM.pdf`

## Customization Notes

- PDF layout is controlled in `convert_csv_to_pdf()` in `start.py`.
- Team, referee, and per-player stats are sourced from in-memory arrays (`home_data`, `away_data`, `ref_data`) and the generated CSV logs (`compress_file`, `running_file`).

## Access controls and display

Open the display page from the app, or go directly in a browser:

`http://127.0.0.1:5000/display`

For table-side controls on a phone or tablet on the same LAN:

`http://<IP of the app machine>:5000/controls`

The setup page shows the detected LAN IPv4 when available (`/setup`).