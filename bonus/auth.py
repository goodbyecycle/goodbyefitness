"""Logins for the bonus tracker page.

Two accounts, stored as password hashes in a file that is never committed.
Create them with `python tools/bonus_user.py add <username>`.
"""

import json
import os
import secrets
import time
from pathlib import Path
from threading import Lock

from werkzeug.security import check_password_hash, generate_password_hash

DATA_DIR = Path(os.environ.get("BONUS_DATA_DIR")
                or Path(__file__).parent.parent)
USERS_FILE = DATA_DIR / "bonus_users.json"
SECRET_FILE = DATA_DIR / "bonus_secret.key"

MIN_PASSWORD_LENGTH = 10
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60

ROLES = ("admin", "member")

# A hash to check against when the username doesn't exist, so a bad username
# and a bad password take the same amount of time to answer.
_DUMMY_HASH = generate_password_hash("not-a-real-password")

_LOCK = Lock()
_failures = {}


def load_users():
    if not USERS_FILE.exists():
        return {}
    return json.loads(USERS_FILE.read_text()).get("users", {})


def _save_users(users):
    USERS_FILE.write_text(json.dumps({"users": users}, indent=2, sort_keys=True))
    os.chmod(USERS_FILE, 0o600)


def get_secret_key():
    """Session signing key — persisted so logins survive a server restart."""
    env_key = os.environ.get("BONUS_SECRET_KEY", "").strip()
    if env_key:
        return env_key
    if SECRET_FILE.exists():
        key = SECRET_FILE.read_text().strip()
        if key:
            return key
    key = secrets.token_urlsafe(48)
    SECRET_FILE.write_text(key)
    os.chmod(SECRET_FILE, 0o600)
    return key


def add_user(username, password, display_name=None, role="member"):
    username = (username or "").strip().lower()
    if not username:
        raise ValueError("username is required")
    if role not in ROLES:
        raise ValueError("role must be one of: %s" % ", ".join(ROLES))
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError("password must be at least %d characters" % MIN_PASSWORD_LENGTH)
    with _LOCK:
        users = load_users()
        users[username] = {
            "hash": generate_password_hash(password),
            "displayName": display_name or username.title(),
            "role": role,
        }
        _save_users(users)
    return {"username": username, "displayName": users[username]["displayName"], "role": role}


def remove_user(username):
    username = (username or "").strip().lower()
    with _LOCK:
        users = load_users()
        if username not in users:
            return False
        del users[username]
        _save_users(users)
    return True


def set_password(username, password):
    username = (username or "").strip().lower()
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError("password must be at least %d characters" % MIN_PASSWORD_LENGTH)
    with _LOCK:
        users = load_users()
        if username not in users:
            raise ValueError("no such user: %s" % username)
        users[username]["hash"] = generate_password_hash(password)
        _save_users(users)
    return True


def lockout_remaining(username, now=None):
    """Seconds left on a lockout after too many failed attempts, 0 if clear."""
    now = now or time.time()
    record = _failures.get((username or "").strip().lower())
    if not record or record["count"] < MAX_FAILED_ATTEMPTS:
        return 0
    remaining = int(record["last"] + LOCKOUT_SECONDS - now)
    return max(0, remaining)


def _record_failure(username, now):
    key = (username or "").strip().lower()
    record = _failures.get(key)
    if record and now - record["last"] > LOCKOUT_SECONDS:
        record = None
    record = record or {"count": 0, "last": now}
    record["count"] += 1
    record["last"] = now
    _failures[key] = record


def clear_failures(username=None):
    if username is None:
        _failures.clear()
    else:
        _failures.pop((username or "").strip().lower(), None)


def verify(username, password, now=None):
    """Return the user dict on a correct login, else None.

    Raises PermissionError while the account is locked out.
    """
    now = now or time.time()
    username = (username or "").strip().lower()
    remaining = lockout_remaining(username, now)
    if remaining:
        raise PermissionError(remaining)
    user = load_users().get(username)
    stored_hash = user["hash"] if user else _DUMMY_HASH
    if not check_password_hash(stored_hash, password or "") or user is None:
        _record_failure(username, now)
        return None
    clear_failures(username)
    return {
        "username": username,
        "displayName": user.get("displayName", username.title()),
        "role": user.get("role", "member"),
    }
