from flask import Flask, render_template, request, redirect, url_for, jsonify,flash
from flask import send_file
import time, csv, math , sys
from datetime import datetime, timedelta
# import winsound
import os
import webview


webtimeout = 180
# the host the webservice is hosted on, FQDN or IP is required.
# 0.0.0.0 for all interfaces.
webhost = '0.0.0.0'

# the port the webservice is hosted on, default flask is 5000.
webport = '5000' 

app = Flask(__name__, static_url_path='/static')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'waterpolo'
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=webtimeout)

# Initial scores for two teams

scores = {
    'Home': {'goals': 0, 'majors': 0},
    'Away': {'goals': 0, 'majors': 0}
}
TeamHome = scores['Home']
TeamAway = scores['Away']

periodscores = {
    'Home': {'goals1': 0, 'majors1': 0, 'goals2': 0, 'majors2': 0,'goals3': 0, 'majors3': 0,'goals4': 0, 'majors4': 0},
    'Away': {'goals1': 0, 'majors1': 0, 'goals2': 0, 'majors2': 0,'goals3': 0, 'majors3': 0,'goals4': 0, 'majors4': 0}
}
home_data = {'home': [['1', ''], ['2', ''], ['3', ''], ['4', ''], ['5', ''], ['6', ''], ['7', ''], ['8', ''], ['9', ''], ['10', ''], ['11', ''], ['12', ''], ['13', '']]}
away_data = {'away': [['1', ''], ['2', ''], ['3', ''], ['4', ''], ['5', ''], ['6', ''], ['7', ''], ['8', ''], ['9', ''], ['10', ''], ['11', ''], ['12', ''], ['13', '']]}

ref_data = {'referee': [['1', '','',''], ['2', '','','']]}


teama = {
    1: {'assists': 0, 'goals': 0, 'majors': 0},
    2: {'assists': 0, 'goals': 0, 'majors': 0},
    3: {'assists': 0, 'goals': 0, 'majors': 0},
    4: {'assists': 0, 'goals': 0, 'majors': 0},
    5: {'assists': 0, 'goals': 0, 'majors': 0},
    6: {'assists': 0, 'goals': 0, 'majors': 0},
    7: {'assists': 0, 'goals': 0, 'majors': 0},
    8: {'assists': 0, 'goals': 0, 'majors': 0},
    9: {'assists': 0, 'goals': 0, 'majors': 0},
    10: {'assists': 0, 'goals': 0, 'majors': 0},
    11: {'assists': 0, 'goals': 0, 'majors': 0},
    12: {'assists': 0, 'goals': 0, 'majors': 0},
    13: {'assists': 0, 'goals': 0, 'majors': 0}
}

teamb = {
    1: {'assists': 0, 'goals': 0, 'majors': 0},
    2: {'assists': 0, 'goals': 0, 'majors': 0},
    3: {'assists': 0, 'goals': 0, 'majors': 0},
    4: {'assists': 0, 'goals': 0, 'majors': 0},
    5: {'assists': 0, 'goals': 0, 'majors': 0},
    6: {'assists': 0, 'goals': 0, 'majors': 0},
    7: {'assists': 0, 'goals': 0, 'majors': 0},
    8: {'assists': 0, 'goals': 0, 'majors': 0},
    9: {'assists': 0, 'goals': 0, 'majors': 0},
    10: {'assists': 0, 'goals': 0, 'majors': 0},
    11: {'assists': 0, 'goals': 0, 'majors': 0},
    12: {'assists': 0, 'goals': 0, 'majors': 0},
    13: {'assists': 0, 'goals': 0, 'majors': 0}
}
quarter= 0
direction = "increment"
hometimeoutv = 0
awaytimeoutv = 0

intervaltime = 2
timeouttime = 1
runningclock = "yes"
gametime = 10
location = 'New Malden'
HomeTeam = 'Kingston Royals'
AwayTeam = 'Away Team'


filename = datetime.now().strftime(HomeTeam+'-%Y-%m-%d-%H-%M.csv')
countdown_running = False
start_time = 0
elapsed_time = 0

