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

The Docker image runs the scoreboard in **browser-only mode** (`SCOREBOARD_BROWSER_ONLY=true`): Flask serves the UI on port 5000 and there is no desktop `pywebview` window. Bluetooth is not available inside the container.

Match logs and PDFs are written under `/app/results` in the container. Mount a local folder there so exports persist on your machine.

### Build the image

Docker:

```bash
docker build -t waterpolo-scoreboard .
```

Podman:

```bash
podman build -t waterpolo-scoreboard .
```

### Run the container

Bind port 5000 and mount a local `results` folder (creates `results/temp/` for in-progress CSV logs and stores finished PDFs in `results/`):

Docker:

```bash
docker run --rm -p 5000:5000 -v ./results:/app/results waterpolo-scoreboard
```

Podman:

```bash
podman run --rm -p 5000:5000 -v ./results:/app/results waterpolo-scoreboard
```

On Windows PowerShell, use an absolute path for the volume if `./results` does not resolve as expected, for example:

```powershell
docker run --rm -p 5000:5000 -v ${PWD}/results:/app/results waterpolo-scoreboard
```

Open the scoreboard in your browser at [http://localhost:5000](http://localhost:5000). From another device on the same network, use `http://<host-ip>:5000/controls` for the control view and `http://<host-ip>:5000/display` for the scoreboard display.

The Dockerfile declares `VOLUME ["/app/results"]`; if you omit `-v`, Docker or Podman still creates an anonymous volume, but binding `./results` is recommended so you can open exported files directly.

## Build (optional)

If you want an EXE, you can use `pyinstaller` or `auto-py-to-exe`.
See `Notes.txt` for your current workflow.

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