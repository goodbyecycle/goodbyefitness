"""Tests for the YouTube connection — sync mapping, overwrite rules, routes."""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from bonus import auth, store, youtube


@pytest.fixture(autouse=True)
def temp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_FILE", tmp_path / "bonus_data.json")
    monkeypatch.setattr(auth, "USERS_FILE", tmp_path / "bonus_users.json")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "bonus_secret.key")
    monkeypatch.setattr(youtube, "TOKENS_FILE", tmp_path / "bonus_youtube.json")
    auth.clear_failures()
    yield


def report(net_subs=148, hours=330.0, month="2026-08", through="2026-08-31"):
    """A stand-in for what the YouTube Analytics API hands back."""
    return {
        "month": month,
        "start": month + "-01",
        "end": through,
        "days": [{"date": month + "-01", "gained": net_subs, "lost": 0, "minutes": hours * 60}],
        "netSubscribers": net_subs,
        "hoursWatched": hours,
    }


# ─── sync ───

def test_sync_fills_both_youtube_rows():
    store.save_month("2026-07", {"youtube_subs": {"prev": 1100, "curr": 1240},
                                 "youtube_hours": {"prev": 1900, "curr": 2150}})
    view = youtube.sync_month("2026-08", report=report())
    rows = {r["key"]: r for r in view["rows"]}
    assert rows["youtube_subs"]["prev"] == 1240      # carried from July
    assert rows["youtube_subs"]["curr"] == 1388      # + the exact net gain
    assert rows["youtube_subs"]["bonus"] == 74.00
    assert rows["youtube_hours"]["curr"] == 330.0
    assert view["sync"]["netSubscribers"] == 148


def test_synced_rows_are_marked_as_such():
    youtube.sync_month("2026-08", report=report())
    rows = {r["key"]: r for r in store.compute_month("2026-08")["rows"]}
    assert rows["youtube_subs"]["source"] == "youtube"
    assert rows["instagram_followers"]["source"] == "manual"


def test_first_sync_anchors_on_the_rounded_public_count():
    youtube.save_tokens({"refresh_token": "x", "channel": {"approxSubscribers": 1390}})
    view = youtube.sync_month("2026-08", report=report())
    row = next(r for r in view["rows"] if r["key"] == "youtube_subs")
    assert row["prev"] == 1242 and row["curr"] == 1390
    assert view["sync"]["anchoredFrom"] == "rounded public count"


def test_sync_leaves_a_hand_typed_row_alone():
    store.save_month("2026-08", {"youtube_subs": {"prev": 1240, "curr": 1400}})
    view = youtube.sync_month("2026-08", report=report())
    row = next(r for r in view["rows"] if r["key"] == "youtube_subs")
    assert row["curr"] == 1400
    assert "youtube_subs" in view["sync"]["skipped"]


def test_force_overwrites_a_hand_typed_row():
    store.save_month("2026-08", {"youtube_subs": {"prev": 1240, "curr": 1400}})
    view = youtube.sync_month("2026-08", force=True, report=report())
    row = next(r for r in view["rows"] if r["key"] == "youtube_subs")
    assert row["curr"] == 1388
    assert view["sync"]["skipped"] == []


def test_a_second_sync_updates_the_same_month():
    youtube.sync_month("2026-08", report=report(net_subs=100, hours=120.0))
    view = youtube.sync_month("2026-08", report=report(net_subs=148, hours=330.0))
    rows = {r["key"]: r for r in view["rows"]}
    assert rows["youtube_hours"]["curr"] == 330.0
    assert rows["youtube_subs"]["curr"] - rows["youtube_subs"]["prev"] == 148


def test_sync_records_when_it_last_ran():
    youtube.sync_month("2026-08", report=report(through="2026-08-22"))
    assert youtube.status()["lastSync"]["through"] == "2026-08-22"


# ─── payout basis ───

def test_hours_can_be_paid_on_the_months_own_total():
    youtube.sync_month("2026-08", report=report(hours=330.0))
    on_gain = next(r for r in store.compute_month("2026-08")["rows"] if r["key"] == "youtube_hours")
    assert on_gain["bonus"] == 330.00      # no previous month, so gain == total here

    store.save_month("2026-09", {}, source="manual")
    youtube.sync_month("2026-09", report=report(hours=400.0, month="2026-09", through="2026-09-30"))
    gain_row = next(r for r in store.compute_month("2026-09")["rows"] if r["key"] == "youtube_hours")
    assert gain_row["bonus"] == 70.00      # paid on the 70-hour increase

    store.set_bases({"youtube_hours": "total"})
    total_row = next(r for r in store.compute_month("2026-09")["rows"] if r["key"] == "youtube_hours")
    assert total_row["bonus"] == 400.00    # paid on all 400 hours
    assert total_row["basis"] == "total"


def test_basis_must_be_one_of_the_two():
    with pytest.raises(ValueError):
        store.set_bases({"youtube_hours": "vibes"})
    with pytest.raises(ValueError):
        store.set_bases({"nope": "gain"})


# ─── month bounds ───

def test_month_never_runs_past_today():
    start, end = youtube.month_bounds("2026-08", today=date(2026, 8, 22))
    assert start.isoformat() == "2026-08-01" and end.isoformat() == "2026-08-22"


