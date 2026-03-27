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

### Export at end of match

When you finish the game, the UI typically calls:

- `GET/POST /finish`

`/finish` writes the CSV log and also produces `running_file` and `compress_file` names used for export.

After that, generate the PDF:

- `GET /convert`

### PDF generation example

Once the match log CSV exists, opening:

`http://127.0.0.1:5000/convert`

creates:

- `<home team> vs <away team>_END_-YYYY-MM-DD-HH-MM.csv` -> PDF with the same base name (`.pdf`)

## File Outputs

Exports depend on `Config.DEFAULT_HOME_TEAM` and `Config.DEFAULT_AWAY_TEAM`, for example:

- CSV: `..._END_-YYYY-MM-DD-HH-MM.csv`
- PDF: same name with `.pdf`

## Customization Notes

- PDF layout is controlled in `convert_csv_to_pdf()` in `start.py`.
- Team, referee, and per-player stats are sourced from in-memory arrays (`home_data`, `away_data`, `ref_data`) and the generated CSV logs (`compress_file`, `running_file`).

## Access controls and Display 
To open the display page either click on the display button in the app, or got direct to the broswer

`http://127.0.0.1:5000/display`

To run the controls on a mobile device as long as on the same network.

`http://<IP of the app machine>:5000/controls`