timeoutrunning = False
starttimeout = 0
elapsedtimeout = 0

reason = 'Timeout'
timeout = 0


# timestamp = datetime.now()

window = webview.create_window('WaterPolo Scoreboard',app )


@app.route('/')
def index():
    return render_template('timer.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway ,periodscores=periodscores, quarter=quarter, HomeTeam=HomeTeam, AwayTeam=AwayTeam, location=location, hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv , filename=filename)

@app.route('/display')
def display():
    return render_template('display.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway ,periodscores=periodscores, quarter=quarter, HomeTeam=HomeTeam, AwayTeam=AwayTeam, location=location, hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv , filename=filename)


@app.route('/start_countdown')
def start_countdown():
    global countdown_running, start_time, elapsed_time
    countdown_running = True
    start_time = time.time() - elapsed_time
    return jsonify({'status': 'success'})

@app.route('/stop_countdown')
def stop_countdown():
    global countdown_running, start_time, elapsed_time
    countdown_running = False
    start_time = 0
    elapsed_time = 0
    return jsonify({'status': 'success'})

@app.route('/pause_countdown')
def pause_countdown():
    global countdown_running, start_time, elapsed_time

    if countdown_running:
        countdown_running = False
        elapsed_time = time.time() - start_time
    else:
        countdown_running = True
        start_time = time.time() - elapsed_time

    return jsonify({'status': 'success'})

# @app.route('/pause_countdown')
# def pause_countdown():
#     global countdown_running, start_time, elapsed_time
#     countdown_running = False
#     elapsed_time = time.time() - start_time
#     return jsonify({'status': 'success'})


@app.route('/resume_countdown')
def resume_countdown():
    global countdown_running, start_time
    countdown_running = True
    start_time = time.time() - elapsed_time
    return jsonify({'status': 'success'})

@app.route('/get_countdown_status')
def get_countdown_status():
    global countdown_running, start_time, elapsed_time
    if countdown_running:
        elapsed_time = time.time() - start_time
        remaining_time = max((gametime*60) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})
    else:
        # return jsonify({'countdown_running': countdown_running, 'elapsed_time': elapsed_time})
        # elapsed_time = time.time() - start_time
        remaining_time = max((gametime*60) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})
@app.route('/start_timeout')
def start_timeout():
    global timeoutrunning, starttimeout, elapsedtimeout
    timeoutrunning = True
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
    global timeoutrunning, starttimeout, elapsedtimeout , timeout
    if timeoutrunning:
        elapsedtimeout = time.time() - starttimeout
        remainingtimeout = max((timeout*60) - elapsedtimeout, 0)
        return jsonify({'timeout_running': timeoutrunning, 'elapsed_timeout': remainingtimeout})
    else:
        return jsonify({'timeout_running': timeoutrunning, 'elapsed_timeout': elapsedtimeout})

@app.route('/addmin')
def addmin():
    global countdown_running, start_time, elapsed_time
    if countdown_running:
        elapsed_time = time.time() - start_time
        remaining_time = max((gametime*60) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})
    else:
        # return jsonify({'countdown_running': countdown_running, 'elapsed_time': elapsed_time})
        # elapsed_time = time.time() - start_time
        elapsed_time = elapsed_time - 60
        remaining_time = max((gametime*60) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})

@app.route('/minmin')
def minmin():
    global countdown_running, start_time, elapsed_time
    if countdown_running:
        elapsed_time = time.time() - start_time
        remaining_time = max((gametime*60) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})
    else:
        # return jsonify({'countdown_running': countdown_running, 'elapsed_time': elapsed_time})
        # elapsed_time = time.time() - start_time
        elapsed_time = elapsed_time + 60
        remaining_time = max((gametime*60) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})

@app.route('/addsec')
def addsec():
    global countdown_running, start_time, elapsed_time
    if countdown_running:
        elapsed_time = time.time() - start_time
        remaining_time = max((gametime*60) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})
    else:
        # return jsonify({'countdown_running': countdown_running, 'elapsed_time': elapsed_time})
        # elapsed_time = time.time() - start_time
        elapsed_time = elapsed_time - 1
        remaining_time = max((gametime*60) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})

