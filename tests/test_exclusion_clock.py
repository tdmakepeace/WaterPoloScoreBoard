"""Tests for the major (exclusion) clocks shown under the shot clock."""

from unittest.mock import patch

import pytest

import start


@pytest.fixture(autouse=True)
def reset_clock_state():
    start.clearExclusionClocks()
    start.countdown_running = False
    start.start_time = 0
    start.elapsed_time = 0
    start.start_shot = 0
    start.elapsed_shot = 0
    start.clock_shot = start.Config.SHOT_CLOCK
    start.remaining_shot = start.Config.SHOT_CLOCK
    start.quarter = 1
    start.runningclock = "no"
    yield
    start.clearExclusionClocks()
    start.countdown_running = False


@pytest.fixture
def quiet_side_effects():
    with (
        patch.object(start, "ble_send_int") as mock_ble_int,
        patch.object(start, "ble_send_command") as mock_ble_cmd,
        patch.object(start, "broadcast_refresh_event"),
        patch.object(start, "render_template", return_value=""),
    ):
        yield {"ble_send_int": mock_ble_int, "ble_send_command": mock_ble_cmd}


@pytest.fixture
def client():
    return start.app.test_client()


def test_major_starts_one_clock_at_foul_clock(client, quiet_side_effects):
    client.get('/major')

    assert start.getExclusionRemaining() == [float(start.Config.FOUL_CLOCK)]


def test_second_major_adds_second_clock(client, quiet_side_effects):
    client.get('/major')
    client.get('/major')

    assert len(start.exclusion_clocks) == 2


def test_third_major_replaces_oldest_clock():
    start.startExclusionClock(now=0.0)
    start.exclusion_clocks[0]['spent'] = 10.0
    start.startExclusionClock(now=0.0)
    start.exclusion_clocks[1]['spent'] = 5.0

    start.startExclusionClock(now=0.0)

    assert start.getExclusionRemaining(now=0.0) == [start.Config.FOUL_CLOCK - 5.0, float(start.Config.FOUL_CLOCK)]


def test_major_before_game_start_does_not_start_clock(client, quiet_side_effects):
    start.quarter = 0

    client.get('/major')

    assert start.exclusion_clocks == []


def test_clock_ticks_while_game_clock_running():
    start.countdown_running = True
    start.startExclusionClock(now=100.0)

    assert start.getExclusionRemaining(now=105.0) == [start.Config.FOUL_CLOCK - 5.0]


def test_clock_holds_while_game_clock_paused():
    start.countdown_running = False
    start.startExclusionClock(now=100.0)

    assert start.getExclusionRemaining(now=200.0) == [float(start.Config.FOUL_CLOCK)]


def test_pause_freezes_and_resume_continues(client, quiet_side_effects):
    with patch("start.time.time", return_value=100.0):
        client.get('/start_countdown')
        start.startExclusionClock()
    with patch("start.time.time", return_value=104.0):
        client.get('/pause_countdown')
    with patch("start.time.time", return_value=150.0):
        client.get('/pause_countdown')
    with patch("start.time.time", return_value=153.0):
        remaining = start.getExclusionRemaining()

    assert remaining == [start.Config.FOUL_CLOCK - 7.0]


def test_repeated_resume_does_not_double_count():
    start.countdown_running = True
    start.startExclusionClock(now=100.0)

    start.resumeExclusionClocks(now=103.0)

    assert start.getExclusionRemaining(now=105.0) == [start.Config.FOUL_CLOCK - 5.0]


@pytest.mark.parametrize("route", ['/possession', '/reset30'])
def test_possession_change_clears_clocks(client, quiet_side_effects, route):
    start.startExclusionClock()
    start.startExclusionClock()

    client.get(route)

    assert start.exclusion_clocks == []


def test_goal_clears_clocks(client, quiet_side_effects):
    start.startExclusionClock()

    client.get('/goal')

    assert start.exclusion_clocks == []


@pytest.mark.parametrize("route", ['/reset20', '/pause20', '/force20', '/shot_clock_plus', '/shot_clock_minus'])
def test_shot_and_corner_routes_keep_clocks(client, quiet_side_effects, route):
    start.startExclusionClock()

    client.get(route)

    assert len(start.exclusion_clocks) == 1


def test_expired_clock_stays_at_zero():
    start.countdown_running = True
    start.startExclusionClock(now=0.0)

    assert start.getExclusionRemaining(now=500.0) == [0.0]


def test_expired_clock_triggers_no_side_effects(client, quiet_side_effects):
    start.countdown_running = True
    start.startExclusionClock(now=0.0)

    with patch("start.time.time", return_value=500.0):
        client.get('/get_countdown_status')

    quiet_side_effects["ble_send_command"].assert_not_called()


def test_countdown_status_includes_exclusion_clocks(client):
    start.startExclusionClock()

    body = client.get('/get_countdown_status').get_json()

    assert body['exclusion_clocks'] == [float(start.Config.FOUL_CLOCK)]
