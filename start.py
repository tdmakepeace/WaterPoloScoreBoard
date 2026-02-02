import errno
from time import sleep
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
# from quart import Quart , render_template, request, redirect, url_for, jsonify, flash
import time
import csv
import math
import os
import webview
from datetime import datetime, timedelta
from fpdf import FPDF
from fpdf.enums import XPos, YPos

## Bluetooth ##
from bleak import BleakClient, BleakScanner , BleakError
import asyncio


# Instead of nested dictionaries, use dataclasses
from dataclasses import dataclass

@dataclass
class PlayerStats:
    """Statistics for a single player."""
    assists: int = 0
    goals: int = 0
    majors: int = 0
    reds: int = 0

@dataclass
class PeriodScores:
    """Period-by-period scoring."""
    goals1: int = 0
    majors1: int = 0
    goals2: int = 0
    majors2: int = 0
    goals3: int = 0
    majors3: int = 0
    goals4: int = 0
    majors4: int = 0

# Initialize teams
teama = {i: PlayerStats() for i in range(1, 15)}
teamb = {i: PlayerStats() for i in range(1, 15)}

periodscores = { 'Home': PeriodScores() ,     'Away': PeriodScores() }

# Group related constants at the top
class Config:
    """Application configuration constants."""
    WEB_TIMEOUT = 180
    WEB_HOST = '0.0.0.0'
    WEB_PORT = 5000
    SESSION_TYPE = 'filesystem'
    SECRET_KEY = 'waterpolo'
    
    # Game settings
    # All time is based on 30 second increments
    INTERVAL_TIME = 4
    HALFTIME = 4
    TIMEOUT_TIME = 2
    GAME_TIME = 13
    SHOT_CLOCK = 28
    FOUL_CLOCK = SHOT_CLOCK -10
    BLUETOOTH_CONNECT = 0
    MAJORS = 9

    
    # Bluetooth constants
    UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
    RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
    TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
    BLUETOOTH_NAME = ["Nano33BLE" , "WaterPolo_1" , "WaterPolo_2"]
    
    # Default values
    DEFAULT_LOCATION = 'New Malden'
    DEFAULT_HOME_TEAM = 'Kingston Royals'
    DEFAULT_AWAY_TEAM = 'Away Team'

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

# REFEREE NAME AND EXPENCES
ref_data = {'referee': [['1', '','',''], ['2', '','','']]}

# CARDS
home_coach = {'red': 0 , 'yellow': 0}
away_coach = {'red': 0 , 'yellow': 0}

home_team_red = {'red': 0 , 'yellow': 0}
away_team_red = {'red': 0 , 'yellow': 0}

runningclock = "no"


filename = datetime.now().strftime(Config.DEFAULT_HOME_TEAM + ' vs ' + Config.DEFAULT_AWAY_TEAM + '-%Y-%m-%d-%H-%M.csv')
filenamebak = filename + '.bak'
running_file = datetime.now().strftime('temp' + '-%Y-%m-%d-%H-%M.csv')
compress_file = datetime.now().strftime(Config.DEFAULT_HOME_TEAM + ' vs ' + Config.DEFAULT_AWAY_TEAM + '_END_' + '-%Y-%m-%d-%H-%M.csv')
countdown_running = False
quarter= 0
direction = "increment"
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
timeout = Config.TIMEOUT_TIME
BLUETOOTH_CONNECT = Config.BLUETOOTH_CONNECT
window = webview.create_window('WaterPolo Scoreboard', app)


## Bluetooth code block ##
ble_client = None  # global client
ble_clients = []
# async def init_ble():
#     global ble_client
#     devices = await BleakScanner.discover()
#     for d in devices:
#         print(f"Name: {d.name}, Address: {d.address}")
#     nano = next((d for d in devices if d.name and Config.BLUETOOTH_NAME in d.name), None)
#     if not nano:
#         print(f"{Config.BLUETOOTH_NAME} not found.")
#         return
#
#     ble_client = BleakClient(nano.address)
#     await ble_client.connect()
#     print(f"Connected to {nano.name} at {nano.address}")


