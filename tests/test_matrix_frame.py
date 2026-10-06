"""Tests for the 0.25s matrix display frame sent to the matrix Arduino over USB serial."""

from unittest.mock import MagicMock, patch

import pytest

import start


@pytest.fixture(autouse=True)
def reset_frame_state():
    previous_scores = (start.scores['Home']['goals'], start.scores['Away']['goals'])
    start.clearExclusionClocks()
    start.countdown_running = False
    start.elapsed_time = 0
    start.elapsed_shot = 0
    start.clock_shot = start.Config.SHOT_CLOCK
    start.quarter = 1
    start.break_label = None
    start.timeout = start.Config.TIMEOUT_TIME
    start.timeoutrunning = False
    start.starttimeout = 0
    start.elapsedtimeout = 0
    start.interval_active = False
    yield
    start.scores['Home']['goals'], start.scores['Away']['goals'] = previous_scores
    start.clearExclusionClocks()
    start.break_label = None
    start.timeoutrunning = False
    start.disconnect_serial()


@pytest.fixture
def client():
    return start.app.test_client()


@pytest.fixture
def no_render():
    with patch.object(start, "render_template", return_value=""):
        yield


def addPausedExclusion(spent: float) -> None:
    start.startExclusionClock(now=0.0)
    start.exclusion_clocks[-1]['spent'] = spent


def setGame(home: int = 3, away: int = 1, quarter: int = 2, elapsed: float = 0, shot_elapsed: float = 0) -> None:
    start.scores['Home']['goals'] = home
    start.scores['Away']['goals'] = away
    start.quarter = quarter
    start.elapsed_time = elapsed
    start.elapsed_shot = shot_elapsed


def test_play_frame_matches_protocol():
    setGame(home=3, away=1, quarter=2, elapsed=145, shot_elapsed=10)
    addPausedExclusion(spent=start.Config.FOUL_CLOCK - 12)
    game_clock = start.Config.GAME_TIME * 30 - 145

    assert start.buildMatrixFrame() == f"03,01,P2,{game_clock},{start.Config.SHOT_CLOCK - 10},12,0"


def test_play_frame_floors_partial_seconds():
    setGame(elapsed=0.4, shot_elapsed=0.4)

    fields = start.buildMatrixFrame().split(",")

    assert fields[3:5] == [f"{start.Config.GAME_TIME * 30 - 1}", f"{start.Config.SHOT_CLOCK - 1}"]


def test_quarter_zero_reports_p1():
    setGame(quarter=0)

    assert start.buildMatrixFrame().split(",")[2] == "P1"


def test_quarter_above_four_reports_p4():
    setGame(quarter=5)

    assert start.buildMatrixFrame().split(",")[2] == "P4"


@pytest.mark.parametrize(
    ("home", "away", "expected"),
    [(0, 0, ["00", "00"]), (7, 12, ["07", "12"]), (150, -2, ["99", "00"])],
)
def test_scores_are_two_digits_and_clamped(home, away, expected):
    setGame(home=home, away=away)

    assert start.buildMatrixFrame().split(",")[:2] == expected


def test_two_exclusion_clocks_fill_both_slots():
    addPausedExclusion(spent=start.Config.FOUL_CLOCK - 12)
    addPausedExclusion(spent=start.Config.FOUL_CLOCK - 5)

    assert start.buildMatrixFrame().split(",")[5:] == ["12", "5"]


def test_no_exclusions_send_zero():
    assert start.buildMatrixFrame().split(",")[5:] == ["0", "0"]


@pytest.mark.parametrize("label", ["TO", "HT", "IN"])
def test_break_replaces_period_and_clock(label):
    setGame(home=3, away=1, quarter=2, elapsed=145)
    start.break_label = label
    start.timeout = 2
    start.elapsedtimeout = 15

    fields = start.buildMatrixFrame().split(",")

    assert fields[2:4] == [label, "45"]


def test_running_break_counts_down_from_start():
    start.break_label = "TO"
    start.timeout = 2
    start.timeoutrunning = True
    start.starttimeout = 1000.0

    with patch("start.time.time", return_value=1020.5):
        fields = start.buildMatrixFrame().split(",")

    assert fields[3] == "39"


def test_break_clock_floors_at_zero():
    start.break_label = "TO"
    start.timeout = 2
    start.elapsedtimeout = 500

    assert start.buildMatrixFrame().split(",")[3] == "0"


def test_timeout_page_sets_to_label(client, no_render):
    client.get('/timeout')

    assert start.break_label == "TO"


@pytest.mark.parametrize(("quarter", "label"), [(1, "IN"), (2, "HT"), (3, "IN")])
def test_runinterval_sets_halftime_or_interval_label(client, no_render, quarter, label):
    start.quarter = quarter

    client.get('/runinterval')

    assert start.break_label == label


def test_runinterval_halftime_uses_halftime_length(client, no_render):
    start.quarter = 2

    client.get('/runinterval')

    assert start.timeout == start.Config.HALFTIME


def test_paused_break_keeps_label(client):
    start.break_label = "IN"

    client.get('/pause_timeout')

    assert start.break_label == "IN"


def test_stop_timeout_clears_label():
    start.break_label = "TO"

    with start.app.app_context():
        start.stop_timeout()

    assert start.break_label is None


def test_returninterval_clears_label(client):
    start.break_label = "HT"
    start.interval_active = True

    with patch.object(start, "stop_countdown"):
        client.get('/returninterval')

    assert start.break_label is None


def test_index_clears_timeout_label(client, no_render):
    start.break_label = "TO"

    client.get('/')

    assert start.break_label is None


def test_index_keeps_interval_label(client, no_render):
    start.break_label = "IN"

    client.get('/')

    assert start.break_label == "IN"


def test_write_matrix_frame_sends_newline_frame_when_connected():
    mock_serial = MagicMock()
    mock_serial.is_open = True
    start._serial_conn = mock_serial

    written = start.writeMatrixFrame()

    assert written is True
    mock_serial.write.assert_called_once_with((start.buildMatrixFrame() + "\n").encode("ascii"))


def test_write_matrix_frame_skips_when_port_closed():
    start.disconnect_serial()
    with patch.object(start, "buildMatrixFrame") as mock_build:
        written = start.writeMatrixFrame()

    assert written is False
    mock_build.assert_not_called()


def test_write_matrix_frame_closes_port_on_write_error():
    mock_serial = MagicMock()
    mock_serial.is_open = True
    mock_serial.write.side_effect = OSError("device removed")
    start._serial_conn = mock_serial

    start.writeMatrixFrame()

    assert start.serial_is_connected() is False


def test_connect_serial_starts_frame_thread():
    mock_serial = MagicMock()
    mock_serial.is_open = True
    with (
        patch("start.serial.Serial", return_value=mock_serial),
        patch("start.time.sleep"),
        patch.object(start, "ensureMatrixFrameThread") as mock_ensure,
    ):
        start.connect_serial("COM3", 9600)

    mock_ensure.assert_called_once()


def test_ensure_matrix_frame_thread_starts_only_once():
    start._matrix_frame_thread = None
    with patch("start.threading.Thread") as thread_ctor:
        thread_ctor.return_value.is_alive.return_value = True
        start.ensureMatrixFrameThread()
        start.ensureMatrixFrameThread()

    thread_ctor.return_value.start.assert_called_once()
    start._matrix_frame_thread = None