def test_a_finished_month_uses_its_last_day():
    _, end = youtube.month_bounds("2026-07", today=date(2026, 8, 22))
    assert end.isoformat() == "2026-07-31"


def test_a_month_that_hasnt_started_is_refused():
    with pytest.raises(ValueError):
        youtube.month_bounds("2026-12", today=date(2026, 8, 22))


# ─── connection state ───

def test_status_reports_not_configured_and_not_connected(monkeypatch):
    monkeypatch.setattr(youtube, "CLIENT_ID", "")
    monkeypatch.setattr(youtube, "CLIENT_SECRET", "")
    state = youtube.status()
    assert state["configured"] is False and state["connected"] is False


def test_auth_url_carries_the_offline_scopes(monkeypatch):
    monkeypatch.setattr(youtube, "CLIENT_ID", "test-client")
    monkeypatch.setattr(youtube, "CLIENT_SECRET", "test-secret")
    url = youtube.auth_url("state123")
    assert "yt-analytics.readonly" in url
    assert "access_type=offline" in url and "state=state123" in url


def test_auth_url_without_credentials_is_refused(monkeypatch):
    monkeypatch.setattr(youtube, "CLIENT_ID", "")
    with pytest.raises(youtube.NotConfigured):
        youtube.auth_url("state123")


def test_asking_for_a_token_before_connecting_is_refused():
    with pytest.raises(youtube.NotConnected):
        youtube.access_token()


def test_disconnect_removes_the_stored_tokens():
    youtube.save_tokens({"refresh_token": "x"})
    youtube.disconnect()
    assert youtube.status()["connected"] is False


def test_tokens_are_written_private():
    youtube.save_tokens({"refresh_token": "x"})
    assert oct(youtube.TOKENS_FILE.stat().st_mode)[-3:] == "600"


# ─── routes ───

@pytest.fixture
def client(monkeypatch, tmp_path):
    import server
    monkeypatch.setattr(server.bonus_store, "DATA_FILE", tmp_path / "bonus_data.json")
    monkeypatch.setattr(server.bonus_auth, "USERS_FILE", tmp_path / "bonus_users.json")
    monkeypatch.setattr(server.bonus_youtube, "TOKENS_FILE", tmp_path / "bonus_youtube.json")
    server.app.config["TESTING"] = True
    server.app.config["SESSION_COOKIE_SECURE"] = False
    auth.add_user("andy", "correct-horse-battery", "Andy", "admin")
    auth.add_user("jess", "another-good-password", "Jess", "member")
    return server.app.test_client()


def sign_in(client, username, password):
    res = client.post("/api/bonus/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrfToken"]


def test_youtube_routes_need_a_login(client):
    assert client.get("/api/bonus/youtube/status").status_code == 401
    assert client.post("/api/bonus/youtube/sync", json={"month": "2026-08"}).status_code == 401


def test_only_an_admin_can_connect_or_disconnect(client):
    csrf = sign_in(client, "jess", "another-good-password")
    assert client.get("/api/bonus/youtube/connect").status_code == 403
    assert client.post("/api/bonus/youtube/disconnect", json={},
                       headers={"X-CSRF-Token": csrf}).status_code == 403


def test_connect_without_server_credentials_says_so(client, monkeypatch):
    import server
    monkeypatch.setattr(server.bonus_youtube, "CLIENT_ID", "")
    sign_in(client, "andy", "correct-horse-battery")
    res = client.get("/api/bonus/youtube/connect")
    assert res.status_code == 503


def test_syncing_before_connecting_says_so(client):
    csrf = sign_in(client, "andy", "correct-horse-battery")
    res = client.post("/api/bonus/youtube/sync", json={"month": "2026-08"},
                      headers={"X-CSRF-Token": csrf})
    assert res.status_code == 409
    assert "not connected" in res.get_json()["error"].lower()


def test_the_oauth_callback_rejects_a_mismatched_state(client):
    sign_in(client, "andy", "correct-horse-battery")
    res = client.get("/callback/youtube?code=abc&state=not-the-one")
    assert res.status_code == 302 and "state_mismatch" in res.headers["Location"]


def test_only_an_admin_can_change_the_basis(client):
    csrf = sign_in(client, "jess", "another-good-password")
    assert client.post("/api/bonus/bases", json={"bases": {"youtube_hours": "total"}},
                       headers={"X-CSRF-Token": csrf}).status_code == 403
    csrf = sign_in(client, "andy", "correct-horse-battery")
    res = client.post("/api/bonus/bases", json={"bases": {"youtube_hours": "total"}},
                      headers={"X-CSRF-Token": csrf})
    assert res.get_json()["bases"]["youtube_hours"] == "total"


def test_connect_redirects_an_admin_to_google(client, monkeypatch):
    import server
    monkeypatch.setattr(server.bonus_youtube, "CLIENT_ID", "test-client")
    monkeypatch.setattr(server.bonus_youtube, "CLIENT_SECRET", "test-secret")
    sign_in(client, "andy", "correct-horse-battery")
    res = client.get("/api/bonus/youtube/connect")
    assert res.status_code == 302
    assert res.headers["Location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "yt-analytics.readonly" in res.headers["Location"]
