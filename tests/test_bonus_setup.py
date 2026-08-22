"""Tests for the setup/doctor command."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from bonus import auth, google_reviews as google, meta, store, traffic, youtube
from tools import bonus_setup, bonus_user


@pytest.fixture(autouse=True)
def temp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_FILE", tmp_path / "bonus_data.json")
    monkeypatch.setattr(auth, "USERS_FILE", tmp_path / "bonus_users.json")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "bonus_secret.key")
    monkeypatch.setattr(youtube, "TOKENS_FILE", tmp_path / "bonus_youtube.json")
    monkeypatch.setattr(meta, "DATA_FILE", tmp_path / "bonus_meta.json")
    monkeypatch.setattr(google, "DATA_FILE", tmp_path / "bonus_google.json")
    monkeypatch.setattr(traffic, "DATA_FILE", tmp_path / "bonus_traffic.json")
    monkeypatch.setattr(bonus_setup, "ROOT", tmp_path)
    yield


def test_check_runs_clean_on_a_fresh_install(capsys):
    assert bonus_setup.run_check() == 0
    out = capsys.readouterr().out
    assert "no logins yet" in out
    assert "set YOUTUBE_CLIENT_ID" in out
    assert "Create the logins first." in out


def test_check_reports_the_rates_and_flags_the_unset_one(capsys):
    bonus_setup.run_check()
    out = capsys.readouterr().out
    assert "$0.50 per new subscriber · on the gain" in out
    assert "$1.50 per new positive review" in out
    assert "no rate set — pays nothing" in out          # website visitors


def test_check_reports_a_basis_change(capsys):
    store.set_bases({"youtube_hours": "total"})
    bonus_setup.run_check()
    assert "on the month's total" in capsys.readouterr().out


def test_check_warns_when_cookies_are_insecure(capsys, monkeypatch):
    monkeypatch.setenv("BONUS_DEV", "1")
    bonus_setup.run_check()
    assert "development only" in capsys.readouterr().out


def test_check_warns_when_the_nightly_sync_is_off(capsys, monkeypatch):
    monkeypatch.setenv("BONUS_AUTOSYNC", "0")
    bonus_setup.run_check()
    assert "off (BONUS_AUTOSYNC=0)" in capsys.readouterr().out


def test_check_lists_existing_logins(capsys):
    auth.add_user("andy", "correct-horse-battery", "Andy", "admin")
    auth.add_user("jess", "another-good-password", "Jess")
    bonus_setup.run_check()
    out = capsys.readouterr().out
    assert "andy (admin)" in out and "jess (member)" in out
    assert "no admin login" not in out


def test_check_warns_when_no_admin_exists(capsys):
    auth.add_user("jess", "another-good-password", "Jess")
    bonus_setup.run_check()
    assert "no admin login" in capsys.readouterr().out


def test_init_creates_both_logins(capsys, monkeypatch):
    answers = iter(["andy", "Andy", "jess", "Jess"])
    passwords = iter(["setup-test-password", "setup-test-password",
                      "another-test-password", "another-test-password"])
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))
    monkeypatch.setattr(bonus_user.getpass, "getpass", lambda *a: next(passwords))

    assert bonus_setup.run_init() == 0
    users = auth.load_users()
    assert users["andy"]["role"] == "admin"
    assert users["jess"]["role"] == "member"
    assert users["andy"]["displayName"] == "Andy"
    assert "setup-test-password" not in auth.USERS_FILE.read_text()


def test_init_leaves_existing_logins_alone(capsys, monkeypatch):
    auth.add_user("andy", "correct-horse-battery", "Andy", "admin")
    answers = iter(["jess", "Jess"])
    passwords = iter(["another-test-password", "another-test-password"])
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))
    monkeypatch.setattr(bonus_user.getpass, "getpass", lambda *a: next(passwords))

    bonus_setup.run_init()
    out = capsys.readouterr().out
    assert "admin login already exists: andy" in out
    assert set(auth.load_users()) == {"andy", "jess"}


def test_check_shows_a_connected_account(capsys, monkeypatch):
    monkeypatch.setattr(meta, "APP_ID", "app")
    monkeypatch.setattr(meta, "APP_SECRET", "secret")
    state = meta.load_state()
    state["page"] = {"id": "1", "name": "Goodbye Fitness", "token": "t"}
    meta.save_state(state)
    bonus_setup.run_check()
    assert "connected · Goodbye Fitness" in capsys.readouterr().out