@app.route('/minsec')
def minsec():
    global countdown_running, start_time, elapsed_time
    if countdown_running:
        elapsed_time = time.time() - start_time
        remaining_time = max((gametime*60) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})
    else:
        # return jsonify({'countdown_running': countdown_running, 'elapsed_time': elapsed_time})
        # elapsed_time = time.time() - start_time
        elapsed_time = elapsed_time + 1
        remaining_time = max((gametime*60) - elapsed_time, 0)
        return jsonify({'countdown_running': countdown_running, 'elapsed_time': remaining_time})



###### url


@app.route('/homegoal')
def homegoal():
    if countdown_running:
        if runningclock == "no":
            pause_countdown()
    else:
        msg = 'clock not running'
        flash(msg, "warning")

    return render_template('homegoal.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=HomeTeam, AwayTeam=AwayTeam, location=location, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)
@app.route('/homemajor')
def homemajor():
    if countdown_running:
        if runningclock == "no":
            pause_countdown()
    else:
        msg = 'clock not running'
        flash(msg, "warning")

    return render_template('homemajor.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=HomeTeam, AwayTeam=AwayTeam, location=location, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)

@app.route('/homepenalty')
def homepenalty():
    if countdown_running:
        if runningclock == "no":
            pause_countdown()
    else:
        msg = 'clock not running'
        flash(msg, "warning")

    return render_template('homepenalty.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=HomeTeam, AwayTeam=AwayTeam, location=location, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)

@app.route('/awaygoal')
def awaygoal():
    if countdown_running:
        if runningclock == "no":
            pause_countdown()
    else:
        msg = 'clock not running'
        flash(msg, "warning")

    return render_template('awaygoal.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=HomeTeam, AwayTeam=AwayTeam, location=location, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)
@app.route('/awaymajor')
def awaymajor():
    if countdown_running:
        if runningclock == "no":
            pause_countdown()
    else:
        msg = 'clock not running'
        flash(msg, "warning")

    return render_template('awaymajor.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=HomeTeam, AwayTeam=AwayTeam, location=location, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)

@app.route('/awaypenalty')
def awaypenalty():
    if countdown_running:
        if runningclock == "no":
            pause_countdown()
    else:
        msg = 'clock not running'
        flash(msg, "warning")

    return render_template('awaypenalty.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time,
                           TeamHome=TeamHome, TeamAway=TeamAway, periodscores=periodscores, quarter=quarter,
                           HomeTeam=HomeTeam, AwayTeam=AwayTeam, location=location, hometimeoutv=hometimeoutv,
                           awaytimeoutv=awaytimeoutv, filename=filename)



@app.route('/updateteamagoal/<int:user_id>', methods=['GET', 'POST'])
def updateteamagoal(user_id):
    if request.method == 'POST':
        global quarter, direction
        global countdown_running, start_time, elapsed_time


        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(gametime*60 - elapsed_time, 0))
        # print('help1')
        # action = request.form['action']
        direction = str(direction)
        # action = "increment"
        if direction == 'increment':
            # print('help2')
            teama[user_id]['goals'] = teama[user_id]['goals'] + 1
            scores['Home']['goals'] = scores['Home']['goals'] + 1
            if quarter == 1:
                periodscores['Home']['goals1'] = periodscores['Home']['goals1'] + 1
                # print('help3')
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
        f = open(filename, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'Min','Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
        data = [ quarter , x[1],x[2], scores['Home']['goals'] , scores['Away']['goals'] , 'Goal' , user_id , 'Home' , teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['assists'] ]
        writer.writerow(data)
        f.close()
        # print(quarter)
        # print(periodscores)
        # print(direction)
        # print(runningclock)
        # print(user_id)

    return redirect(url_for('index'))


@app.route('/updateteamamajor/<int:user_id>', methods=['GET', 'POST'])
def updateteamamajor(user_id):
    if request.method == 'POST':
        # action = request.form['action']
        global quarter
        global direction
        global countdown_running, start_time, elapsed_time
        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(gametime*60 - elapsed_time, 0))
        if direction == 'increment':
            if teama[user_id]['majors'] == 3:
                teama[user_id]['majors'] = 0
                scores['Home']['majors'] = scores['Home']['majors'] - 3
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

        f = open(filename, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
        data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Majors', user_id, 'Home', teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['assists']]
        writer.writerow(data)
        f.close()

    return redirect(url_for('index'))


@app.route('/updateteamapenalty/<int:user_id>', methods=['GET', 'POST'])
def updateteamapenalty(user_id):
    if request.method == 'POST':
        # action = request.form['action']
        global quarter
        global direction
        global countdown_running, start_time, elapsed_time
        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(gametime * 60 - elapsed_time, 0))
        if direction == 'increment':
            if teama[user_id]['majors'] == 3:
                teama[user_id]['majors'] = 0
                scores['Home']['majors'] = scores['Home']['majors'] - 3
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

        f = open(filename, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
        data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Penalty', user_id, 'Home',
                teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['assists']]
        writer.writerow(data)
        f.close()

    return redirect(url_for('index'))



# @app.route('/updateteamaassists/<int:user_id>', methods=['GET', 'POST'])
# def updateteamaassists(user_id):
#     if request.method == 'POST':
#         global quarter
#         global direction
#         global countdown_running, start_time, elapsed_time
#         if countdown_running:
#             elapsed_time = time.time() - start_time
#             remaining_time = math.floor(max(gametime*60 - elapsed_time, 0))
#
#             # action = request.form['action']
#
#             if direction == 'increment':
#                 teama[user_id]['assists'] = teama[user_id]['assists'] + 1
#             elif direction == 'decrement':
#                 teama[user_id]['assists'] = teama[user_id]['assists'] - 1
#             direction = "increment"
#
#             td_str = str(timedelta(seconds=remaining_time))
#             x = td_str.split(':')
#
#             f = open(filename, 'a')
#             writer = csv.writer(f)
#             # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
#             data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Assists', user_id, 'Home',
#             teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['assists']]
#             writer.writerow(data)
#             f.close()
#
#         else:
#             msg = 'clock not running'
#             flash(msg, "warning")
#         return redirect(url_for('index'))
#
#     return redirect(url_for('index'))

@app.route('/updateteambgoal/<int:user_id>', methods=['GET', 'POST'])
def updateteambgoal(user_id):
    if request.method == 'POST':
        # action = request.form['action']
        global quarter
        global direction
        global countdown_running, start_time, elapsed_time
        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(gametime*60 - elapsed_time, 0))

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

        f = open(filename, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
        data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Goal', user_id, 'Away',
        teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['assists']]
        writer.writerow(data)
        f.close()

    return redirect(url_for('index'))


@app.route('/updateteambmajor/<int:user_id>', methods=['GET', 'POST'])
def updateteambmajor(user_id):
    if request.method == 'POST':
        # direction = request.form['action']

        global quarter
        global direction
        global countdown_running, start_time, elapsed_time
        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(gametime*60 - elapsed_time, 0))

        if direction == 'increment':
            if teamb[user_id]['majors'] == 3:
                teamb[user_id]['majors'] = 0
                scores['Away']['majors'] = scores['Away']['majors'] - 3
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

        f = open(filename, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
        data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Major', user_id, 'Away',
        teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['assists']]
        writer.writerow(data)
        f.close()

    return redirect(url_for('index'))

@app.route('/updateteambpenalty/<int:user_id>', methods=['GET', 'POST'])
def updateteambpenalty(user_id):
    if request.method == 'POST':
        # action = request.form['action']
        global quarter
        global direction
        global countdown_running, start_time, elapsed_time
        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(gametime * 60 - elapsed_time, 0))
        if direction == 'increment':
            if teamb[user_id]['majors'] == 3:
                teamb[user_id]['majors'] = 0
                scores['Away']['majors'] = scores['Away']['majors'] - 3
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

        f = open(filename, 'a')
        writer = csv.writer(f)
        # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
        data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Penalty', user_id, 'Away',
        teamb[user_id]['goals'], teamb[user_id]['majors'], teamb[user_id]['assists']]
        writer.writerow(data)
        f.close()

    return redirect(url_for('index'))




