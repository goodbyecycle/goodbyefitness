"""Tests for the social media bonus tracker — store, auth, and the API."""

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from bonus import auth, store


@pytest.fixture(autouse=True)
def temp_files(tmp_path, monkeypatch):
    """Point every module at throwaway files so real data is never touched."""
    monkeypatch.setattr(store, "DATA_FILE", tmp_path / "bonus_data.json")
    monkeypatch.setattr(auth, "USERS_FILE", tmp_path / "bonus_users.json")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "bonus_secret.key")
    auth.clear_failures()
    yield


# ─── store ───

def test_defaults_match_the_agreed_rates():
    rates = store.get_rates()
    assert rates["youtube_subs"] == 0.50
    assert rates["instagram_followers"] == 0.25
    assert rates["facebook_followers"] == 0.25
    assert rates["google_reviews"] == 1.50
    assert rates["youtube_hours"] == 1.00


def test_gain_and_bonus_are_computed_per_metric():
    view = store.save_month("2026-08", {
        "youtube_subs": {"prev": 1240, "curr": 1388},
        "instagram_followers": {"prev": 3120, "curr": 3305},
        "facebook_followers": {"prev": 870, "curr": 902},
        "google_reviews": {"prev": 46, "curr": 53},
        "youtube_hours": {"prev": 2150, "curr": 2480},
    })
    rows = {row["key"]: row for row in view["rows"]}
    assert rows["youtube_subs"]["gain"] == 148
    assert rows["youtube_subs"]["bonus"] == 74.00
    assert rows["instagram_followers"]["bonus"] == 46.25
    assert rows["facebook_followers"]["bonus"] == 8.00
    assert rows["google_reviews"]["bonus"] == 10.50
    assert rows["youtube_hours"]["bonus"] == 330.00
    assert view["totalBonus"] == 468.75


def test_summary_splits_bonus_by_group():
    store.save_month("2026-08", {
        "youtube_subs": {"prev": 1240, "curr": 1388},
        "instagram_followers": {"prev": 3120, "curr": 3305},
        "facebook_followers": {"prev": 870, "curr": 902},
        "google_reviews": {"prev": 46, "curr": 53},
        "youtube_hours": {"prev": 2150, "curr": 2480},
    })
    summary = store.compute_month("2026-08")["summary"]
    assert summary["audienceGain"] == 365
    assert summary["audienceBonus"] == 128.25
    assert summary["watchBonus"] == 330.00
    assert summary["reviewsBonus"] == 10.50


def test_a_month_that_goes_backwards_pays_nothing():
    view = store.save_month("2026-08", {"instagram_followers": {"prev": 3120, "curr": 3000}})
    row = next(r for r in view["rows"] if r["key"] == "instagram_followers")
    assert row["gain"] == -120
    assert row["bonus"] == 0.0


def test_previous_month_carries_forward():
    store.save_month("2026-07", {"youtube_subs": {"prev": 1100, "curr": 1240}})
    row = next(r for r in store.compute_month("2026-08")["rows"] if r["key"] == "youtube_subs")
    assert row["prev"] == 1240
    assert row["carriedPrev"] is True


def test_an_entered_previous_month_beats_the_carried_one():
    store.save_month("2026-07", {"youtube_subs": {"prev": 1100, "curr": 1240}})
    store.save_month("2026-08", {"youtube_subs": {"prev": 1250, "curr": 1300}})
    row = next(r for r in store.compute_month("2026-08")["rows"] if r["key"] == "youtube_subs")
    assert row["prev"] == 1250
    assert row["carriedPrev"] is False
    assert row["bonus"] == 25.00


def test_changing_a_rate_changes_the_bonus():
    store.save_month("2026-08", {"youtube_subs": {"prev": 100, "curr": 200}})
    store.set_rates({"youtube_subs": 0.75})
    row = next(r for r in store.compute_month("2026-08")["rows"] if r["key"] == "youtube_subs")
    assert row["bonus"] == 75.00


def test_bad_input_is_rejected():
    with pytest.raises(ValueError):
        store.save_month("2026-13", {})
    with pytest.raises(ValueError):
        store.save_month("2026-08", {"not_a_metric": {"curr": 5}})
    with pytest.raises(ValueError):
        store.save_month("2026-08", {"youtube_subs": {"curr": -5}})
    with pytest.raises(ValueError):
        store.set_rates({"youtube_subs": -1})


def test_hours_keep_one_decimal_but_counts_stay_whole():
    view = store.save_month("2026-08", {
        "youtube_hours": {"prev": 100.44, "curr": 150.55},
        "youtube_subs": {"prev": 10.6, "curr": 20},
    })
    rows = {row["key"]: row for row in view["rows"]}
    assert rows["youtube_hours"]["prev"] == 100.4
    assert rows["youtube_hours"]["curr"] == 150.6
    assert rows["youtube_subs"]["prev"] == 11


