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
- Export at game end:
  - CSV log file
  - PDF output created from the logged data (`/convert`)

## Tech Stack

- Flask (`start.py`)
- `pywebview` to show the UI as a desktop window
- `bleak` for Bluetooth (optional)
- `fpdf2` for PDF generation

## Requirements

Install dependencies with:

```bash
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Python packages are pinned in `requirements.txt`.

## Running

Start the app:

```bash
python start.py
```

The app launches a `pywebview` window and serves the Flask app.

## Docker

The scoreboard runs in Docker via `docker-compose.yaml`. The container uses **browser-only mode** (`SCOREBOARD_BROWSER_ONLY=true`): Flask serves the UI on port 5000 and there is no desktop `pywebview` window. Bluetooth is not available inside the container.

`docker-compose.yaml` defines one service (`scoreboard`):

- **Image / container name:** `waterpolo-scoreboard`
- **Port:** host `5000` → container `5000` (override with `SCOREBOARD_HOST_PORT`, e.g. `SCOREBOARD_HOST_PORT=10080`)
- **Volume:** `./results:/app/results` — match CSV logs and PDF exports persist on the host
- **Restart policy:** `unless-stopped`

Match exports land under `results/` on your machine (`results/temp/` for in-progress CSV logs, finished PDFs in `results/`).

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

Open the scoreboard at [http://localhost:5000](http://localhost:5000). From another device on the same network, use `http://<host-ip>:5000/controls` for the control view and `http://<host-ip>:5000/display` for the scoreboard display.

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
| `ard_ble_buzzer/`, `BLE_small_sample/` | Arduino / BLE firmware samples |

Things worth cleaning up locally:

1. **Root stray exports** — Move or delete `Kingston*`, `temp-*.csv`, and `*.bak` files in the repo root; keep exports under `results/` only.
2. **Duplicate virtual envs** — You likely only need one of `venv/` or `.venv/` (both are gitignored).
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

## Access controls and Display 
To open the display page either click on the display button in the app, or got direct to the broswer

`http://127.0.0.1:5000/display`

To run the controls on a mobile device as long as on the same network.

`http://<IP of the app machine>:5000/controls`