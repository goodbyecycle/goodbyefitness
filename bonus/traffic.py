"""Website traffic counting for the bonus tracker.

The site counts its own visitors rather than leaning on an analytics service:
every page request is hashed into a per-day bucket, so we get views and unique
visitors per day with no third-party account and no tracking cookie.

Raw IP addresses are never stored. Each day a random salt is generated and the
visitor's address and user agent are hashed with it; the salt is thrown away
when the day rolls over, so yesterday's hashes can't be tied back to anyone.
"""

import hashlib
import json
import os
import re
import secrets
from datetime import date
from pathlib import Path
from threading import Lock

from bonus import store

DATA_DIR = Path(os.environ.get("BONUS_DATA_DIR")
                or Path(__file__).parent.parent)
DATA_FILE = DATA_DIR / "bonus_traffic.json"

METRIC = "website_visitors"
KEEP_DAYS = 400

# The tracker's own pages, the API, and static assets aren't website traffic.
IGNORED_PREFIXES = ("/api/", "/bonus", "/nicki", "/callback/", "/static/")
IGNORED_SUFFIXES = (".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp",
                    ".woff", ".woff2", ".map", ".json", ".txt", ".xml")
BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|bingpreview|headless|phantom|puppeteer|playwright|"
    r"curl|wget|python-requests|httpx|go-http-client|lighthouse|pingdom|uptime",
    re.I)

_LOCK = Lock()


def _blank():
    return {"days": {}, "hashes": {}, "salt": {}, "startedOn": None}


def _read():
    """Always from disk. The counts are tiny, and a stale in-memory copy would
    quietly lose visits whenever the server restarts or runs more than once."""
    if not DATA_FILE.exists():
        return _blank()
    try:
        state = json.loads(DATA_FILE.read_text())
    except json.JSONDecodeError:
        return _blank()
    for key, value in _blank().items():
        state.setdefault(key, value)
    return state


def _write(state):
    """Write through a temp file so a crash mid-write can't corrupt the counts."""
    temp = DATA_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2, sort_keys=True))
    os.replace(temp, DATA_FILE)


def _salt_for(state, today):
    """A random salt per day, so visitor hashes can't outlive the day."""
    salt = state.get("salt") or {}
    if salt.get("date") != today:
        salt = {"date": today, "value": secrets.token_hex(16)}
        state["salt"] = salt
        state["hashes"] = {today: []}
    return salt["value"]


def countable(path, user_agent):
    if BOT_RE.search(user_agent or ""):
        return False
    path = (path or "/").split("?")[0]
    if any(path.startswith(prefix) for prefix in IGNORED_PREFIXES):
        return False
    if any(path.lower().endswith(suffix) for suffix in IGNORED_SUFFIXES):
        return False
    return True


def record(path, address, user_agent, today=None):
    """Count one request. Returns True if it counted as a new visitor."""
    if not countable(path, user_agent):
        return False
    today = today or date.today().isoformat()
    with _LOCK:
        state = _read()
        if not state.get("startedOn"):
            state["startedOn"] = today
        salt = _salt_for(state, today)
        fingerprint = hashlib.sha256(
            ("%s|%s|%s" % (salt, address or "", user_agent or "")).encode()).hexdigest()[:16]
        day = state["days"].setdefault(today, {"views": 0, "visitors": 0})
        day["views"] += 1
        seen = state["hashes"].setdefault(today, [])
        fresh = fingerprint not in seen
        if fresh:
            seen.append(fingerprint)
            day["visitors"] += 1
        _prune(state)
        _write(state)
    return fresh


def _prune(state):
    days = sorted(state["days"])
    for old in days[:-KEEP_DAYS]:
        state["days"].pop(old, None)
    for day in list(state["hashes"]):
        if day != (state.get("salt") or {}).get("date"):
            state["hashes"].pop(day, None)


def month_totals(month):
    """Views and unique-per-day visitors for a month."""
    if not store.valid_month(month):
        raise ValueError("month must look like 2026-08")
    state = _read()
    days = {day: counts for day, counts in state["days"].items() if day.startswith(month)}
    return {
        "month": month,
        "views": sum(c.get("views", 0) for c in days.values()),
        "visitors": sum(c.get("visitors", 0) for c in days.values()),
        "days": len(days),
        "countingSince": state.get("startedOn"),
    }


def sync_month(month, force=False):
    """Write the month's visitor count into the tracker.

    Same rule as the YouTube sync: a row someone typed by hand is left alone
    unless forced.
    """
    totals = month_totals(month)
    view = store.compute_month(month)
    row = next(r for r in view["rows"] if r["key"] == METRIC)

    skipped = []
    if row["source"] == "manual" and row["curr"] is not None and not force:
        skipped.append(METRIC)
    else:
        store.save_month(month, {METRIC: {"prev": row["prev"], "curr": totals["visitors"]}},
                         editor="Website", source="website")

    result = store.compute_month(month)
    result["sync"] = {
        "visitors": totals["visitors"],
        "views": totals["views"],
        "days": totals["days"],
        "skipped": skipped,
    }
    return result


def status(month=None):
    state = _read()
    totals = month_totals(month) if month else None
    return {
        "countingSince": state.get("startedOn"),
        "daysRecorded": len(state.get("days", {})),
        "thisMonth": totals,
    }