# @app.route('/updateteambassists/<int:user_id>', methods=['GET', 'POST'])
# def updateteambassists(user_id):
#     if request.method == 'POST':
#         # action = request.form['action']
#
#         global quarter
#         global direction
#         global countdown_running, start_time, elapsed_time
#         if countdown_running:
#             elapsed_time = time.time() - start_time
#             remaining_time = math.floor(max(gametime*60 - elapsed_time, 0))
#
#             if direction == 'increment':
#                 teamb[user_id]['assists'] = teamb[user_id]['assists'] + 1
#
#             elif direction == 'decrement':
#                 teamb[user_id]['assists'] = teamb[user_id]['assists'] - 1
#                 direction = "increment"
#
#             td_str = str(timedelta(seconds=remaining_time))
#             x = td_str.split(':')
#
#             f = open(filename, 'a')
#             writer = csv.writer(f)
#             # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
#             data = [quarter, x[1],x[2], scores['Home']['goals'], scores['Away']['goals'], 'Assist', user_id, 'Away',
#             teama[user_id]['goals'], teama[user_id]['majors'], teama[user_id]['assists']]
#             writer.writerow(data)
#             f.close()
#         else:
#             msg = 'clock not running'
#             flash(msg, "warning")
#         return redirect(url_for('index'))
#
#     return redirect(url_for('index'))

