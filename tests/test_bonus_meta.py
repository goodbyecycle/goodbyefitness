"""Tests for the Instagram & Facebook connection."""

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from bonus import auth, meta, store


@pytest.fixture(autouse=True)
def temp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_FILE", tmp_path / "bonus_data.json")
    monkeypatch.setattr(auth, "USERS_FILE", tmp_path / "bonus_users.json")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "bonus_secret.key")
    monkeypatch.setattr(meta, "DATA_FILE", tmp_path / "bonus_meta.json")
    auth.clear_failures()
    yield


def connect(monkeypatch, instagram=True):
    """Put a connected Page in place without touching the network."""
    def fake_graph(path, params=None, token=None):
        assert path == "/me/accounts"
        page = {"id": "page-1", "name": "Goodbye Fitness", "access_token": "page-token",
                "followers_count": 870}
        if instagram:
            page["instagram_business_account"] = {"id": "ig-1", "username": "goodbye_cycle",
                                                  "followers_count": 3120}
        return {"data": [page, {"id": "page-2", "name": "Old Page"}]}

    monkeypatch.setattr(meta, "_graph", fake_graph)
    state = meta.load_state()
    state["token"] = {"value": "user-token", "expiresAt": time.time() + 60 * 86400}
    meta.save_state(state)
    meta.choose_page()


# ─── connecting ───

def test_auth_url_asks_for_the_page_and_instagram_scopes(monkeypatch):
    monkeypatch.setattr(meta, "APP_ID", "app")
    monkeypatch.setattr(meta, "APP_SECRET", "secret")
    url = meta.auth_url("state123")
    assert "pages_read_engagement" in url and "instagram_basic" in url
    assert "state=state123" in url


def test_auth_url_without_credentials_is_refused(monkeypatch):
    monkeypatch.setattr(meta, "APP_ID", "")
    with pytest.raises(meta.NotConfigured):
        meta.auth_url("state123")


def test_the_page_with_instagram_attached_is_chosen(monkeypatch):
    connect(monkeypatch)
    state = meta.status()
    assert state["page"] == "Goodbye Fitness"
    assert state["instagram"] == "goodbye_cycle"
    assert state["otherPages"] == ["Old Page"]
    assert state["connected"] is True


def test_a_page_without_instagram_still_connects(monkeypatch):
    connect(monkeypatch, instagram=False)
    assert meta.status()["connected"] is True
    assert meta.status()["instagram"] is None


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.content = b"{}"

    def json(self):
        return self.payload


def test_an_expired_token_reads_as_not_connected(monkeypatch):
    monkeypatch.setattr(meta.http_requests, "get",
                        lambda *a, **k: FakeResponse({"error": {"code": 190, "message": "Session has expired"}}))
    with pytest.raises(meta.NotConnected):
        meta._graph("/page-1", token="stale")


def test_other_meta_errors_surface_their_message(monkeypatch):
    monkeypatch.setattr(meta.http_requests, "get",
                        lambda *a, **k: FakeResponse({"error": {"code": 100, "message": "Unknown field"}}))
    with pytest.raises(RuntimeError, match="Unknown field"):
        meta._graph("/page-1", token="ok")


def test_status_warns_before_the_sign_in_expires(monkeypatch):
    connect(monkeypatch)
    state = meta.load_state()
    state["token"]["expiresAt"] = time.time() + 3 * 86400
    meta.save_state(state)
    assert meta.status()["expiresInDays"] == 3


def test_disconnect_keeps_the_follower_history(monkeypatch):
    connect(monkeypatch)
    meta.snapshot(today="2026-08-22", counts={"instagram": 3120, "facebook": 870})
    meta.disconnect()
    assert meta.status()["connected"] is False
    assert meta.status()["daysRecorded"] == 1


def test_asking_for_counts_before_connecting_is_refused():
    with pytest.raises(meta.NotConnected):
        meta.current_counts()


# ─── snapshots ───

def test_a_snapshot_records_both_networks():
    meta.snapshot(today="2026-08-22", counts={"instagram": 3305, "facebook": 902})
    state = meta.load_state()
    assert state["days"]["2026-08-22"] == {"instagram": 3305, "facebook": 902}


def test_the_months_closing_figure_is_its_last_snapshot():
    meta.snapshot(today="2026-08-01", counts={"instagram": 3120, "facebook": 870})
    meta.snapshot(today="2026-08-15", counts={"instagram": 3200, "facebook": 880})
    meta.snapshot(today="2026-08-31", counts={"instagram": 3305, "facebook": 902})
    assert meta.closing_count("2026-08", "instagram") == 3305
    assert meta.closing_count("2026-08", "facebook") == 902


