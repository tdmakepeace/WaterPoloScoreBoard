"""Tests for roster CSV filename sanitization and export endpoints."""

import start


def test_safe_roster_filename_default_stem():
    assert start._safeRosterFilename("") == "home_roster.csv"
    assert start._safeRosterFilename("  ", "away_roster") == "away_roster.csv"


def test_safe_roster_filename_preserves_requested_basename():
    assert start._safeRosterFilename("My_Team.csv") == "My_Team.csv"
    assert start._safeRosterFilename("Away.csv", "away_roster") == "Away.csv"


def test_exportawayplayers_success(monkeypatch):
    def fake_write_text(self, data, encoding="utf-8", newline=""):
        return len(data)

    monkeypatch.setattr(start.Path, "write_text", fake_write_text)
    client = start.app.test_client()
    resp = client.post(
        "/exportawayplayers/u1",
        json={"csv": "1,Ada\n", "filename": "My_Away.csv"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["filename"] == "My_Away.csv"
    assert body["user_id"] == "u1"


def test_exportawayplayers_empty_csv(monkeypatch):
    def fake_write_text(self, data, encoding="utf-8", newline=""):
        raise AssertionError("write_text should not be called for empty CSV")

    monkeypatch.setattr(start.Path, "write_text", fake_write_text)
    client = start.app.test_client()
    resp = client.post(
        "/exportawayplayers/u1",
        json={"csv": "   ", "filename": "x.csv"},
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False