@app.route('/period', methods=['GET', 'POST'])
def period():
    if request.method == 'POST':
        global quarter, direction
        if direction == 'increment':
            quarter = quarter + 1
            timestamp = datetime.now()

            f = open(filename, 'a')
            writer = csv.writer(f)
            header = ['Game Status at ', location, ' on the ', timestamp, 'end of quarter :' ,quarter -1, ]
            writer.writerow(header)

            # header1 = ['HomeScore', 'AwayScore', 'HomeMajors', 'AwayMajors']
            # writer.writerow(header1)

            data = ['Home score:', scores['Home']['goals'], 'Away score :', scores['Away']['goals'],'Home Majors:',  scores['Home']['majors'], 'Away Majors :', scores['Away']['majors']]
            writer.writerow(data)

            header = ['Quarter', 'Min', 'Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'team', 'goals', 'majors', 'assists']
            writer.writerow(header)

            f.close()
        elif direction == 'decrement':
            quarter = quarter - 1
            timestamp = datetime.now()

            f = open(filename, 'a')
            writer = csv.writer(f)
            header = ['Game Status at ', location, ' on the ', timestamp, 'end of quarter :' ,quarter -1, ]
            writer.writerow(header)

            # header1 = ['HomeScore', 'AwayScore', 'HomeMajors', 'AwayMajors']
            # writer.writerow(header1)

            data = ['Home score:', scores['Home']['goals'], 'Away score :', scores['Away']['goals'],'Home Majors:',  scores['Home']['majors'], 'Away Majors :', scores['Away']['majors']]
            writer.writerow(data)

            header = ['Quarter', 'Min', 'Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'team', 'goals', 'majors', 'assists']
            writer.writerow(header)

            f.close()
            direction = "increment"

    return redirect(url_for('index'))

@app.route('/clear', methods=['GET', 'POST'])
def direction():
    if request.method == 'POST':
        global direction
        direction = "decrement"
    return redirect(url_for('index'))




@app.route('/start', methods=['GET', 'POST'])
def start():
    if request.method == 'POST':

        global quarter , scores, TeamHome, TeamAway,periodscores,teama,teamb
        global direction ,hometimeoutv, awaytimeoutv
        now = datetime.now()  # current date and time
        timestamp = now.strftime("%d/%m/%Y, %H:%M:%S")

        direction = "increment"
        # print(direction)
        quarter = int(1)
        header = ['New Game Held at ',location,' on the ',timestamp]
        f = open(filename, 'w')
        writer = csv.writer(f)
        writer.writerow(header)


        header2 = ['Home Team: ', HomeTeam ]
        writer.writerow(header2)
        header2 = ['Hatnumber','Player']
        writer.writerow(header2)
        for i in home_data['home'] :
            data = i[0],i[1]
            writer.writerow(data)

        header2 = ['Away Team: ', AwayTeam ]
        writer.writerow(header2)
        header2 = ['Hatnumber','Player']
        writer.writerow(header2)
        for i in away_data['away'] :
            data = i[0],i[1]
            writer.writerow(data)


        header = ['Quarter', 'Min','Sec', 'HomeScore', 'AwayScore', 'action', 'player', 'team', 'goals', 'majors', 'assists']
        writer.writerow(header)

        f.close()

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
        1: {'assists': 0, 'goals': 0, 'majors': 0},
        2: {'assists': 0, 'goals': 0, 'majors': 0},
        3: {'assists': 0, 'goals': 0, 'majors': 0},
        4: {'assists': 0, 'goals': 0, 'majors': 0},
        5: {'assists': 0, 'goals': 0, 'majors': 0},
        6: {'assists': 0, 'goals': 0, 'majors': 0},
        7: {'assists': 0, 'goals': 0, 'majors': 0},
        8: {'assists': 0, 'goals': 0, 'majors': 0},
        9: {'assists': 0, 'goals': 0, 'majors': 0},
        10: {'assists': 0, 'goals': 0, 'majors': 0},
        11: {'assists': 0, 'goals': 0, 'majors': 0},
        12: {'assists': 0, 'goals': 0, 'majors': 0},
        13: {'assists': 0, 'goals': 0, 'majors': 0}
        }

        teamb = {
        1: {'assists': 0, 'goals': 0, 'majors': 0},
        2: {'assists': 0, 'goals': 0, 'majors': 0},
        3: {'assists': 0, 'goals': 0, 'majors': 0},
        4: {'assists': 0, 'goals': 0, 'majors': 0},
        5: {'assists': 0, 'goals': 0, 'majors': 0},
        6: {'assists': 0, 'goals': 0, 'majors': 0},
        7: {'assists': 0, 'goals': 0, 'majors': 0},
        8: {'assists': 0, 'goals': 0, 'majors': 0},
        9: {'assists': 0, 'goals': 0, 'majors': 0},
        10: {'assists': 0, 'goals': 0, 'majors': 0},
        11: {'assists': 0, 'goals': 0, 'majors': 0},
        12: {'assists': 0, 'goals': 0, 'majors': 0},
        13: {'assists': 0, 'goals': 0, 'majors': 0}
        }
        hometimeoutv = 0
        awaytimeoutv = 0

    return redirect(url_for('index'))


@app.route('/finish', methods=['GET', 'POST'])
def finish():
    if request.method == 'POST':
        global quarter
        # timestamp = datetime.now()

        now = datetime.now()  # current date and time
        timestamp = now.strftime("%d/%m/%Y, %H:%M:%S")

        f = open(filename, 'a')
        writer = csv.writer(f)
        header = ['Game Over at ', location, ' on the ', timestamp]
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

        header2 = ['Home Team: ', HomeTeam ]
        writer.writerow(header2)
        header2 = ['Hatnumber','Player']
        writer.writerow(header2)
        for i in home_data['home'] :
            data = i[0],i[1]
            writer.writerow(data)

        header2 = ['Away Team: ', AwayTeam ]
        writer.writerow(header2)
        header2 = ['Hatnumber','Player']
        writer.writerow(header2)
        for i in away_data['away'] :
            data = i[0],i[1]
            writer.writerow(data)

        header2 = ['Home Player','goals','majors','assists']
        writer.writerow(header2)
        for user_id in teama:
            data = [user_id ,teama[user_id]['goals'],teama[user_id]['majors'],teama[user_id]['assists'] ]
            writer.writerow(data)

        header2 = ['Away Player','goals','majors','assists']
        writer.writerow(header2)
        for user_id in teamb:
            data = [user_id ,teamb[user_id]['goals'],teamb[user_id]['majors'],teamb[user_id]['assists'] ]
            writer.writerow(data)

        header2 = ['Referees: ' ]
        writer.writerow(header2)
        header2 = ['Hatnumber','Name', 'Club', 'Expences']
        writer.writerow(header2)
        for i in ref_data['referee'] :
            data = i[0],i[1],i[2],i[3]
            writer.writerow(data)

        f.close()

    return redirect(url_for('index'))

@app.route('/hometimeout', methods=['GET', 'POST'])
def hometimeout():
    if request.method == 'POST':
        global hometimeoutv
        global quarter
        global direction
        global countdown_running, start_time, elapsed_time
        global timeout, reason ,timeouttime
        reason = 'Home Timeout'
        timeout = timeouttime
        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(gametime * 60 - elapsed_time, 0))
        if countdown_running:
            if direction == 'increment':
                pause_countdown()
                hometimeoutv = int(hometimeoutv) + 1
                print(hometimeoutv)
                td_str = str(timedelta(seconds=remaining_time))
                x = td_str.split(':')

                f = open(filename, 'a')
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
                print(hometimeoutv)
                td_str = str(timedelta(seconds=remaining_time))
                x = td_str.split(':')

                f = open(filename, 'a')
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
                print(hometimeoutv)
                td_str = str(timedelta(seconds=remaining_time))
                x = td_str.split(':')

                f = open(filename, 'a')
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
                print(hometimeoutv)
                td_str = str(timedelta(seconds=remaining_time))
                x = td_str.split(':')

                f = open(filename, 'a')
                writer = csv.writer(f)
                # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout removed',
                hometimeoutv, 'Home']
                writer.writerow(data)
                f.close()
                direction = "increment"

        return redirect(url_for('index'))


