"""Tests for the Google reviews connection."""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from bonus import auth, google_reviews as google, store


@pytest.fixture(autouse=True)
def temp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_FILE", tmp_path / "bonus_data.json")
    monkeypatch.setattr(auth, "USERS_FILE", tmp_path / "bonus_users.json")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "bonus_secret.key")
    monkeypatch.setattr(google, "DATA_FILE", tmp_path / "bonus_google.json")
    auth.clear_failures()
    yield


def review(created, stars):
    return {"createTime": created, "starRating": stars}


REVIEWS = [
    review("2026-06-14T10:00:00Z", "FIVE"),
    review("2026-07-02T10:00:00Z", "FIVE"),
    review("2026-07-19T10:00:00Z", "FOUR"),
    review("2026-07-25T10:00:00Z", "TWO"),      # not positive
    review("2026-08-03T10:00:00Z", "FIVE"),
    review("2026-08-11T10:00:00Z", "FIVE"),
    review("2026-08-12T10:00:00Z", "THREE"),    # not positive
    review("2026-08-20T10:00:00Z", "FOUR"),
]


def connect(monkeypatch):
    state = google.load_state()
    state["token"] = {"refreshToken": "r", "access_token": "a", "expiresAt": time.time() + 3600}
    state["account"] = {"name": "accounts/1", "title": "Goodbye Fitness"}
    state["location"] = {"name": "locations/2", "title": "Goodbye Fitness — Lansing", "others": []}
    google.save_state(state)


# ─── grouping ───

def test_reviews_are_grouped_by_the_month_they_were_written():
    months = google.group_by_month(REVIEWS)
    assert months["2026-07"] == {"positive": 2, "total": 3, "stars": 11}
    assert months["2026-08"]["positive"] == 3
    assert months["2026-08"]["total"] == 4


def test_only_four_and_five_stars_count_as_positive():
    months = google.group_by_month([review("2026-08-01T10:00:00Z", stars)
                                    for stars in ("ONE", "TWO", "THREE", "FOUR", "FIVE")])
    assert months["2026-08"]["positive"] == 2
    assert months["2026-08"]["total"] == 5


def test_a_review_with_no_usable_date_is_skipped():
    months = google.group_by_month([{"starRating": "FIVE"}, {"createTime": "nonsense", "starRating": "FIVE"}])
    assert months == {}


def test_the_running_total_counts_everything_up_to_that_month():
    months = google.group_by_month(REVIEWS)
    assert google.running_total("2026-06", months) == 1
    assert google.running_total("2026-07", months) == 3
    assert google.running_total("2026-08", months) == 6


# ─── syncing ───

def test_sync_fills_the_row_as_a_running_total(monkeypatch):
    connect(monkeypatch)
    view = google.sync_month("2026-08", reviews=REVIEWS)
    row = next(r for r in view["rows"] if r["key"] == "google_reviews")
    assert row["prev"] == 3        # positive reviews through July
    assert row["curr"] == 6        # ...and through August
    assert row["gain"] == 3        # the three positive ones left in August
    assert row["bonus"] == 4.50    # at $1.50 each
    assert row["source"] == "google"


def test_a_past_month_comes_out_exact(monkeypatch):
    """The whole point of reading review dates: months before you connected."""
    connect(monkeypatch)
    view = google.sync_month("2026-07", reviews=REVIEWS)
    row = next(r for r in view["rows"] if r["key"] == "google_reviews")
    assert row["prev"] == 1 and row["curr"] == 3
    assert row["gain"] == 2 and row["bonus"] == 3.00


def test_sync_reports_what_it_saw(monkeypatch):
    connect(monkeypatch)
    view = google.sync_month("2026-08", reviews=REVIEWS)
    assert view["sync"] == {"positiveThisMonth": 3, "reviewsThisMonth": 4,
                            "runningTotal": 6, "skipped": []}


def test_sync_leaves_a_hand_typed_row_alone(monkeypatch):
    connect(monkeypatch)
    store.save_month("2026-08", {"google_reviews": {"prev": 3, "curr": 9}})
    view = google.sync_month("2026-08", reviews=REVIEWS)
    row = next(r for r in view["rows"] if r["key"] == "google_reviews")
    assert row["curr"] == 9 and view["sync"]["skipped"] == ["google_reviews"]


def test_force_overwrites_a_hand_typed_row(monkeypatch):
    connect(monkeypatch)
    store.save_month("2026-08", {"google_reviews": {"prev": 3, "curr": 9}})
    view = google.sync_month("2026-08", force=True, reviews=REVIEWS)
    row = next(r for r in view["rows"] if r["key"] == "google_reviews")
    assert row["curr"] == 6


def test_a_month_with_no_reviews_pays_nothing(monkeypatch):
    connect(monkeypatch)
    view = google.sync_month("2026-09", reviews=REVIEWS)
    row = next(r for r in view["rows"] if r["key"] == "google_reviews")
    assert row["gain"] == 0 and row["bonus"] == 0.00
    assert row["curr"] == 6        # the running total holds


def test_a_bad_month_is_refused():
    with pytest.raises(ValueError):
        google.sync_month("2026-13", reviews=REVIEWS)


# ─── connection state ───

def test_status_summarises_what_is_known(monkeypatch):
    connect(monkeypatch)
    google.refresh(REVIEWS)
    state = google.status()
    assert state["connected"] is True
    assert state["location"] == "Goodbye Fitness — Lansing"
    assert state["reviewsKnown"] == 8 and state["positiveKnown"] == 6
    assert state["averageStars"] == 4.12      # 33 stars across 8 reviews
    assert state["monthsKnown"] == 3