def test_paid_flag_round_trips():
    store.save_month("2026-08", {"youtube_subs": {"prev": 1, "curr": 2}})
    view = store.set_paid("2026-08", True, "2026-09-01", "Andy")
    assert view["paid"] is True and view["paidOn"] == "2026-09-01"
    assert store.set_paid("2026-08", False)["paid"] is False


def test_month_list_is_newest_first():
    store.save_month("2026-07", {"youtube_subs": {"prev": 0, "curr": 10}})
    store.save_month("2026-08", {"youtube_subs": {"prev": 10, "curr": 30}})
    months = store.list_months()
    assert [m["month"] for m in months] == ["2026-08", "2026-07"]
    assert months[0]["totalBonus"] == 10.00


def test_shift_month_crosses_year_boundaries():
    assert store.shift_month("2026-01", -1) == "2025-12"
    assert store.shift_month("2026-12", 1) == "2027-01"


# ─── auth ───

def test_password_is_never_stored_in_the_clear():
    auth.add_user("andy", "correct-horse-battery", "Andy", "admin")
    stored = json.loads(auth.USERS_FILE.read_text())["users"]["andy"]
    assert "correct-horse-battery" not in json.dumps(stored)
    assert stored["role"] == "admin"


def test_login_accepts_the_right_password_only():
    auth.add_user("jess", "another-good-password")
    assert auth.verify("Jess", "another-good-password")["role"] == "member"
    assert auth.verify("jess", "wrong-password") is None
    assert auth.verify("nobody", "another-good-password") is None


def test_short_passwords_are_refused():
    with pytest.raises(ValueError):
        auth.add_user("andy", "short")


def test_repeated_failures_lock_the_account():
    auth.add_user("andy", "correct-horse-battery")
    for _ in range(auth.MAX_FAILED_ATTEMPTS):
        auth.verify("andy", "nope")
    with pytest.raises(PermissionError):
        auth.verify("andy", "correct-horse-battery")
    # ...and the lock lifts once the window passes
    later = time.time() + auth.LOCKOUT_SECONDS + 1
    assert auth.verify("andy", "correct-horse-battery", now=later)


def test_secret_key_persists_between_calls():
    first = auth.get_secret_key()
    assert first and auth.get_secret_key() == first


# ─── API ───

@pytest.fixture
def client(monkeypatch, tmp_path):
    import server
    monkeypatch.setattr(server.bonus_store, "DATA_FILE", tmp_path / "bonus_data.json")
    monkeypatch.setattr(server.bonus_auth, "USERS_FILE", tmp_path / "bonus_users.json")
    server.app.config["TESTING"] = True
    server.app.config["SESSION_COOKIE_SECURE"] = False
    auth.add_user("andy", "correct-horse-battery", "Andy", "admin")
    auth.add_user("jess", "another-good-password", "Jess", "member")
    return server.app.test_client()


def sign_in(client, username, password):
    res = client.post("/api/bonus/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.get_json()
    return res.get_json()["csrfToken"]


def test_the_page_needs_a_login(client):
    assert client.get("/api/bonus/months").status_code == 401
    assert client.get("/api/bonus/month/2026-08").status_code == 401
    assert client.post("/api/bonus/month/2026-08", json={"values": {}}).status_code == 401


def test_wrong_password_is_rejected(client):
    assert client.post("/api/bonus/login", json={"username": "andy", "password": "nope"}).status_code == 401


def test_a_member_can_enter_numbers(client):
    csrf = sign_in(client, "jess", "another-good-password")
    res = client.post("/api/bonus/month/2026-08",
                      json={"values": {"youtube_subs": {"prev": 100, "curr": 200}}},
                      headers={"X-CSRF-Token": csrf})
    assert res.status_code == 200
    assert res.get_json()["totalBonus"] == 50.00


def test_writes_need_the_csrf_token(client):
    sign_in(client, "andy", "correct-horse-battery")
    res = client.post("/api/bonus/month/2026-08",
                      json={"values": {"youtube_subs": {"prev": 100, "curr": 200}}})
    assert res.status_code == 403


def test_only_an_admin_can_change_rates_or_mark_paid(client):
    csrf = sign_in(client, "jess", "another-good-password")
    assert client.post("/api/bonus/rates", json={"rates": {"youtube_subs": 5}},
                       headers={"X-CSRF-Token": csrf}).status_code == 403
    assert client.post("/api/bonus/month/2026-08/paid", json={"paid": True},
                       headers={"X-CSRF-Token": csrf}).status_code == 403

    csrf = sign_in(client, "andy", "correct-horse-battery")
    assert client.post("/api/bonus/rates", json={"rates": {"youtube_subs": 0.75}},
                       headers={"X-CSRF-Token": csrf}).status_code == 200
    paid = client.post("/api/bonus/month/2026-08/paid", json={"paid": True},
                       headers={"X-CSRF-Token": csrf})
    assert paid.get_json()["paid"] is True


def test_signing_out_ends_the_session(client):
    csrf = sign_in(client, "andy", "correct-horse-battery")
    client.post("/api/bonus/logout", headers={"X-CSRF-Token": csrf})
    assert client.get("/api/bonus/months").status_code == 401
