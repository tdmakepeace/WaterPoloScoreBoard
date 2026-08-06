"""Regression tests for timeout state, countdown resume, and settings sync."""

from unittest.mock import patch

import pytest

import start


@pytest.fixture
def restore_timeout_state():
    previous = (start.timeoutrunning, start.starttimeout, start.elapsedtimeout)
    yield
    start.timeoutrunning, start.starttimeout, start.elapsedtimeout = previous


@pytest.fixture
def restore_countdown_state():
    previous = (
        start.countdown_running,
        start.start_time,
        start.start_shot,
        start.elapsed_time,
        start.elapsed_shot,
    )
    yield
    (
        start.countdown_running,
        start.start_time,
        start.start_shot,
        start.elapsed_time,
        start.elapsed_shot,
    ) = previous


@pytest.fixture
def restore_config_state():
    previous = (
        start.Config.GAME_TIME,
        start.Config.INTERVAL_TIME,
        start.Config.HALFTIME,
        start.Config.DEFAULT_LOCATION,
        start.Config.DEFAULT_HOME_TEAM,
        start.Config.DEFAULT_AWAY_TEAM,
        start.Config.SHOT_CLOCK,
        start.Config.FOUL_CLOCK,
        start.Config.MAJORS,
        start.Config.SERIAL_PORT,
    )
    yield
    (
        start.Config.GAME_TIME,
        start.Config.INTERVAL_TIME,
        start.Config.HALFTIME,
        start.Config.DEFAULT_LOCATION,
        start.Config.DEFAULT_HOME_TEAM,
        start.Config.DEFAULT_AWAY_TEAM,
        start.Config.SHOT_CLOCK,
        start.Config.FOUL_CLOCK,
        start.Config.MAJORS,
        start.Config.SERIAL_PORT,
    ) = previous


def test_stop_timeout_clears_running_flag(restore_timeout_state):
    start.timeoutrunning = True
    start.starttimeout = 123.0
    start.elapsedtimeout = 15.0

    with start.app.app_context():
        start.stop_timeout()

    assert start.timeoutrunning is False
    assert start.starttimeout == 0
    assert start.elapsedtimeout == 0


def test_return_countdown_restores_clock_baselines(restore_countdown_state):
    start.countdown_running = False
    start.elapsed_time = 42.0
    start.elapsed_shot = 9.0
    start.start_time = 0
    start.start_shot = 0

    with start.app.app_context():
        with patch("start.time.time", return_value=100.0):
            start.return_countdown()

    assert start.countdown_running is True
    assert start.start_time == 58.0
    assert start.start_shot == 91.0


def test_save_recomputes_foul_clock_from_shot_clock(restore_config_state):
    client = start.app.test_client()

    with patch.object(start, "try_autoconnect_serial"), patch.object(start, "disconnect_serial"):
        response = client.post(
            "/save",
            data={
                "game": "13",
                "interval": "4",
                "half": "4",
                "Location": "Pool",
                "Home": "Home",
                "Away": "Away",
                "shotclock": "25",
                "majors": "3",
                "serial_port": "",
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert start.Config.SHOT_CLOCK == 25
    assert start.Config.FOUL_CLOCK == 15