def test_disconnect_keeps_the_review_counts(monkeypatch):
    connect(monkeypatch)
    google.refresh(REVIEWS)
    google.disconnect()
    assert google.status()["connected"] is False
    assert google.status()["reviewsKnown"] == 8


def test_auth_url_asks_for_the_business_scope(monkeypatch):
    monkeypatch.setattr(google, "CLIENT_ID", "client")
    monkeypatch.setattr(google, "CLIENT_SECRET", "secret")
    url = google.auth_url("state123")
    assert "business.manage" in url and "access_type=offline" in url


def test_auth_url_without_credentials_is_refused(monkeypatch):
    monkeypatch.setattr(google, "CLIENT_ID", "")
    with pytest.raises(google.NotConfigured):
        google.auth_url("state123")


def test_fetching_before_connecting_is_refused():
    with pytest.raises(google.NotConnected):
        google.fetch_reviews()


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self.payload = payload
        self.content = b"{}"

    def json(self):
        return self.payload


def test_an_unapproved_project_says_so(monkeypatch):
    connect(monkeypatch)
    monkeypatch.setattr(google.http_requests, "get", lambda *a, **k: FakeResponse(
        403, {"error": {"message": "Request had insufficient authentication scopes."}}))
    with pytest.raises(google.NotApproved, match="Business Profile APIs"):
        google._get(google.ACCOUNTS_URL)


def test_an_expired_sign_in_says_reconnect(monkeypatch):
    connect(monkeypatch)
    monkeypatch.setattr(google.http_requests, "get",
                        lambda *a, **k: FakeResponse(401, {"error": {"message": "Invalid Credentials"}}))
    with pytest.raises(google.NotConnected, match="reconnect"):
        google._get(google.ACCOUNTS_URL)


def test_paging_collects_every_review(monkeypatch):
    connect(monkeypatch)
    pages = [
        {"reviews": REVIEWS[:5], "nextPageToken": "more"},
        {"reviews": REVIEWS[5:]},
    ]
    calls = []

    def fake_get(url, params=None):
        calls.append((params or {}).get("pageToken"))
        return pages[len(calls) - 1]

    monkeypatch.setattr(google, "_get", fake_get)
    assert len(google.fetch_reviews()) == len(REVIEWS)
    assert calls == [None, "more"]


# ─── routes ───

@pytest.fixture
def client(monkeypatch, tmp_path):
    import server
    monkeypatch.setattr(server.bonus_store, "DATA_FILE", store.DATA_FILE)
    monkeypatch.setattr(server.bonus_auth, "USERS_FILE", auth.USERS_FILE)
    monkeypatch.setattr(server.bonus_google, "DATA_FILE", google.DATA_FILE)
    server.app.config["TESTING"] = True
    server.app.config["SESSION_COOKIE_SECURE"] = False
    auth.add_user("andy", "correct-horse-battery", "Andy", "admin")
    auth.add_user("jess", "another-good-password", "Jess", "member")
    return server.app.test_client()


def sign_in(client, username="andy", password="correct-horse-battery"):
    res = client.post("/api/bonus/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrfToken"]


def test_google_routes_need_a_login(client):
    assert client.get("/api/bonus/google/status").status_code == 401
    assert client.post("/api/bonus/google/sync", json={}).status_code == 401


def test_only_an_admin_can_connect_or_disconnect(client):
    csrf = sign_in(client, "jess", "another-good-password")
    assert client.get("/api/bonus/google/connect").status_code == 403
    assert client.post("/api/bonus/google/disconnect", json={},
                       headers={"X-CSRF-Token": csrf}).status_code == 403


def test_connect_without_server_credentials_says_so(client, monkeypatch):
    import server
    monkeypatch.setattr(server.bonus_google, "CLIENT_ID", "")
    sign_in(client)
    assert client.get("/api/bonus/google/connect").status_code == 503


def test_connect_redirects_an_admin_to_google(client, monkeypatch):
    import server
    monkeypatch.setattr(server.bonus_google, "CLIENT_ID", "client")
    monkeypatch.setattr(server.bonus_google, "CLIENT_SECRET", "secret")
    sign_in(client)
    res = client.get("/api/bonus/google/connect")
    assert res.status_code == 302
    assert "business.manage" in res.headers["Location"]


def test_syncing_before_connecting_says_so(client):
    csrf = sign_in(client)
    res = client.post("/api/bonus/google/sync", json={"month": "2026-08"},
                      headers={"X-CSRF-Token": csrf})
    assert res.status_code == 409


def test_the_callback_rejects_a_mismatched_state(client):
    sign_in(client)
    res = client.get("/callback/google-reviews?code=abc&state=wrong")
    assert res.status_code == 302 and "state_mismatch" in res.headers["Location"]


def test_the_nightly_sync_includes_google_when_connected(monkeypatch):
    import server
    from datetime import datetime
    monkeypatch.setattr(server.bonus_store, "DATA_FILE", store.DATA_FILE)
    monkeypatch.setattr(server.bonus_google, "status", lambda: {"connected": True})
    monkeypatch.setattr(server.bonus_google, "sync_month", lambda month: None)
    results = server.run_nightly_sync(today=datetime(2026, 8, 22, 3, 15))
    assert "google 2026-08 ok" in results