@app.route('/awaytimeout', methods=['GET', 'POST'])
def awaytimeout():
    if request.method == 'POST':
        global awaytimeoutv
        global quarter
        global direction
        global countdown_running, start_time, elapsed_time
        global timeout, reason, timeouttime
        reason = 'Away Timeout'
        timeout = timeouttime
        print(timeout)
        print(timeouttime)
        # elapsed_time = time.time() - start_time
        remaining_time = math.floor(max(gametime * 60 - elapsed_time, 0))
        if countdown_running:
            if direction == 'increment':
                awaytimeoutv = int(awaytimeoutv) + 1
                print(awaytimeoutv)
                td_str = str(timedelta(seconds=remaining_time))
                x = td_str.split(':')

                f = open(filename, 'a')
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
                print(awaytimeoutv)
                td_str = str(timedelta(seconds=remaining_time))
                x = td_str.split(':')

                f = open(filename, 'a')
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
                print(awaytimeoutv)
                td_str = str(timedelta(seconds=remaining_time))
                x = td_str.split(':')

                f = open(filename, 'a')
                writer = csv.writer(f)
                # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
                data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Timeout', awaytimeoutv,
                'Away']
                writer.writerow(data)
                f.close()
                direction = "increment"

    return redirect(url_for('index'))


# @app.route('/homepenalty', methods=['GET', 'POST'])
# def homepenalty():
#     if request.method == 'POST':
#         global quarter
#         global direction
#         global countdown_running, start_time, elapsed_time
#         elapsed_time = time.time() - start_time
#         remaining_time = math.floor(max(gametime * 60 - elapsed_time, 0))
#         pause_countdown()
#         td_str = str(timedelta(seconds=remaining_time))
#         x = td_str.split(':')
#
#         f = open(filename, 'a')
#         writer = csv.writer(f)
#         # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
#         data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Penalty', 'Penalty' ,'Home']
#         writer.writerow(data)
#         f.close()
#
#     return redirect(url_for('index'))
#
#
# @app.route('/awaypenalty', methods=['GET', 'POST'])
# def awaypenalty():
#     if request.method == 'POST':
#         global quarter
#         global direction
#         global countdown_running, start_time, elapsed_time
#         elapsed_time = time.time() - start_time
#         remaining_time = math.floor(max(gametime * 60 - elapsed_time, 0))
#         pause_countdown()
#         td_str = str(timedelta(seconds=remaining_time))
#         x = td_str.split(':')
#
#         f = open(filename, 'a')
#         writer = csv.writer(f)
#         # header = ['Quarter', 'time', 'HomeScore', 'AwayScore', 'action', 'player', 'team' , 'goals' , 'majors', 'assists' ]
#         data = [quarter, x[1], x[2], scores['Home']['goals'], scores['Away']['goals'], 'Penalty', 'Penalty' ,'Away']
#         writer.writerow(data)
#         f.close()
#
#     return redirect(url_for('index'))




