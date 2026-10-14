"""Tests for the settings page time / shot clock choices and defaults."""

from unittest.mock import patch

import pytest

import start

# Captured at collection, before other tests post /save and change Config.
STARTUP_SETTINGS = {
    name: getattr(start.Config, name) for name in ("GAME_TIME", "INTERVAL_TIME", "HALFTIME", "SHOT_CLOCK")
}


@pytest.fixture
def restore_timing_config():
    previous = (start.Config.GAME_TIME, start.Config.INTERVAL_TIME, start.Config.HALFTIME, start.Config.SHOT_CLOCK)
    yield
    start.Config.GAME_TIME, start.Config.INTERVAL_TIME, start.Config.HALFTIME, start.Config.SHOT_CLOCK = previous


def postSettings(client, **overrides: str):
    data = {
        "game": "16",
        "interval": "4",
        "half": "4",
        "Location": "Pool",
        "Home": "Home",
        "Away": "Away",
        "shotclock": "28",
        "majors": "3",
        "serial_port": "",
    }
    data.update(overrides)
    with patch.object(start, "disconnect_serial"), patch.object(start, "try_autoconnect_serial"):
        return client.post("/save", data=data, follow_redirects=False)


@pytest.mark.parametrize(
    ("setting", "expected"),
    [("GAME_TIME", 16), ("INTERVAL_TIME", 4), ("HALFTIME", 4), ("SHOT_CLOCK", 28)],
)
def test_defaults(setting, expected):
    assert STARTUP_SETTINGS[setting] == expected


@pytest.mark.parametrize(
    ("options", "first", "last"),
    [
        ("GAME_TIME_OPTIONS", "5:00", "10:00"),
        ("INTERVAL_TIME_OPTIONS", "0:30", "3:00"),
        ("HALFTIME_OPTIONS", "1:00", "5:00"),
    ],
)
def test_time_option_ranges(options, first, last):
    labels = [label for _, label in start.buildHalfMinuteOptions(getattr(start.Config, options))]

    assert (labels[0], labels[-1]) == (first, last)


def test_game_time_options_step_every_30_seconds():
    assert start.Config.GAME_TIME_OPTIONS == tuple(range(10, 21))


def test_shot_clock_options():
    assert start.Config.SHOT_CLOCK_OPTIONS == (24, 26, 28, 30)


@pytest.mark.parametrize(("units", "label"), [(1, "0:30"), (4, "2:00"), (17, "8:30"), (20, "10:00")])
def test_format_half_minutes(units, label):
    assert start.formatHalfMinutes(units) == label


def test_settings_page_preselects_current_values(restore_timing_config):
    start.Config.GAME_TIME = 17
    start.Config.SHOT_CLOCK = 26
    with patch.object(start, "list_com_ports", return_value=[]):
        body = start.app.test_client().get("/settings").get_data(as_text=True)

    assert '<option value="17" selected>8:30 Min</option>' in body and '<option value="26" selected>26</option>' in body


def test_save_accepts_allowed_values(restore_timing_config):
    postSettings(start.app.test_client(), game="20", interval="1", half="10", shotclock="24")

    assert (start.Config.GAME_TIME, start.Config.INTERVAL_TIME, start.Config.HALFTIME, start.Config.SHOT_CLOCK) == (
        20,
        1,
        10,
        24,
    )


@pytest.mark.parametrize(
    ("field", "value", "setting"),
    [
        ("game", "9", "GAME_TIME"),
        ("game", "21", "GAME_TIME"),
        ("interval", "7", "INTERVAL_TIME"),
        ("half", "1", "HALFTIME"),
        ("shotclock", "25", "SHOT_CLOCK"),
        ("shotclock", "abc", "SHOT_CLOCK"),
    ],
)
def test_save_rejects_values_outside_choices(restore_timing_config, field, value, setting):
    before = getattr(start.Config, setting)

    postSettings(start.app.test_client(), **{field: value})

    assert getattr(start.Config, setting) == before
