"""Tests for BLE shot-clock integer string normalization."""

import pytest

from start import normalize_ble_int_payload


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (14.567890123456, "14"),
        (0.0, "0"),
        (28, "28"),
        ("28", "28"),
        ("14.9", "14"),
    ],
)
def test_normalize_ble_int_payload_integer_strings(raw, expected):
    assert normalize_ble_int_payload(raw) == expected