def test_a_month_with_no_snapshots_has_no_closing_figure():
    assert meta.closing_count("2026-07", "instagram") is None


def test_a_later_snapshot_the_same_day_replaces_the_earlier_one():
    meta.snapshot(today="2026-08-22", counts={"instagram": 3300, "facebook": 900})
    meta.snapshot(today="2026-08-22", counts={"instagram": 3305, "facebook": 902})
    assert meta.load_state()["days"]["2026-08-22"] == {"instagram": 3305, "facebook": 902}


# ─── syncing ───

def test_sync_fills_both_rows_from_the_snapshots():
    meta.snapshot(today="2026-07-31", counts={"instagram": 3120, "facebook": 870})
    meta.snapshot(today="2026-08-31", counts={"instagram": 3305, "facebook": 902})
    view = meta.sync_month("2026-08", today="2026-09-01")
    rows = {r["key"]: r for r in view["rows"]}
    assert rows["instagram_followers"]["prev"] == 3120
    assert rows["instagram_followers"]["curr"] == 3305
    assert rows["instagram_followers"]["bonus"] == 46.25
    assert rows["facebook_followers"]["bonus"] == 8.00
    assert rows["facebook_followers"]["source"] == "meta"


def test_syncing_the_running_month_takes_a_fresh_snapshot(monkeypatch):
    connect(monkeypatch)
    monkeypatch.setattr(meta, "current_counts", lambda: {"instagram": 3400, "facebook": 910})
    view = meta.sync_month("2026-08", today="2026-08-22")
    row = next(r for r in view["rows"] if r["key"] == "instagram_followers")
    assert row["curr"] == 3400


def test_sync_leaves_a_hand_typed_row_alone():
    meta.snapshot(today="2026-08-31", counts={"instagram": 3305, "facebook": 902})
    store.save_month("2026-08", {"instagram_followers": {"prev": 3120, "curr": 3400}})
    view = meta.sync_month("2026-08", today="2026-09-01")
    row = next(r for r in view["rows"] if r["key"] == "instagram_followers")
    assert row["curr"] == 3400 and "instagram_followers" in view["sync"]["skipped"]


def test_force_overwrites_a_hand_typed_row():
    meta.snapshot(today="2026-08-31", counts={"instagram": 3305, "facebook": 902})
    store.save_month("2026-08", {"instagram_followers": {"prev": 3120, "curr": 3400}})
    view = meta.sync_month("2026-08", force=True, today="2026-09-01")
    row = next(r for r in view["rows"] if r["key"] == "instagram_followers")
    assert row["curr"] == 3305


def test_a_month_with_no_history_reports_what_is_missing():
    view = meta.sync_month("2026-08", today="2026-09-01")
    assert set(view["sync"]["missing"]) == {"instagram_followers", "facebook_followers"}
    row = next(r for r in view["rows"] if r["key"] == "instagram_followers")
    assert row["curr"] is None


def test_a_bad_month_is_refused():
    with pytest.raises(ValueError):
        meta.sync_month("2026-13")


# ─── routes ───

@pytest.fixture
def client(monkeypatch, tmp_path):
    import server
    monkeypatch.setattr(server.bonus_store, "DATA_FILE", store.DATA_FILE)
    monkeypatch.setattr(server.bonus_auth, "USERS_FILE", auth.USERS_FILE)
    monkeypatch.setattr(server.bonus_meta, "DATA_FILE", meta.DATA_FILE)
    server.app.config["TESTING"] = True
    server.app.config["SESSION_COOKIE_SECURE"] = False
    auth.add_user("andy", "correct-horse-battery", "Andy", "admin")
    auth.add_user("jess", "another-good-password", "Jess", "member")
    return server.app.test_client()


def sign_in(client, username="andy", password="correct-horse-battery"):
    res = client.post("/api/bonus/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrfToken"]


def test_meta_routes_need_a_login(client):
    assert client.get("/api/bonus/meta/status").status_code == 401
    assert client.post("/api/bonus/meta/sync", json={}).status_code == 401


def test_only_an_admin_can_connect_or_disconnect(client):
    csrf = sign_in(client, "jess", "another-good-password")
    assert client.get("/api/bonus/meta/connect").status_code == 403
    assert client.post("/api/bonus/meta/disconnect", json={},
                       headers={"X-CSRF-Token": csrf}).status_code == 403


