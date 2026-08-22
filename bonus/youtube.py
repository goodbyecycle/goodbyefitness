"""YouTube connection for the bonus tracker.

Pulls the two YouTube rows straight from the channel instead of having them
typed in:

* subscribers — `subscribersGained` minus `subscribersLost` for the month,
  which is the exact net figure the bonus is paid on
* hours watched — `estimatedMinutesWatched` for the month, converted to hours

Both come from the YouTube Analytics API, which needs the channel owner to
sign in once. The public subscriber *count* is rounded to three significant
figures by Google, so the running total is anchored once and then moved by
these exact daily deltas rather than re-read each month.
"""

import calendar
import json
import os
import time
from datetime import date
from pathlib import Path

import requests as http_requests

from bonus import store

DATA_DIR = Path(__file__).parent.parent
TOKENS_FILE = DATA_DIR / "bonus_youtube.json"

CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("YOUTUBE_REDIRECT_URI", "https://goodbyefitness.com/callback/youtube")

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]

SUBS_METRIC = "youtube_subs"
HOURS_METRIC = "youtube_hours"

TIMEOUT = 20


class NotConfigured(RuntimeError):
    """No Google OAuth client set in the environment."""


class NotConnected(RuntimeError):
    """Nobody has signed the channel in yet."""


def is_configured():
    return bool(CLIENT_ID and CLIENT_SECRET)


def load_tokens():
    if not TOKENS_FILE.exists():
        return {}
    return json.loads(TOKENS_FILE.read_text())


def save_tokens(tokens):
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2, sort_keys=True))
    os.chmod(TOKENS_FILE, 0o600)


def disconnect():
    if TOKENS_FILE.exists():
        TOKENS_FILE.unlink()
    return True


def auth_url(state):
    if not is_configured():
        raise NotConfigured("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are not set")
    from urllib.parse import urlencode
    return AUTH_URL + "?" + urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",     # so we get a refresh token
        "prompt": "consent",          # ...even on a repeat authorisation
        "include_granted_scopes": "true",
        "state": state,
    })


