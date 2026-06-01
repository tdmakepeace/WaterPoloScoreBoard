"""Tests for BLE manual connect / reconnect HTTP error reporting."""

from unittest.mock import MagicMock, patch

import pytest

import start


def _noop_run_ble_coro(coro, timeout=120.0, reraise=False):
    """Stand in for _run_ble_coro without running the real loop; close the coroutine to avoid warnings."""
    coro.close()
    return None


@pytest.fixture
def clean_ble_lists():
    prev_clients = list(start.ble_clients)
    prev_names = list(start.ble_client_names)
    prev_addrs = list(start.ble_client_addresses)
    start.ble_clients.clear()
    start.ble_client_names.clear()
    start.ble_client_addresses.clear()
    yield
    start.ble_clients[:] = prev_clients
    start.ble_client_names[:] = prev_names
    start.ble_client_addresses[:] = prev_addrs


def test_ble_any_live_client_respects_is_connected(clean_ble_lists):
    dead = MagicMock()
    dead.is_connected = False
    live = MagicMock()
    live.is_connected = True
    start.ble_clients.extend([dead, live])
    assert start.ble_any_live_client() is True

    start.ble_clients.clear()
    start.ble_clients.extend([dead])
    assert start.ble_any_live_client() is False


def test_connectble_json_500_when_no_live_clients(clean_ble_lists):
    with (
        patch.object(start, "_run_ble_coro", _noop_run_ble_coro),
        patch.object(start, "ble_send_command"),
        patch.object(start, "sleep", lambda s: None),
    ):
        client = start.app.test_client()
        resp = client.post("/connectble", headers={"Accept": "application/json"})
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["status"] == "error"
    assert "No BLE devices" in body["message"]


def test_connectble_json_200_when_live_client(clean_ble_lists):
    mock_client = MagicMock()
    mock_client.is_connected = True
    with (
        patch.object(start, "_run_ble_coro", _noop_run_ble_coro),
        patch.object(start, "ble_send_command"),
        patch.object(start, "sleep", lambda s: None),
    ):
        start.ble_clients.append(mock_client)
        start.ble_client_names.append("WaterPolo_1")
        start.ble_client_addresses.append("00:11:22:33:44:55")
        client = start.app.test_client()
        resp = client.post("/connectble", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"


def test_reconnectble_500_when_no_live_clients(clean_ble_lists):
    with (
        patch.object(start, "_run_ble_coro", _noop_run_ble_coro),
        patch.object(start, "ble_send_command"),
    ):
        client = start.app.test_client()
        resp = client.get("/reconnectble")
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["status"] == "error"
    assert "flags" in body
