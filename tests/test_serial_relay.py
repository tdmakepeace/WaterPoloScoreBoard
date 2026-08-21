"""Tests for USB serial relay alongside BLE scoreboard commands."""

from unittest.mock import MagicMock, patch

import start


def test_serial_send_command_writes_newline_payload():
    mock_serial = MagicMock()
    mock_serial.is_open = True
    start._serial_conn = mock_serial
    try:
        start.serial_send_command("TEST")
    finally:
        start.disconnect_serial()

    mock_serial.write.assert_called_once_with(b"TEST\n")
    mock_serial.flush.assert_called_once()


def test_serial_send_command_noop_when_not_connected():
    start.disconnect_serial()
    with patch("start.serial.Serial") as serial_ctor:
        start.serial_send_command("BUZZER")
    serial_ctor.assert_not_called()


def test_ble_send_command_also_sends_serial():
    with (
        patch.object(start, "_run_ble"),
        patch.object(start, "serial_send_command") as mock_serial,
    ):
        start.ble_send_command("CHANGE")
    mock_serial.assert_called_once_with("CHANGE")


def test_get_device_connection_flags_includes_serial():
    start.Config.SERIAL_PORT = "COM9"
    with patch.object(start, "serial_is_connected", return_value=True):
        flags = start.get_device_connection_flags()
    assert flags["serial"] is True
    assert flags["serial_port"] == "COM9"


def test_connectserial_json_500_when_no_port_configured():
    start.Config.SERIAL_PORT = ""
    start.disconnect_serial()
    client = start.app.test_client()
    resp = client.post("/connectserial", headers={"Accept": "application/json"})
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["status"] == "error"
    assert "No COM port" in body["message"]


def test_connectserial_json_200_when_port_opens():
    start.Config.SERIAL_PORT = "COM3"
    with patch.object(start, "connect_serial", return_value="") as mock_connect:
        client = start.app.test_client()
        resp = client.post("/connectserial", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"
    mock_connect.assert_called_once()


def test_connectserial_uses_port_query_param():
    start.Config.SERIAL_PORT = ""
    with patch.object(start, "connect_serial", return_value="") as mock_connect:
        client = start.app.test_client()
        resp = client.post(
            "/connectserial?port=COM7",
            headers={"Accept": "application/json"},
        )
    assert resp.status_code == 200
    assert start.Config.SERIAL_PORT == "COM7"
    mock_connect.assert_called_once()


def test_save_persists_serial_port_in_config():
    client = start.app.test_client()
    with patch.object(start, "try_autoconnect_serial") as mock_autoconnect:
        client.post(
            "/save",
            data={
                "game": "13",
                "interval": "4",
                "half": "4",
                "Location": "Pool",
                "Home": "Home",
                "Away": "Away",
                "shotclock": "28",
                "majors": "3",
                "serial_port": "COM5",
            },
            follow_redirects=False,
        )
    assert start.Config.SERIAL_PORT == "COM5"
    mock_autoconnect.assert_called_once()


def test_save_clears_serial_when_port_empty():
    start.Config.SERIAL_PORT = "COM5"
    client = start.app.test_client()
    with patch.object(start, "disconnect_serial") as mock_disconnect:
        client.post(
            "/save",
            data={
                "game": "13",
                "interval": "4",
                "half": "4",
                "Location": "Pool",
                "Home": "Home",
                "Away": "Away",
                "shotclock": "28",
                "majors": "3",
                "serial_port": "",
            },
            follow_redirects=False,
        )
    assert start.Config.SERIAL_PORT == ""
    mock_disconnect.assert_called_once()


def test_comports_returns_rescanned_ports():
    start.Config.SERIAL_PORT = "COM5"
    fake_ports = [
        {"device": "COM5", "description": "USB Serial"},
        {"device": "COM7", "description": "LoRa Master"},
    ]
    with patch.object(start, "list_com_ports", return_value=fake_ports) as mock_list:
        client = start.app.test_client()
        resp = client.get("/comports", headers={"Accept": "application/json"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["selected"] == "COM5"
    assert body["ports"] == fake_ports
    mock_list.assert_called_once()


def test_list_com_ports_skips_blank_devices():
    entry_ok = MagicMock(device="COM3", description="USB-SERIAL CH340")
    entry_blank = MagicMock(device="  ", description="ignored")
    with patch.object(start, "list_ports") as mock_list_ports:
        mock_list_ports.comports.return_value = [entry_ok, entry_blank]
        ports = start.list_com_ports()

    assert ports == [{"device": "COM3", "description": "USB-SERIAL CH340"}]


def test_connect_serial_opens_port_and_sends_test():
    mock_serial = MagicMock()
    mock_serial.is_open = True
    start.disconnect_serial()
    with (
        patch("start.serial.Serial", return_value=mock_serial) as serial_ctor,
        patch("start.time.sleep") as mock_sleep,
    ):
        error = start.connect_serial("COM3", 9600)

    assert error == ""
    serial_ctor.assert_called_once_with()
    mock_serial.open.assert_called_once()
    mock_sleep.assert_called()
    mock_serial.write.assert_called_with(b"TEST\n")
    assert start.serial_is_connected()
    start.disconnect_serial()


def test_connect_serial_keeps_port_if_test_write_fails():
    mock_serial = MagicMock()
    mock_serial.is_open = True
    mock_serial.write.side_effect = OSError("device not functioning")
    start.disconnect_serial()
    with patch("start.serial.Serial", return_value=mock_serial), patch("start.time.sleep"):
        error = start.connect_serial("COM5")

    assert error == ""
    assert start.serial_is_connected()
    start.disconnect_serial()


def test_connect_serial_permission_error_mentions_serial_monitor():
    start.disconnect_serial()
    with patch("start.serial.Serial") as serial_ctor:
        conn = MagicMock()
        conn.open.side_effect = PermissionError("Access is denied.")
        serial_ctor.return_value = conn
        error = start.connect_serial("COM4")

    assert "Access is denied" in error
    assert "Serial Monitor" in error
    assert not start.serial_is_connected()