@app.route('/timeout')
def timeout():
    start_timeout()
    return render_template('timeout.html', scores=scores, teama=teama, teamb=teamb, elapsed_timeout=elapsedtimeout, TeamHome=TeamHome, TeamAway=TeamAway , location=location, hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, reason=reason)

@app.route('/runinterval')
def runinterval():
    start_timeout()
    return render_template('interval.html', scores=scores, teama=teama, teamb=teamb, elapsed_timeout=elapsedtimeout, TeamHome=TeamHome, TeamAway=TeamAway , location=location, hometimeoutv=hometimeoutv, awaytimeoutv=awaytimeoutv, reason=reason)


@app.route('/returninterval')
def returninterval():
    stop_countdown()
    return redirect(url_for('index'))


@app.route('/callinterval', methods=['GET', 'POST'])
def callinterval():
    if request.method == 'GET':
        global quarter
        global countdown_running, start_time, elapsed_time
        global timeout, reason ,intervaltime
        reason = 'Break'
        timeout = intervaltime
        # elapsed_time = time.time() - start_time
        # remaining_time = math.floor(max(gametime * 60 - elapsed_time, 0))
        quarter=quarter +1
        pause_countdown()
        time.sleep(1)
        stop_timeout()
        return redirect(url_for('runinterval'))

    return redirect(url_for('index'))