def test_connect_without_server_credentials_says_so(client, monkeypatch):
    import server
    monkeypatch.setattr(server.bonus_meta, "APP_ID", "")
    sign_in(client)
    assert client.get("/api/bonus/meta/connect").status_code == 503


def test_connect_redirects_an_admin_to_facebook(client, monkeypatch):
    import server
    monkeypatch.setattr(server.bonus_meta, "APP_ID", "app")
    monkeypatch.setattr(server.bonus_meta, "APP_SECRET", "secret")
    sign_in(client)
    res = client.get("/api/bonus/meta/connect")
    assert res.status_code == 302
    assert res.headers["Location"].startswith("https://www.facebook.com/")
    assert "instagram_basic" in res.headers["Location"]


def test_syncing_before_connecting_says_so(client):
    csrf = sign_in(client)
    res = client.post("/api/bonus/meta/sync", json={"month": "2026-08"},
                      headers={"X-CSRF-Token": csrf})
    assert res.status_code == 409


def test_the_callback_rejects_a_mismatched_state(client):
    sign_in(client)
    res = client.get("/callback/meta?code=abc&state=wrong")
    assert res.status_code == 302 and "state_mismatch" in res.headers["Location"]


def test_the_nightly_sync_includes_meta_when_connected(monkeypatch):
    import server
    from datetime import datetime
    monkeypatch.setattr(server.bonus_store, "DATA_FILE", store.DATA_FILE)
    monkeypatch.setattr(server.bonus_meta, "status", lambda: {"connected": True})
    monkeypatch.setattr(server.bonus_meta, "sync_month", lambda month: None)
    results = server.run_nightly_sync(today=datetime(2026, 8, 22, 3, 15))
    assert "meta 2026-08 ok" in results


# ─── kept separate ───

def test_only_instagram_can_be_synced():
    meta.snapshot(today="2026-07-31", counts={"instagram": 3120, "facebook": 870})
    meta.snapshot(today="2026-08-31", counts={"instagram": 3305, "facebook": 902})
    view = meta.sync_month("2026-08", today="2026-09-01", networks=["instagram"])
    rows = {r["key"]: r for r in view["rows"]}
    assert rows["instagram_followers"]["curr"] == 3305
    assert rows["facebook_followers"]["curr"] is None
    assert view["sync"]["networks"] == ["instagram"]


def test_only_facebook_can_be_synced():
    meta.snapshot(today="2026-08-31", counts={"instagram": 3305, "facebook": 902})
    view = meta.sync_month("2026-08", today="2026-09-01", networks=["facebook"])
    rows = {r["key"]: r for r in view["rows"]}
    assert rows["facebook_followers"]["curr"] == 902
    assert rows["instagram_followers"]["curr"] is None


def test_an_unknown_network_is_refused():
    with pytest.raises(ValueError):
        meta.sync_month("2026-08", networks=["tiktok"])


def test_status_counts_history_per_network():
    meta.snapshot(today="2026-08-20", counts={"facebook": 870})
    meta.snapshot(today="2026-08-21", counts={"instagram": 3120, "facebook": 880})
    networks = meta.status()["networks"]
    assert networks["facebook"]["daysRecorded"] == 2
    assert networks["instagram"]["daysRecorded"] == 1
    assert networks["instagram"]["latest"] == {"date": "2026-08-21", "count": 3120}


def test_the_route_can_sync_one_network(client, monkeypatch):
    import server
    meta.snapshot(today="2026-08-31", counts={"instagram": 3305, "facebook": 902})
    monkeypatch.setattr(server.bonus_meta, "snapshot", lambda *a, **k: None)
    csrf = sign_in(client)
    res = client.post("/api/bonus/meta/sync",
                      json={"month": "2026-08", "network": "facebook"},
                      headers={"X-CSRF-Token": csrf})
    assert res.status_code == 200
    body = res.get_json()
    assert body["sync"]["networks"] == ["facebook"]
    rows = {r["key"]: r for r in body["rows"]}
    assert rows["facebook_followers"]["curr"] == 902
    assert rows["instagram_followers"]["curr"] is None


def test_the_summary_reports_each_metric_separately():
    meta.snapshot(today="2026-07-31", counts={"instagram": 3120, "facebook": 870})
    meta.snapshot(today="2026-08-31", counts={"instagram": 3305, "facebook": 902})
    view = meta.sync_month("2026-08", today="2026-09-01")
    by_metric = view["summary"]["byMetric"]
    assert by_metric["instagram_followers"] == 46.25
    assert by_metric["facebook_followers"] == 8.00


