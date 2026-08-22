"""Tests for website traffic counting and the unattended nightly sync."""

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from bonus import auth, google_reviews as google, meta, store, traffic, youtube


@pytest.fixture(autouse=True)
def temp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_FILE", tmp_path / "bonus_data.json")
    monkeypatch.setattr(auth, "USERS_FILE", tmp_path / "bonus_users.json")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "bonus_secret.key")
    monkeypatch.setattr(youtube, "TOKENS_FILE", tmp_path / "bonus_youtube.json")
    monkeypatch.setattr(meta, "DATA_FILE", tmp_path / "bonus_meta.json")
    monkeypatch.setattr(google, "DATA_FILE", tmp_path / "bonus_google.json")
    monkeypatch.setattr(traffic, "DATA_FILE", tmp_path / "bonus_traffic.json")
    auth.clear_failures()
    yield


# ─── what counts ───

def test_a_normal_page_view_counts():
    assert traffic.countable("/", "Mozilla/5.0 (iPhone)") is True
    assert traffic.countable("/app", "Mozilla/5.0") is True


def test_the_tracker_and_the_api_are_not_website_traffic():
    assert traffic.countable("/bonus", "Mozilla/5.0") is False
    assert traffic.countable("/api/bonus/months", "Mozilla/5.0") is False
    assert traffic.countable("/callback/youtube", "Mozilla/5.0") is False


def test_assets_are_not_page_views():
    for path in ("/style.css", "/app.js", "/g-icon.png", "/favicon.ico"):
        assert traffic.countable(path, "Mozilla/5.0") is False


def test_bots_are_ignored():
    for agent in ("Googlebot/2.1", "python-requests/2.31", "HeadlessChrome/120", "curl/8.4"):
        assert traffic.countable("/", agent) is False


# ─── counting ───

def test_the_same_visitor_counts_once_a_day():
    for _ in range(4):
        traffic.record("/", "1.2.3.4", "Mozilla/5.0", today="2026-08-22")
    day = traffic.month_totals("2026-08")
    assert day["views"] == 4 and day["visitors"] == 1


def test_different_visitors_count_separately():
    traffic.record("/", "1.2.3.4", "Mozilla/5.0", today="2026-08-22")
    traffic.record("/", "5.6.7.8", "Mozilla/5.0", today="2026-08-22")
    assert traffic.month_totals("2026-08")["visitors"] == 2


def test_a_visitor_counts_again_the_next_day():
    traffic.record("/", "1.2.3.4", "Mozilla/5.0", today="2026-08-22")
    traffic.record("/", "1.2.3.4", "Mozilla/5.0", today="2026-08-23")
    totals = traffic.month_totals("2026-08")
    assert totals["visitors"] == 2 and totals["days"] == 2


def test_only_the_asked_for_month_is_counted():
    traffic.record("/", "1.2.3.4", "Mozilla/5.0", today="2026-07-31")
    traffic.record("/", "1.2.3.4", "Mozilla/5.0", today="2026-08-01")
    assert traffic.month_totals("2026-08")["visitors"] == 1
    assert traffic.month_totals("2026-07")["visitors"] == 1


def test_no_raw_address_is_ever_stored():
    traffic.record("/", "1.2.3.4", "Mozilla/5.0 (iPhone)", today="2026-08-22")
    stored = traffic.DATA_FILE.read_text()
    assert "1.2.3.4" not in stored
    assert "iPhone" not in stored


def test_yesterdays_hashes_are_dropped_with_their_salt():
    traffic.record("/", "1.2.3.4", "Mozilla/5.0", today="2026-08-22")
    traffic.record("/", "1.2.3.4", "Mozilla/5.0", today="2026-08-23")
    assert list(traffic._read()["hashes"]) == ["2026-08-23"]


def test_counts_survive_a_restart():
    traffic.record("/", "1.2.3.4", "Mozilla/5.0", today="2026-08-22")
    assert traffic.month_totals("2026-08")["visitors"] == 1


def test_every_visit_is_on_disk_immediately():
    """No in-memory buffer: a second process (or a restart) sees every count."""
    traffic.record("/", "1.1.1.1", "Mozilla/5.0", today="2026-08-22")
    traffic.record("/", "1.1.1.1", "Mozilla/5.0", today="2026-08-22")
    traffic.record("/", "2.2.2.2", "Mozilla/5.0", today="2026-08-22")
    on_disk = traffic._read()["days"]["2026-08-22"]
    assert on_disk == {"views": 3, "visitors": 2}


def test_counting_since_is_the_first_day_seen():
    traffic.record("/", "1.1.1.1", "Mozilla/5.0", today="2026-08-20")
    traffic.record("/", "1.1.1.1", "Mozilla/5.0", today="2026-08-22")
    assert traffic.status()["countingSince"] == "2026-08-20"


# ─── syncing into the tracker ───

def test_sync_writes_the_visitor_count_into_the_month():
    for address in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
        traffic.record("/", address, "Mozilla/5.0", today="2026-08-22")
    view = traffic.sync_month("2026-08")
    row = next(r for r in view["rows"] if r["key"] == "website_visitors")
    assert row["curr"] == 3 and row["source"] == "website"
    assert view["sync"]["visitors"] == 3


