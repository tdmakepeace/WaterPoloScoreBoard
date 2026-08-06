"""Tests for countdown display helpers."""

from unittest.mock import patch

import start


def test_get_countdown_display_values_default_game_start():
    start.countdown_running = False
    start.elapsed_time = 0
    start.elapsed_shot = 0
    start.clock_shot = start.Config.SHOT_CLOCK

    values = start.getCountdownDisplayValues()

    assert values['countdown_running'] is False
    assert values['remaining_time'] == start.Config.GAME_TIME * 30
    assert values['remaining_shot'] == start.Config.SHOT_CLOCK
    assert values['game_clock'] == '6:30'
    assert values['shot_clock'] == f'{start.Config.SHOT_CLOCK:02d}'


def test_get_countdown_status_uses_display_helper():
    start.countdown_running = False
    start.elapsed_time = 30
    start.elapsed_shot = 5
    start.clock_shot = start.Config.SHOT_CLOCK

    client = start.app.test_client()
    resp = client.get('/get_countdown_status')
    body = resp.get_json()

    expected = start.getCountdownDisplayValues()
    assert body['countdown_running'] == expected['countdown_running']
    assert body['elapsed_time'] == expected['remaining_time']
    assert body['elapsed_shot'] == expected['remaining_shot']


def test_pause20_resets_to_foul_clock_when_live_remaining_is_below_threshold():
    start.countdown_running = True
    start.start_time = 70.0
    start.elapsed_time = 0
    start.start_shot = 84.0
    start.elapsed_shot = 0
    start.clock_shot = start.Config.SHOT_CLOCK
    start.remaining_shot = start.Config.SHOT_CLOCK

    with start.app.app_context():
        with (
            patch("start.time.time", return_value=100.0),
            patch.object(start, "ble_send_int") as mock_ble_send_int,
            patch.object(start, "broadcast_refresh_event"),
        ):
            start.pause20()

    assert start.remaining_shot == start.Config.FOUL_CLOCK
    assert start.elapsed_shot == 0
    mock_ble_send_int.assert_called_once_with(str(start.Config.FOUL_CLOCK))


def test_reset20_resets_to_foul_clock_when_cached_remaining_is_stale():
    start.countdown_running = False
    start.elapsed_time = 30
    start.start_shot = 0
    start.elapsed_shot = 15
    start.clock_shot = start.Config.SHOT_CLOCK
    start.remaining_shot = start.Config.SHOT_CLOCK

    with start.app.app_context():
        with (
            patch.object(start, "ble_send_int") as mock_ble_send_int,
            patch.object(start, "broadcast_refresh_event"),
        ):
            start.reset20()

    assert start.countdown_running is True
    assert start.remaining_shot == start.Config.FOUL_CLOCK + 1
    assert start.elapsed_shot == 0
    mock_ble_send_int.assert_called_once_with(str(start.Config.FOUL_CLOCK))


def test_pause20_uses_configured_foul_clock_as_threshold():
    original_foul_clock = start.Config.FOUL_CLOCK
    start.Config.FOUL_CLOCK = 15
    start.countdown_running = False
    start.elapsed_shot = 14
    start.clock_shot = 28
    start.remaining_shot = 28

    try:
        with start.app.app_context():
            with (
                patch.object(start, "ble_send_int") as mock_ble_send_int,
                patch.object(start, "broadcast_refresh_event"),
            ):
                start.pause20()

        assert start.remaining_shot == 15
        mock_ble_send_int.assert_called_once_with("15")
    finally:
        start.Config.FOUL_CLOCK = original_foul_clock


def test_callinterval_is_idempotent_while_interval_is_active():
    start.interval_active = False
    start.countdown_running = True

    client = start.app.test_client()

    with (
        patch.object(start, "pause_countdown") as mock_pause,
        patch.object(start, "stop_timeout"),
        patch("start.time.sleep"),
    ):
        first = client.get('/callinterval')
        second = client.get('/callinterval')

    assert first.status_code == 302
    assert second.status_code == 302
    assert start.interval_active is True
    mock_pause.assert_called_once()


def test_returninterval_only_advances_quarter_once():
    start.interval_active = True
    start.quarter = 2

    client = start.app.test_client()

    with patch.object(start, "stop_countdown"):
        first = client.get('/returninterval')
        second = client.get('/returninterval')

    assert first.status_code == 302
    assert second.status_code == 302
    assert start.quarter == 3
    assert start.interval_active is False