async def init_ble():
    global ble_clients
    devices = await BleakScanner.discover(timeout=5.0)
    targets = [
        d for d in devices if d.name and any(name in d.name for name in Config.BLUETOOTH_NAME)
    ]

    if not targets:
        print(f"None of {Config.BLUETOOTH_NAME} found.")
        return

    ble_clients = []  # reset before reconnecting
    for d in targets:
        client = BleakClient(d.address)
        await client.connect()
        print(f"Connected to {d.name} at {d.address}")
        ble_clients.append(client)
    # print(ble_clients)
    return ble_clients   # now returns the actual list


# async def dis_ble():
#     global ble_client
#     await ble_client.disconnect()
#     print(f"Disconnected bluetooth")

async def dis_ble():
    global ble_clients
    for client in ble_clients:
        # print(client)
        try:
            if client.is_connected:
                await client.disconnect()
                print(f"Disconnected safely from {client.address}")
            else:
                print(f"Already disconnected from {client.address}, skipping.")
        except BleakError as e:
            print(f"Error during disconnect from {client.address}: {e}")
        except Exception as e:
            print(f"Unexpected error with {client.address}: {e}")

    # Clear the list once all are disconnected
    ble_clients = []
    return ble_clients


# async def send_ble_command(command: str):
#     global ble_client
#     if Config.BLUETOOTH_CONNECT == 1:
#         if ble_client and ble_client.is_connected:
#             command = command + "\0"
#             await ble_client.write_gatt_char(Config.RX_CHAR_UUID, command.encode())
#
#
#
# async def send_ble_int(value: str):
#     global ble_client
#     if Config.BLUETOOTH_CONNECT == 1:
#         if ble_client and ble_client.is_connected:
#             command = str(value) + "\0"
#             await ble_client.write_gatt_char(Config.RX_CHAR_UUID, command.encode('utf-8'))


# async def send_ble_command(command: str):
#     global ble_clients
#     for client in ble_clients:
#         if client and client.is_connected:
#             try:
#                 cmd = command + "\0"
#                 await client.write_gatt_char(Config.RX_CHAR_UUID, cmd.encode('utf-8'))
#                 # print(f"Sent command '{command}' to {client.address}")
#             except Exception as e:
#                 print(f"Error sending command to {client.address}: {e}")

async def send_ble_command(command: str):
    global ble_clients
    for client in ble_clients:
        if client and client.is_connected:
            try:
                cmd = command + "\0"
                await client.write_gatt_char(Config.RX_CHAR_UUID, cmd.encode("utf-8"))
                # print(f"Sent command '{command}' to {client.address}")
            except Exception as e:
                # Log the error with more context
                print(f"[ERROR] Failed to send '{command}' to {client.address}: {e}")
                # Optionally: disconnect or remove the client if it's broken
                try:
                    await client.disconnect()
                except Exception:
                    pass

async def send_ble_int(value: str):
    global ble_clients

    for client in ble_clients:
        if client and client.is_connected:
            try:
                cmd = str(value) + "\0"
                await client.write_gatt_char(Config.RX_CHAR_UUID, cmd.encode('utf-8'))
                # print(f"Sent int '{value}' to {client.address}")
            except Exception as e:
                print(f"Error sending int to {client.address}: {e}")
                try:
                    await client.disconnect()
                except Exception:
                    pass

@app.route('/changeposs')
def changeposs():
    command = "CHANGE"
    asyncio.run(send_ble_command(command))
    return jsonify({'status': 'success'})


@app.route('/periodend')
def periodend():
    command = "END"
    asyncio.run(send_ble_command(command))
    return jsonify({'status': 'success'})


@app.route('/buzzer')
def buzzer():
    command = "BUZZER"
    asyncio.run(send_ble_command(command))
    return jsonify({'status': 'success'})

# @app.route('/displayshotclock/<int:shot>')
# def displayshotclock(shot):
#     command = shot
#     # print(f"Sent command to int: {command}")
#     asyncio.run(send_ble_int(command))
#     return jsonify({'status': 'success'})