def test_the_website_row_pays_nothing_until_a_rate_is_set():
    traffic.record("/", "1.1.1.1", "Mozilla/5.0", today="2026-08-22")
    view = traffic.sync_month("2026-08")
    row = next(r for r in view["rows"] if r["key"] == "website_visitors")
    assert row["rate"] == 0.00 and row["bonus"] == 0.00

    store.set_rates({"website_visitors": 0.10})
    row = next(r for r in store.compute_month("2026-08")["rows"] if r["key"] == "website_visitors")
    assert row["bonus"] == 0.10


def test_sync_leaves_a_hand_typed_visitor_count_alone():
    traffic.record("/", "1.1.1.1", "Mozilla/5.0", today="2026-08-22")
    store.save_month("2026-08", {"website_visitors": {"prev": 0, "curr": 900}})
    view = traffic.sync_month("2026-08")
    row = next(r for r in view["rows"] if r["key"] == "website_visitors")
    assert row["curr"] == 900 and view["sync"]["skipped"] == ["website_visitors"]


def test_force_overwrites_a_hand_typed_visitor_count():
    traffic.record("/", "1.1.1.1", "Mozilla/5.0", today="2026-08-22")
    store.save_month("2026-08", {"website_visitors": {"prev": 0, "curr": 900}})
    view = traffic.sync_month("2026-08", force=True)
    row = next(r for r in view["rows"] if r["key"] == "website_visitors")
    assert row["curr"] == 1


# ─── nightly sync ───

def test_nightly_sync_covers_this_month(monkeypatch):
    import server
    monkeypatch.setattr(server.bonus_store, "DATA_FILE", store.DATA_FILE)
    traffic.record("/", "1.1.1.1", "Mozilla/5.0", today="2026-08-22")
    results = server.run_nightly_sync(today=datetime(2026, 8, 22, 3, 15))
    assert results == ["website 2026-08 ok"]
    row = next(r for r in store.compute_month("2026-08")["rows"] if r["key"] == "website_visitors")
    assert row["curr"] == 1


def test_early_in_the_month_it_also_finishes_the_previous_one(monkeypatch):
    import server
    monkeypatch.setattr(server.bonus_store, "DATA_FILE", store.DATA_FILE)
    results = server.run_nightly_sync(today=datetime(2026, 9, 2, 3, 15))
    assert "website 2026-09 ok" in results and "website 2026-08 ok" in results


def test_a_failing_sync_is_logged_not_raised(monkeypatch):
    import server

    def explode(*args, **kwargs):
        raise RuntimeError("YouTube said no")

    monkeypatch.setattr(server.bonus_store, "DATA_FILE", store.DATA_FILE)
    monkeypatch.setattr(server.bonus_youtube, "status", lambda: {"connected": True})
    monkeypatch.setattr(server.bonus_youtube, "sync_month", explode)
    results = server.run_nightly_sync(today=datetime(2026, 8, 22, 3, 15))
    assert any("youtube 2026-08 failed: YouTube said no" in r for r in results)


def test_the_last_nightly_run_is_remembered(monkeypatch):
    import server
    monkeypatch.setattr(server.bonus_store, "DATA_FILE", store.DATA_FILE)
    server.run_nightly_sync(today=datetime(2026, 8, 22, 3, 15))
    last = store.get_autosync()
    assert last["at"].startswith("2026-08-22T03:15") and last["results"]


def test_rescheduling_the_sms_leaves_the_nightly_sync_alone():
    import server
    server.scheduler.add_job(lambda: None, "cron", hour=3, id="bonus_nightly_sync",
                             replace_existing=True)
    server.reschedule_sms({"msgTime": "none"})
    assert server.scheduler.get_job("bonus_nightly_sync") is not None


# ─── routes ───

@pytest.fixture
def client(monkeypatch, tmp_path):
    import server
    monkeypatch.setattr(server.bonus_store, "DATA_FILE", store.DATA_FILE)
    monkeypatch.setattr(server.bonus_auth, "USERS_FILE", auth.USERS_FILE)
    monkeypatch.setattr(server.bonus_traffic, "DATA_FILE", traffic.DATA_FILE)
    server.app.config["TESTING"] = True
    server.app.config["SESSION_COOKIE_SECURE"] = False
    auth.add_user("jess", "another-good-password", "Jess", "member")
    return server.app.test_client()


def sign_in(client):
    res = client.post("/api/bonus/login", json={"username": "jess", "password": "another-good-password"})
    return res.get_json()["csrfToken"]


def test_website_routes_need_a_login(client):
    assert client.get("/api/bonus/website/status").status_code == 401
    assert client.post("/api/bonus/website/sync", json={}).status_code == 401
    assert client.get("/api/bonus/autosync").status_code == 401


def test_a_member_can_sync_the_website_row(client):
    csrf = sign_in(client)
    traffic.record("/", "1.1.1.1", "Mozilla/5.0", today="2026-08-22")
    res = client.post("/api/bonus/website/sync", json={"month": "2026-08"},
                      headers={"X-CSRF-Token": csrf})
    assert res.status_code == 200 and res.get_json()["sync"]["visitors"] == 1


def test_autosync_status_reports_the_schedule(client):
    sign_in(client)
    body = client.get("/api/bonus/autosync").get_json()
    assert body["enabled"] is True and body["at"] == "03:15"


def test_visiting_the_public_site_is_counted(client):
    client.get("/", headers={"User-Agent": "Mozilla/5.0"})
    csrf = sign_in(client)
    month = datetime.now().strftime("%Y-%m")
    res = client.post("/api/bonus/website/sync", json={"month": month},
                      headers={"X-CSRF-Token": csrf})
    assert res.get_json()["sync"]["visitors"] >= 1
