"""Tests for countdown display helpers."""

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