@app.route('/displayshotclock/<int:shot>')
def displayshotclock(shot):
    command = shot
    try:
        asyncio.run(send_ble_int(command))
        return jsonify({'status': 'success'})
    except Exception as e:
        # Log the error and return a controlled response
        print(f"Error in displayshotclock route: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
## end of Bluetooth code block



@app.route('/')
def index():
    return render_template('timer.html', scores=scores, teama=teama, teamb=teamb,
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION,
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)

@app.route('/display')
def display():
    return render_template('display.html', scores=scores, teama=teama, teamb=teamb, 
                           elapsed_shot=elapsed_shot, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway,
                           periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM,
                           AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, 
                           hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, filename=filename,
                           home_coach=home_team_red, away_coach=away_team_red)



# CLOCK CONTROLS
@app.route('/start_countdown')
def start_countdown():
    global countdown_running, start_time, elapsed_time, start_shot, elapsed_shot
    countdown_running = True
    start_time = time.time() - elapsed_time
    start_shot = time.time() - elapsed_shot
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
    return jsonify({'status': 'success'})


@app.route('/get_countdown_status')
def get_countdown_status():
    global countdown_running, start_time, elapsed_time, remaining_time , start_shot, elapsed_shot , remaining_shot , clock_shot
    if countdown_running:
        elapsed_time = time.time() - start_time
        remaining_time = max((Config.GAME_TIME*30) - elapsed_time, 0)
        elapsed_shot = time.time() - start_shot
        remaining_shot = max((clock_shot) - elapsed_shot, 0 )
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time, 'elapsed_shot': remaining_shot })
    else:
        # return jsonify({'countdown_running': countdown_running, 'elapsed_time': elapsed_time})
        # elapsed_time = time.time() - start_time
        remaining_time = max((Config.GAME_TIME*30) - elapsed_time, 0)
        # elapsed_shot = time.time() - start_shot
        remaining_shot = max((clock_shot) - elapsed_shot, 0 )
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time, 'elapsed_shot': remaining_shot })


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
    asyncio.run(send_ble_int(command))

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
    asyncio.run(send_ble_int(command))

    return jsonify({'status': 'success'})


@app.route('/reset20')
def reset20():
    global countdown_running, start_time, elapsed_time, remaining_time , start_shot, elapsed_shot , remaining_shot, clock_shot
    if countdown_running:
        pause_countdown()
        if remaining_shot < 20:
            clock_shot = max((Config.FOUL_CLOCK),0)+1
            remaining_shot = max((clock_shot) , 0)
            elapsed_shot = 0
            start_shot = 0
        start_countdown()
    else:
        if remaining_shot < 20:
            clock_shot = max((Config.FOUL_CLOCK),0)+1
            remaining_shot = max((clock_shot) , 0)
            elapsed_shot = 0
            start_shot = 0
        start_countdown()
    command = str(remaining_shot-1)
    # print(f"Sent command to int: {command}")
    asyncio.run(send_ble_int(command))
    return jsonify({'status': 'success'})

@app.route('/pause20')
def pause20():
    global countdown_running, start_time, elapsed_time, remaining_time , start_shot, elapsed_shot , remaining_shot, clock_shot
    if countdown_running:
        pause_countdown()
        if remaining_shot < 20:
            clock_shot = max((Config.FOUL_CLOCK),0)
            remaining_shot = max((clock_shot) , 0)
            elapsed_shot = 0
            start_shot = 0
    else:
        if remaining_shot < 20:
            clock_shot = max((Config.FOUL_CLOCK),0)
            remaining_shot = max((clock_shot) , 0)
            elapsed_shot = 0
            start_shot = 0
    command = str(remaining_shot)
    # print(f"Sent command to int: {command}")
    asyncio.run(send_ble_int(command))
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
    asyncio.run(send_ble_int(command))
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
    asyncio.run(send_ble_int(command))
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