def exchange_code(code):
    if not is_configured():
        raise NotConfigured("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are not set")
    res = http_requests.post(TOKEN_URL, data={
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=TIMEOUT)
    payload = res.json()
    if "access_token" not in payload:
        raise RuntimeError(payload.get("error_description") or "Google refused the sign-in")
    tokens = load_tokens()
    tokens.update({
        "access_token": payload["access_token"],
        "expires_at": time.time() + payload.get("expires_in", 3600) - 60,
    })
    if payload.get("refresh_token"):
        tokens["refresh_token"] = payload["refresh_token"]
    save_tokens(tokens)
    try:
        tokens["channel"] = channel_info()
        save_tokens(tokens)
    except Exception:
        pass   # the channel name is decoration; the tokens are what matter
    return tokens


def access_token():
    """A valid access token, refreshed if the stored one has expired."""
    tokens = load_tokens()
    if not tokens.get("refresh_token") and not tokens.get("access_token"):
        raise NotConnected("YouTube is not connected yet")
    if tokens.get("access_token") and tokens.get("expires_at", 0) > time.time():
        return tokens["access_token"]
    if not is_configured():
        raise NotConfigured("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are not set")
    res = http_requests.post(TOKEN_URL, data={
        "refresh_token": tokens["refresh_token"],
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
    }, timeout=TIMEOUT)
    payload = res.json()
    if "access_token" not in payload:
        raise NotConnected(payload.get("error_description") or "YouTube sign-in expired — reconnect")
    tokens["access_token"] = payload["access_token"]
    tokens["expires_at"] = time.time() + payload.get("expires_in", 3600) - 60
    save_tokens(tokens)
    return tokens["access_token"]


def _get(url, params):
    res = http_requests.get(url, params=params, timeout=TIMEOUT,
                            headers={"Authorization": "Bearer " + access_token()})
    payload = res.json() if res.content else {}
    if res.status_code != 200:
        message = (payload.get("error") or {}).get("message") or "YouTube API error %s" % res.status_code
        raise RuntimeError(message)
    return payload


def channel_info():
    payload = _get(CHANNELS_URL, {"part": "snippet,statistics", "mine": "true"})
    items = payload.get("items") or []
    if not items:
        raise RuntimeError("That Google account has no YouTube channel")
    item = items[0]
    return {
        "id": item["id"],
        "title": item["snippet"]["title"],
        # Google rounds this to three significant figures — fine as an anchor,
        # never used for the bonus itself.
        "approxSubscribers": int(item.get("statistics", {}).get("subscriberCount", 0)),
    }


def month_bounds(month, today=None):
    """First and last day of the month, never running past today."""
    if not store.valid_month(month):
        raise ValueError("month must look like 2026-08")
    today = today or date.today()
    year, mon = int(month[:4]), int(month[5:])
    start = date(year, mon, 1)
    end = date(year, mon, calendar.monthrange(year, mon)[1])
    if start > today:
        raise ValueError("that month hasn't started yet")
    return start, min(end, today)


def month_report(month, today=None):
    """Net subscribers and hours watched for one month, day by day."""
    start, end = month_bounds(month, today)
    payload = _get(ANALYTICS_URL, {
        "ids": "channel==MINE",
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "metrics": "subscribersGained,subscribersLost,estimatedMinutesWatched",
        "dimensions": "day",
        "sort": "day",
    })
    columns = [c["name"] for c in payload.get("columnHeaders", [])]
    days = []
    for row in payload.get("rows", []):
        entry = dict(zip(columns, row))
        days.append({
            "date": entry.get("day"),
            "gained": int(entry.get("subscribersGained", 0)),
            "lost": int(entry.get("subscribersLost", 0)),
            "minutes": float(entry.get("estimatedMinutesWatched", 0)),
        })
    return {
        "month": month,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "netSubscribers": sum(d["gained"] - d["lost"] for d in days),
        "hoursWatched": round(sum(d["minutes"] for d in days) / 60.0, 1),
    }


def sync_month(month, force=False, today=None, report=None):
    """Fill the two YouTube rows for a month from the channel's own numbers.

    A row someone typed by hand is left alone unless `force` is set, so a sync
    never quietly overwrites a correction.
    """
    report = report or month_report(month, today)
    view = store.compute_month(month)
    rows = {row["key"]: row for row in view["rows"]}

    values = {}
    skipped = []
    anchored_from = None

    subs = rows[SUBS_METRIC]
    if subs["source"] == "manual" and subs["curr"] is not None and not force:
        skipped.append(SUBS_METRIC)
    else:
        # Anchor on whatever the previous month ended at; fall back to the
        # rounded public count so the very first sync still lands somewhere sane.
        anchor = subs["prev"]
        anchored_from = "previous month"
        if anchor is None:
            channel = load_tokens().get("channel") or {}
            approx = channel.get("approxSubscribers")
            anchor = max(0, (approx or 0) - report["netSubscribers"])
            anchored_from = "rounded public count" if approx else "zero"
        values[SUBS_METRIC] = {"prev": anchor, "curr": anchor + report["netSubscribers"]}

    hours = rows[HOURS_METRIC]
    if hours["source"] == "manual" and hours["curr"] is not None and not force:
        skipped.append(HOURS_METRIC)
    else:
        values[HOURS_METRIC] = {"prev": hours["prev"], "curr": report["hoursWatched"]}

    if values:
        store.save_month(month, values, editor="YouTube", source="youtube")

    tokens = load_tokens()
    tokens.setdefault("syncs", {})[month] = {
        "at": time.time(),
        "netSubscribers": report["netSubscribers"],
        "hoursWatched": report["hoursWatched"],
        "days": len(report["days"]),
        "through": report["end"],
    }
    tokens["lastSync"] = tokens["syncs"][month]
    if tokens:
        save_tokens(tokens)

    result = store.compute_month(month)
    result["sync"] = {
        "netSubscribers": report["netSubscribers"],
        "hoursWatched": report["hoursWatched"],
        "through": report["end"],
        "skipped": skipped,
        "anchoredFrom": anchored_from if SUBS_METRIC in values else None,
    }
    return result


def status():
    tokens = load_tokens()
    return {
        "configured": is_configured(),
        "connected": bool(tokens.get("refresh_token") or tokens.get("access_token")),
        "channel": tokens.get("channel"),
        "lastSync": tokens.get("lastSync"),
        "redirectUri": REDIRECT_URI,
    }