# ─── choosing which Page to track ───

def multi_page(monkeypatch):
    """Three Pages with Instagram attached — the real portfolio shape."""
    pages = [
        {"id": "page-fitness", "name": "Goodbye fitness", "access_token": "tok-f",
         "followers_count": 0,
         "instagram_business_account": {"id": "ig-f", "username": "goodbyefitness",
                                        "followers_count": 0}},
        {"id": "page-rg", "name": "RG Seamless Gutters LLC", "access_token": "tok-r",
         "followers_count": 940,
         "instagram_business_account": {"id": "ig-r", "username": "rgseamlessguttersnwa",
                                        "followers_count": 1210}},
        {"id": "page-coffee", "name": "Goodbye Coffee Co", "access_token": "tok-c",
         "followers_count": 310,
         "instagram_business_account": {"id": "ig-c", "username": "goodbye_coffee_co",
                                        "followers_count": 480}},
    ]
    monkeypatch.setattr(meta, "_graph",
                        lambda path, params=None, token=None: {"data": pages})
    state = meta.load_state()
    state["token"] = {"value": "user-token", "expiresAt": time.time() + 60 * 86400}
    meta.save_state(state)
    return pages


def test_every_page_is_offered_with_its_follower_counts(monkeypatch):
    multi_page(monkeypatch)
    meta.choose_page()
    listed = meta.list_pages()
    assert [p["name"] for p in listed] == [
        "Goodbye fitness", "RG Seamless Gutters LLC", "Goodbye Coffee Co"]
    rg = next(p for p in listed if p["id"] == "page-rg")
    assert rg["followers"] == 940
    assert rg["instagram"]["username"] == "rgseamlessguttersnwa"
    assert rg["instagram"]["followers"] == 1210


def test_the_picker_never_leaks_page_access_tokens(monkeypatch):
    multi_page(monkeypatch)
    meta.choose_page()
    assert "tok-r" not in json.dumps(meta.list_pages())


def test_exactly_one_page_reads_as_selected(monkeypatch):
    multi_page(monkeypatch)
    meta.choose_page(page_id="page-coffee")
    assert [p["selected"] for p in meta.list_pages()].count(True) == 1
    assert next(p for p in meta.list_pages() if p["selected"])["id"] == "page-coffee"


def test_an_explicit_page_beats_the_automatic_guess(monkeypatch):
    multi_page(monkeypatch)
    meta.choose_page()                       # guesses the first with Instagram
    assert meta.load_state()["page"]["id"] == "page-fitness"
    meta.choose_page(page_id="page-rg")      # admin overrules it
    state = meta.load_state()
    assert state["page"]["id"] == "page-rg"
    assert state["instagram"]["username"] == "rgseamlessguttersnwa"


def test_a_page_from_another_account_is_refused(monkeypatch):
    multi_page(monkeypatch)
    meta.choose_page()
    with pytest.raises(RuntimeError):
        meta.choose_page(page_id="page-somebody-elses")


def test_switching_page_clears_the_other_pages_history(monkeypatch):
    """The recorded counts belong to the old Page.

    Keeping them would make next month's gain a subtraction between two
    unrelated accounts — a plausible-looking number that is simply wrong.
    """
    multi_page(monkeypatch)
    meta.choose_page(page_id="page-coffee")
    state = meta.load_state()
    state["days"] = {"2026-08-01": {"instagram": 480, "facebook": 310}}
    meta.save_state(state)

    meta.choose_page(page_id="page-rg")
    assert meta.load_state()["days"] == {}


def test_reselecting_the_same_page_keeps_its_history(monkeypatch):
    """Reconnecting must not throw away good data."""
    multi_page(monkeypatch)
    meta.choose_page(page_id="page-rg")
    state = meta.load_state()
    state["days"] = {"2026-08-01": {"instagram": 1210, "facebook": 940}}
    meta.save_state(state)

    meta.choose_page(page_id="page-rg")
    assert meta.load_state()["days"] == {"2026-08-01": {"instagram": 1210, "facebook": 940}}


def test_listing_pages_before_connecting_is_refused(monkeypatch):
    monkeypatch.setattr(meta, "_graph",
                        lambda path, params=None, token=None: {"data": []})
    with pytest.raises(meta.NotConnected):
        meta.list_pages()
