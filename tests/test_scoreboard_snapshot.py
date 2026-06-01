"""Tests for live scoreboard snapshot API."""

import start


def test_get_scoreboard_snapshot_returns_scores():
    start.scores = {'Home': {'goals': 3, 'majors': 1}, 'Away': {'goals': 2, 'majors': 0}}
    start.periodscores = {
        'Home': {'goals1': 1, 'goals2': 1, 'goals3': 1, 'goals4': 0, 'majors1': 1, 'majors2': 0, 'majors3': 0, 'majors4': 0},
        'Away': {'goals1': 0, 'goals2': 2, 'goals3': 0, 'goals4': 0, 'majors1': 0, 'majors2': 0, 'majors3': 0, 'majors4': 0},
    }
    start.quarter = 2
    start.hometimeoutv = 1
    start.awaytimeoutv = 0

    client = start.app.test_client()
    resp = client.get('/get_scoreboard_snapshot')
    body = resp.get_json()

    assert resp.status_code == 200
    assert body['home_goals'] == 3
    assert body['away_goals'] == 2
    assert body['quarter'] == 2
    assert body['periodscores']['Home']['goals2'] == 1
    assert body['periodscores']['Away']['goals2'] == 2
    assert 'game_clock' in body
    assert 'shot_clock' in body