@app.route('/settings')
def settings():
    # return render_template('setup.html', scores=scores, teama=teama, teamb=teamb, elapsed_time=elapsed_time, TeamHome=TeamHome, TeamAway=TeamAway ,periodscores=periodscores, quarter=quarter, HomeTeam=HomeTeam, AwayTeam=AwayTeam)
    return render_template('setup.html' , HomeTeam=HomeTeam, AwayTeam=AwayTeam, location=location)

@app.route('/help')
def help():
    return render_template('help.html')

@app.route('/save' , methods=['GET', 'POST'])
def save():
    global runningclock, gametime, location, HomeTeam, AwayTeam,  timeouttime, intervaltime

    game = int(request.form['game'])
    running = (request.form['running'])
    timeouttime = int(request.form['timeout'])
    intervaltime = int(request.form['interval'])
    Loca = (request.form['Location'])
    Home = (request.form['Home'])
    Away = (request.form['Away'])

    # print(game,running,timeout,Loca,Home,Away)
    runningclock = running
    gametime = game
    location = Loca
    HomeTeam = Home
    AwayTeam = Away
    # restart()
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
        print(home_data)
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
        print(away_data)
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
        print(ref_data)
        return redirect(url_for('index'))

    # For GET requests, render the form with existing data
    existing_data = ref_data.get(user_id, [])

    return render_template('refdata.html', user_id=user_id, data=existing_data)


@app.route('/download/<filename>', methods=['GET', 'POST'])
def download(filename):
    return send_file(filename, as_attachment=True)

def restart():
    print('Restarting script...')
    os.execv(sys.executable, ['python3 start.py'] + sys.argv)


if __name__ == '__main__':
    # app.run(debug=True, host=webhost, port=webport)
    webview.start()