@app.route('/homecard')
def homecard():
    if quarter == 0 :
        return redirect(url_for('index'))
    if countdown_running:
        if runningclock == "no":
            pause_countdown()
    else:
        msg = 'clock not running'
        flash(msg, "warning")

    return render_template('homecard.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=Config.DEFAULT_HOME_TEAM, AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)

@app.route('/awaycard')
def awaycard():
    if quarter == 0 :
        return redirect(url_for('index'))
    if countdown_running:
        if runningclock == "no":
            pause_countdown()
    else:
        msg = 'clock not running'
        flash(msg, "warning")

    return render_template('awaycard.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=Config.DEFAULT_HOME_TEAM, AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)


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
    return render_template('goal.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=Config.DEFAULT_HOME_TEAM, AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)

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
    return render_template('goalint.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=Config.DEFAULT_HOME_TEAM, AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)




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

    return render_template('major.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=Config.DEFAULT_HOME_TEAM, AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)

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

    return render_template('penalty.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=Config.DEFAULT_HOME_TEAM, AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)


@app.route('/updateteamacoach/<int:id>', methods=['GET', 'POST'])
def updateteamacoach(id):
    global quarter, direction
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
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'YELLOW', 'Coach','', 'Home']
                writer.writerow(data)


            elif id == 2 :
                home_coach['red'] = 1
                home_team_red['red'] = home_team_red['red'] + 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED', 'Coach','', 'Home']
                writer.writerow(data)

        elif direction == 'decrement':
            if id == 1 :
                home_coach['yellow'] = 0
                home_team_red['yellow'] = home_team_red['yellow'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL CARD', 'Coach','', 'Home']
                writer.writerow(data)
            elif id == 2 :
                home_coach['red'] = 0
                home_team_red['red'] = home_team_red['red'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL CARD', 'Coach','', 'Home']
                writer.writerow(data)
            direction = "increment"

        f.close()

    return redirect(url_for('index'))

@app.route('/updateteambcoach/<int:id>', methods=['GET', 'POST'])
def updateteambcoach(id):
    global quarter, direction
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
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'YELLOW', 'Coach','', 'Away']
                writer.writerow(data)

            elif id == 2 :
                away_coach['red'] = 1
                away_team_red['red'] = away_team_red['red'] + 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED', 'Coach','', 'Away']
                writer.writerow(data)

        elif direction == 'decrement':
            if id == 1 :
                away_coach['yellow'] = 0
                away_team_red['yellow'] = away_team_red['yellow'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL CARD', 'Coach','', 'Away']
                writer.writerow(data)
            elif id == 2 :
                away_coach['red'] = 0
                away_team_red['red'] = away_team_red['red'] - 1
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL CARD', 'Coach','', 'Away']
                writer.writerow(data)
            direction = "increment"

        f.close()

    return redirect(url_for('index'))



@app.route('/updateteamacard/<int:user_id>', methods=['GET', 'POST'])
def updateteamacard(user_id):
    global quarter, direction
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
            teama[user_id]['reds'] = teama[user_id]['reds'] + 1
            home_team_red['red'] = home_team_red['red']  + 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED', user_id, home_data['home'][user_id - 1][1], 'Home',
                    teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            teama[user_id]['reds'] = teama[user_id]['reds'] - 1
            home_team_red['red'] = home_team_red['red'] - 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED', user_id, home_data['home'][user_id - 1][1], 'Home',
                    teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
            writer.writerow(data)

            direction = "increment"
        f.close()

    return redirect(url_for('index'))

@app.route('/updateteambcard/<int:user_id>', methods=['GET', 'POST'])
def updateteambcard(user_id):
    global quarter, direction
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
            teamb[user_id]['reds'] = teamb[user_id]['reds'] + 1
            away_team_red['red'] = away_team_red['red'] + 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'RED', user_id, away_data['away'][user_id - 1][1], 'Away',
                    teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
            writer.writerow(data)
        elif direction == 'decrement':
            teamb[user_id]['red'] = teamb[user_id]['reds'] - 1
            away_team_red['red'] = away_team_red['red'] - 1
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'CANCEL RED', user_id, away_data['away'][user_id - 1][1], 'Away',
                    teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
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
        data = [ quarter , x[1],x[2], scores['Home']['goals'] , scores['Away']['goals'] , 'Goal' , user_id , home_data['home'][user_id - 1][1], 'Home', teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds'] ]
        writer.writerow(data)
        f.close()


    return redirect(url_for('index'))

@app.route('/updateteamintagoal/<int:user_id>', methods=['GET', 'POST'])
def updateteamintagoal(user_id):
    global quarter, direction
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
        data = [ quarter , x[1],x[2], scores['Home']['goals'] , scores['Away']['goals'] , 'Goal' , user_id , home_data['home'][user_id - 1][1], 'Home', teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds'] ]
        writer.writerow(data)
        f.close()

    # callintervalgoal
    return redirect(url_for('runintervalgoal'))
    # return redirect(url_for('interval'))

@app.route('/updateteamamajor/<int:user_id>', methods=['GET', 'POST'])
def updateteamamajor(user_id):
    global quarter
    global direction
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
        data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Majors', user_id, home_data['home'][user_id - 1][1], 'Home', teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
        writer.writerow(data)
        f.close()

    return redirect(url_for('index'))


@app.route('/updateteamapenalty/<int:user_id>', methods=['GET', 'POST'])
def updateteamapenalty(user_id):
    global quarter
    global direction
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
        data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Penalty', user_id, home_data['home'][user_id - 1][1], 'Home',
                teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['reds']]
        writer.writerow(data)
        f.close()

    return redirect(url_for('index'))

@app.route('/updateteambgoal/<int:user_id>', methods=['GET', 'POST'])
def updateteambgoal(user_id):
    global quarter
    global direction
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
        data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Goal', user_id, away_data['away'][user_id - 1][1], 'Away',
        teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
        writer.writerow(data)
        f.close()

    return redirect(url_for('index'))

@app.route('/updateteamintbgoal/<int:user_id>', methods=['GET', 'POST'])
def updateteamintbgoal(user_id):
    global quarter
    global direction
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
        data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Goal', user_id, away_data['away'][user_id - 1][1], 'Away',
        teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
        writer.writerow(data)
        f.close()

    return redirect(url_for('runintervalgoal'))


@app.route('/updateteambmajor/<int:user_id>', methods=['GET', 'POST'])
def updateteambmajor(user_id):
    global quarter
    global direction
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
        data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Major', user_id, away_data['away'][user_id - 1][1], 'Away',
        teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
        writer.writerow(data)
        f.close()

    return redirect(url_for('index'))

@app.route('/updateteambpenalty/<int:user_id>', methods=['GET', 'POST'])
def updateteambpenalty(user_id):
    global quarter
    global direction
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
        data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Penalty', user_id, away_data['away'][user_id - 1][1], 'Away',
        teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['reds']]
        writer.writerow(data)
        f.close()

    return redirect(url_for('index'))



@app.route('/period', methods=['GET', 'POST'])
def period():
    if request.method == 'POST':
        global quarter, direction
        if direction == 'increment':
            quarter = quarter + 1
            timestamp = datetime.now()

            f = open(running_file, 'a')
            writer = csv.writer(f)
            header = ['Game Status at ', Config.DEFAULT_LOCATION, ' on the ', timestamp, 'end of quarter :' ,quarter -1, ]
            writer.writerow(header)

            # header1 = ['HomeScore', 'AwayScore', 'HomeMajors', 'AwayMajors']
            # writer.writerow(header1)

            data = ['Home score:', scores['Home']['goals'], 'Away score :', scores['Away']['goals'],'Home Majors:',  scores['Home']['majors'], 'Away Majors :', scores['Away']['majors']]
            writer.writerow(data)

            header = ['Quarter', 'Min', 'Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'name', 'team', 'goals', 'majors', 'reds']
            writer.writerow(header)

            f.close()
        elif direction == 'decrement':
            quarter = quarter - 1
            timestamp = datetime.now()

            f = open(running_file, 'a')
            writer = csv.writer(f)
            header = ['Game Status at ', Config.DEFAULT_LOCATION, ' on the ', timestamp, 'end of quarter :' ,quarter -1, ]
            writer.writerow(header)

            # header1 = ['HomeScore', 'AwayScore', 'HomeMajors', 'AwayMajors']
            # writer.writerow(header1)

            data = ['Home score:', scores['Home']['goals'], 'Away score :', scores['Away']['goals'],'Home Majors:',  scores['Home']['majors'], 'Away Majors :', scores['Away']['majors']]
            writer.writerow(data)

            header = ['Quarter', 'Min', 'Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'name', 'team', 'goals', 'majors', 'reds']
            writer.writerow(header)

            f.close()
            direction = "increment"

    return redirect(url_for('index'))

@app.route('/clear', methods=['GET', 'POST'])
def direction():
    global direction
    direction = "decrement"
    return redirect(url_for('index'))

@app.route('/connectble', methods=['GET', 'POST'])
def connectble():
    global BLUETOOTH_CONNECT
    asyncio.run(init_ble())
    sleep(1)
    asyncio.run(send_ble_command("TEST"))
    BLUETOOTH_CONNECT = 1
    return redirect(url_for('index'))


@app.route('/disconnectble', methods=['GET', 'POST'])
def disconnectble():
    global BLUETOOTH_CONNECT
    asyncio.run(send_ble_command("exit"))
    BLUETOOTH_CONNECT = 0
    asyncio.run(dis_ble())
    return redirect(url_for('index'))

@app.route('/start', methods=['GET', 'POST'])
def start():
    global quarter, scores, TeamHome, TeamAway, periodscores, teama, teamb
    global direction, hometimeoutv, awaytimeoutv, filename
    if request.method == 'POST':


        asyncio.run(send_ble_command("TEST"))

        filename = datetime.now().strftime(
            Config.DEFAULT_HOME_TEAM + ' vs ' + Config.DEFAULT_AWAY_TEAM + '-%Y-%m-%d-%H-%M.csv')
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

        # timestamp = datetime.now()
        command = str(0)
        # print(f"Sent command to int: {command}")
        asyncio.run(send_ble_int(command))
        asyncio.run(send_ble_command("exit"))
        now = datetime.now()  # current date and time
        timestamp = now.strftime("%d/%m/%Y, %H:%M:%S")

        f = open(filename, 'a')
        writer = csv.writer(f)
        header = ['Game Over at ', Config.DEFAULT_LOCATION, ' on the ', timestamp]
        writer.writerow(header)
        header = ['Home: ', scores['Home']['goals'] , 'Away :' , scores['Away']['goals']]
        writer.writerow(header)

        header = ['breakdown']
        writer.writerow(header)
        header = ['Team','Event','P1','P2','P3','P4']
        writer.writerow(header)

        for team in periodscores:
            data = [team , 'Goals', periodscores[team]['goals1'], periodscores[team]['goals2'], periodscores[team]['goals3'], periodscores[team]['goals4']]
            writer.writerow(data)
        for team in periodscores:
            data = [team , 'Majors', periodscores[team]['majors1'], periodscores[team]['majors2'], periodscores[team]['majors3'], periodscores[team]['majors4']]
            writer.writerow(data)

        header2 = ['Home Team: ', Config.DEFAULT_HOME_TEAM ]
        writer.writerow(header2)
        header2 = ['Home Player','name', 'goals', 'majors', 'reds']

        writer.writerow(header2)
        for user_id in teama:

            data = [user_id ,home_data['home'][user_id-1][1], teama[user_id]['goals'],teama[user_id]['majors'],teama[user_id]['reds'] ]
            writer.writerow(data)


        header2 = ['Away Team: ', Config.DEFAULT_AWAY_TEAM ]
        writer.writerow(header2)
        header2 = ['Away Player','name', 'goals', 'majors', 'reds']
        writer.writerow(header2)
        for user_id in teamb:
            data = [user_id ,away_data['away'][user_id-1][1], teamb[user_id]['goals'],teamb[user_id]['majors'],teamb[user_id]['reds'] ]
            writer.writerow(data)

        header2 = ['Referees: ' ]
        writer.writerow(header2)
        header2 = ['Hatnumber','Name', 'Club', 'Expences']
        writer.writerow(header2)
        for i in ref_data['referee'] :
            data = i[0],i[1],i[2],i[3]
            writer.writerow(data)

        header = ['Quarter', 'Min', 'Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'name', 'team', 'goals',
                  'majors', 'reds']
        writer.writerow(header)

        f.close()

        try:
            with open(running_file, newline='') as in_file:
                with open(filename, 'a', newline='') as out_file:
                    writer = csv.writer(out_file)
                    for row in csv.reader(in_file):
                        if row:
                            writer.writerow(row)
            f.close()
        except :
            print('finish')
        try:
            with open(filename, newline='') as in_file:
                with open(compress_file, 'w', newline='') as out_file:
                    writer = csv.writer(out_file)
                    for row in csv.reader(in_file):
                        if row:
                            writer.writerow(row)
            f.close()
        except :
            print('finish')

        try:
            os.remove(running_file)
        except OSError as e:  # this would be "except OSError, e:" before Python 2.6
            if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
                raise  # re-raise exception if a different error occurred...

        try:
            os.remove(filename)
        except OSError as e:  # this would be "except OSError, e:" before Python 2.6
            if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
                raise  # re-raise exception if a different error occurred...

    return redirect(url_for('convert_csv_to_pdf'))


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
            # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout',
            hometimeoutv, 'Home']
            writer.writerow(data)
            f.close()
            # pause_countdown()
            time.sleep(1)
            start_timeout()
            return redirect(url_for('timeout'))

        elif direction == 'decrement':
            hometimeoutv = int(hometimeoutv) - 1
            # print(hometimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout removed',
            hometimeoutv, 'Home']
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
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout',
            hometimeoutv, 'Home']
            writer.writerow(data)
            f.close()
            # pause_countdown()
            time.sleep(1)
            start_timeout()
            return redirect(url_for('timeout'))

        elif direction == 'decrement':
            hometimeoutv = int(hometimeoutv) - 1
            # print(hometimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout removed',
            hometimeoutv, 'Home']
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
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout', awaytimeoutv ,'Away']
            writer.writerow(data)
            f.close()
            pause_countdown()
            time.sleep(1)
            stop_timeout()
            return redirect(url_for('timeout'))

        elif direction == 'decrement':
            awaytimeoutv = int(awaytimeoutv) - 1
            # print(awaytimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout', awaytimeoutv ,'Away']
            writer.writerow(data)
            f.close()
            direction = "increment"

    else:
        msg = 'clock not running'
        flash(msg, "warning")
        if direction == 'decrement':
            awaytimeoutv = int(awaytimeoutv) - 1
            # print(awaytimeoutv)
            td_str = str(timedelta(seconds=remaining_time))
            x = td_str.split(':')

            f = open(running_file, 'a')
            writer = csv.writer(f)
            # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
            data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout', awaytimeoutv,
            'Away']
            writer.writerow(data)
            f.close()
            direction = "increment"

    return redirect(url_for('index'))



@app.route('/timeout')
def timeout():
    global  timeout
    timeout = Config.TIMEOUT_TIME
    start_timeout()
    return render_template('timeout.html', scores=scores, teama=teama, teamb=teamb, elapsed_timeout=elapsedtimeout, TeamHome=TeamHome, TeamAway=TeamAway ,periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM, AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv , filename=filename, clocktime=remaining_time)
@app.route('/runinterval')
def runinterval():
    global timeout
    if quarter == 3 :
        timeout = Config.HALFTIME
    else:
        timeout = Config.INTERVAL_TIME

    start_timeout()
    return render_template('interval.html', scores=scores, teama=teama, teamb=teamb, elapsed_timeout=elapsedtimeout, TeamHome=TeamHome, TeamAway=TeamAway ,periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM, AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv , filename=filename)


@app.route('/runintervalgoal')
def runintervalgoal():
    global timeout
    # if quarter == 3 :
    #     timeout = Config.HALFTIME
    # else:
    #     timeout = Config.INTERVAL_TIME

    # start_timeout()
    return render_template('interval.html', scores=scores, teama=teama, teamb=teamb, elapsed_timeout=elapsedtimeout, TeamHome=TeamHome, TeamAway=TeamAway ,periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM, AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv , filename=filename)

@app.route('/interval')
def interval():
    start_timeout()
    return render_template('interval.html', scores=scores, teama=teama, teamb=teamb, elapsed_timeout=elapsedtimeout, TeamHome=TeamHome, TeamAway=TeamAway ,periodscores=periodscores, quarter=quarter, HomeTeam=Config.DEFAULT_HOME_TEAM, AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION, hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv , filename=filename)



@app.route('/returninterval')
def returninterval():
    stop_countdown()

    timestamp = datetime.now()

    f = open(running_file, 'a')
    writer = csv.writer(f)
    header = ['Game Status at ', Config.DEFAULT_LOCATION, ' on the ', timestamp, 'end of quarter :', quarter - 1, ]
    writer.writerow(header)

    # header1 = ['HomeScore', 'AwayScore', 'HomeMajors', 'AwayMajors']
    # writer.writerow(header1)

    data = ['Home score:', scores['Home']['goals'], 'Away score :', scores['Away']['goals'], 'Home Majors:',
            scores['Home']['majors'], 'Away Majors :', scores['Away']['majors']]
    writer.writerow(data)

    header = ['Quarter', 'Min', 'Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'name', 'team', 'goals', 'majors',
              'reds']
    writer.writerow(header)

    f.close()

    return redirect(url_for('index'))


@app.route('/callinterval', methods=['GET', 'POST'])
def callinterval():
    if request.method == 'GET':
        global quarter
        global countdown_running, start_time, elapsed_time
        global timeout, reason ,intervaltime
        reason = 'Break'
        timeout = Config.TIMEOUT_TIME
        # elapsed_time = time.time() - start_time
        # remaining_time = math.floor(max(gametime * 30 - elapsed_time, 0))
        quarter=quarter +1
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
    return render_template('setup.html' , HomeTeam=Config.DEFAULT_HOME_TEAM, AwayTeam=Config.DEFAULT_AWAY_TEAM, location=Config.DEFAULT_LOCATION , ble_clients=ble_clients  )

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
    Config.MAJORS = int(request.form['majors'])
    Config.BLUETOOTH_NAME = str(request.form['ble'])

    return redirect(url_for('index'))


@app.route('/savehomeplayers/<user_id>' , methods=['GET', 'POST'])
def savehomeplayers(user_id):
    if request.method == 'POST':
        # Clear the existing data for the user ID
        home_data[user_id] = []

        # Get the number of entries
        num_entries = int(request.form.get('num_entries'))

        # Update the user's data with the new entries
        for i in range(num_entries):
            hatnum = request.form.get(f'hatnum_{i}')
            name = request.form.get(f'name_{i}')

            form_data = [hatnum,name]

            home_data[user_id].append(form_data)
        # print(home_data)
        return redirect(url_for('index'))

    # For GET requests, render the form with existing data
    existing_data = home_data.get(user_id, [])

    return render_template('hometeamsetup.html', user_id=user_id, data=existing_data)

@app.route('/saveawayplayers/<user_id>' , methods=['GET', 'POST'])
def saveawayplayers(user_id):
    if request.method == 'POST':
        # Clear the existing data for the user ID
        away_data[user_id] = []

        # Get the number of entries
        num_entries = int(request.form.get('num_entries'))

        # Update the user's data with the new entries
        for i in range(num_entries):
            hatnum = request.form.get(f'hatnum_{i}')
            name = request.form.get(f'name_{i}')

            form_data = [hatnum,name]

            away_data[user_id].append(form_data)
        # print(away_data)
        return redirect(url_for('index'))

    # For GET requests, render the form with existing data
    existing_data = away_data.get(user_id, [])
    return render_template('awayteamsetup.html', user_id=user_id, data=existing_data)

@app.route('/saverefdata/<user_id>' , methods=['GET', 'POST'])
def saverefdata(user_id):
    if request.method == 'POST':
        # Clear the existing data for the user ID
        ref_data[user_id] = []

        # Get the number of entries
        num_entries = int(request.form.get('num_entries'))

        # Update the user's data with the new entries
        for i in range(num_entries):
            hatnum = request.form.get(f'hatnum_{i}')
            name = request.form.get(f'name_{i}')
            club = request.form.get(f'club_{i}')
            expences = request.form.get(f'expences_{i}')

            form_data = [hatnum,name,club,expences]

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
    pdf.set_font("helvetica", size=10)

    with open(compress_file, 'r', encoding='utf-8', newline='') as f:
        csv_reader = csv.reader(f)
        for row in csv_reader:
            # Join CSV columns with proper spacing
            line_text = ' | '.join(str(cell) for cell in row)

            # Handle long lines - split if necessary
            if pdf.get_string_width(line_text) > 190:  # Page width minus margins
                # For long lines, use multi_cell
                pdf.multi_cell(0, 10, txt=line_text, border=0)
            else:
                pdf.cell(0, 10, text=line_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf_file_path = compress_file.rsplit('.', 1)[0] + '.pdf'
    pdf.output(pdf_file_path)
    return redirect(url_for('index'))


if __name__ == '__main__':
    # asyncio.run(init_ble())
    # app.run(debug=True, host=Config.WEB_HOST, port=Config.WEB_PORT)
    webview.start()
    # webview.start(gui='edgechromium', debug=True, private_mode=True, run_on_main_thread=False)

    # asyncio.run(init_ble())

