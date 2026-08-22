"""Google reviews connection for the bonus tracker.

Unlike followers, reviews come with the date they were left, so this one can
work out any month exactly — including months before the account was ever
connected. Every review is fetched, grouped by the month it was written, and a
"positive" review is one of four or five stars.

The row is kept as a running total: the previous month's figure is the count of
positive reviews up to the end of that month, so the gain is exactly the
positive reviews received during the month.

Reading reviews needs the Google Business Profile APIs, which Google grants per
project on request — see the README. Until that request is approved the calls
come back 403 and the page says so.
"""

import json
import os
import time
from pathlib import Path
from threading import Lock
from urllib.parse import urlencode

import requests as http_requests

from bonus import store

DATA_DIR = Path(__file__).parent.parent
DATA_FILE = DATA_DIR / "bonus_google.json"

# Same Google project as YouTube by default — one OAuth client can serve both.
CLIENT_ID = os.environ.get("GOOGLE_BUSINESS_CLIENT_ID") or os.environ.get("YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_BUSINESS_CLIENT_SECRET") or os.environ.get("YOUTUBE_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("GOOGLE_BUSINESS_REDIRECT_URI",
                              "https://goodbyefitness.com/callback/google-reviews")

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ACCOUNTS_URL = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
LOCATIONS_URL = "https://mybusinessbusinessinformation.googleapis.com/v1"
REVIEWS_URL = "https://mybusiness.googleapis.com/v4"

SCOPES = ["https://www.googleapis.com/auth/business.manage"]

METRIC = "google_reviews"
POSITIVE_STARS = ("FOUR", "FIVE")
STAR_VALUES = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}

TIMEOUT = 30
PAGE_SIZE = 50

_LOCK = Lock()


class NotConfigured(RuntimeError):
    """No Google OAuth client set in the environment."""


class NotConnected(RuntimeError):
    """Nobody has connected the business listing yet."""


class NotApproved(RuntimeError):
    """Google hasn't granted this project access to the Business Profile APIs."""


def is_configured():
    return bool(CLIENT_ID and CLIENT_SECRET)


def _blank():
    return {"token": None, "account": None, "location": None, "months": {}, "lastSync": None}


def load_state():
    if not DATA_FILE.exists():
        return _blank()
    try:
        state = json.loads(DATA_FILE.read_text())
    except json.JSONDecodeError:
        return _blank()
    for key, value in _blank().items():
        state.setdefault(key, value)
    return state


def save_state(state):
    temp = DATA_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2, sort_keys=True))
    os.replace(temp, DATA_FILE)
    os.chmod(DATA_FILE, 0o600)


def disconnect():
    state = load_state()
    state.update({"token": None, "account": None, "location": None})
    save_state(state)      # the month counts stay; only the sign-in goes
    return True


def auth_url(state_token):
    if not is_configured():
        raise NotConfigured("GOOGLE_BUSINESS_CLIENT_ID and GOOGLE_BUSINESS_CLIENT_SECRET are not set")
    return AUTH_URL + "?" + urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state_token,
    })


def exchange_code(code):
    if not is_configured():
        raise NotConfigured("GOOGLE_BUSINESS_CLIENT_ID and GOOGLE_BUSINESS_CLIENT_SECRET are not set")
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
    state = load_state()
    token = state.get("token") or {}
    token.update({
        "access_token": payload["access_token"],
        "expiresAt": time.time() + payload.get("expires_in", 3600) - 60,
    })
    if payload.get("refresh_token"):
        token["refreshToken"] = payload["refresh_token"]
    state["token"] = token
    save_state(state)
    choose_location()
    return load_state()


def access_token():
    state = load_state()
    token = state.get("token") or {}
    if not token.get("refreshToken") and not token.get("access_token"):
        raise NotConnected("Google reviews are not connected yet")
    if token.get("access_token") and token.get("expiresAt", 0) > time.time():
        return token["access_token"]
    if not is_configured():
        raise NotConfigured("GOOGLE_BUSINESS_CLIENT_ID and GOOGLE_BUSINESS_CLIENT_SECRET are not set")
    res = http_requests.post(TOKEN_URL, data={
        "refresh_token": token["refreshToken"],
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
    }, timeout=TIMEOUT)
    payload = res.json()
    if "access_token" not in payload:
        raise NotConnected(payload.get("error_description") or "Google sign-in expired — reconnect")
    token["access_token"] = payload["access_token"]
    token["expiresAt"] = time.time() + payload.get("expires_in", 3600) - 60
    state["token"] = token
    save_state(state)
    return token["access_token"]


def _get(url, params=None):
    """One Google API call. Tests replace this."""
    res = http_requests.get(url, params=params or {}, timeout=TIMEOUT,
                            headers={"Authorization": "Bearer " + access_token()})
    payload = res.json() if res.content else {}
    if res.status_code == 403:
        message = (payload.get("error") or {}).get("message", "")
        raise NotApproved(
            "Google hasn't granted this project access to the Business Profile APIs yet. " + message)
    if res.status_code == 401:
        raise NotConnected("Google sign-in expired — reconnect")
    if res.status_code != 200:
        raise RuntimeError((payload.get("error") or {}).get("message")
                           or "Google API error %s" % res.status_code)
    return payload


def choose_location():
    """Find the business listing whose reviews we'll count."""
    accounts = (_get(ACCOUNTS_URL).get("accounts") or [])
    if not accounts:
        raise RuntimeError("That Google account manages no business profiles")
    account = accounts[0]
    locations = (_get(LOCATIONS_URL + "/" + account["name"] + "/locations",
                      {"readMask": "name,title"}).get("locations") or [])
    if not locations:
        raise RuntimeError("That business profile has no locations")
    location = locations[0]

    state = load_state()
    state["account"] = {"name": account["name"], "title": account.get("accountName")}
    state["location"] = {
        "name": location["name"],
        "title": location.get("title"),
        "others": [l.get("title") for l in locations[1:]],
    }
    save_state(state)
    return state


def fetch_reviews():
    """Every review on the listing, following pagination."""
    state = load_state()
    account, location = state.get("account"), state.get("location")
    if not account or not location:
        raise NotConnected("Google reviews are not connected yet")
    url = "%s/%s/%s/reviews" % (REVIEWS_URL, account["name"], location["name"])

    reviews, page_token = [], None
    while True:
        params = {"pageSize": PAGE_SIZE}
        if page_token:
            params["pageToken"] = page_token
        payload = _get(url, params)
        reviews.extend(payload.get("reviews") or [])
        page_token = payload.get("nextPageToken")
        if not page_token:
            return reviews


def group_by_month(reviews):
    """{month: {positive, total, stars}} keyed on the month each review was written."""
    months = {}
    for review in reviews:
        created = (review.get("createTime") or "")[:7]
        if not store.valid_month(created):
            continue
        stars = review.get("starRating")
        entry = months.setdefault(created, {"positive": 0, "total": 0, "stars": 0})
        entry["total"] += 1
        entry["stars"] += STAR_VALUES.get(stars, 0)
        if stars in POSITIVE_STARS:
            entry["positive"] += 1
    return months


def refresh(reviews=None):
    """Pull every review and remember the per-month counts."""
    months = group_by_month(reviews if reviews is not None else fetch_reviews())
    with _LOCK:
        state = load_state()
        state["months"] = months
        state["lastSync"] = time.time()
        save_state(state)
    return months


def running_total(month, months=None):
    """Positive reviews received up to and including the end of a month."""
    months = months if months is not None else load_state()["months"]
    return sum(entry.get("positive", 0) for period, entry in months.items() if period <= month)


def sync_month(month, force=False, reviews=None):
    """Fill the Google reviews row for a month from the review dates themselves."""
    if not store.valid_month(month):
        raise ValueError("month must look like 2026-08")
    months = refresh(reviews)

    view = store.compute_month(month)
    row = next(r for r in view["rows"] if r["key"] == METRIC)
    skipped = []
    if row["source"] == "manual" and row["curr"] is not None and not force:
        skipped.append(METRIC)
    else:
        store.save_month(month, {METRIC: {
            "prev": running_total(store.shift_month(month, -1), months),
            "curr": running_total(month, months),
        }}, editor="Google", source="google")

    this_month = months.get(month, {})
    result = store.compute_month(month)
    result["sync"] = {
        "positiveThisMonth": this_month.get("positive", 0),
        "reviewsThisMonth": this_month.get("total", 0),
        "runningTotal": running_total(month, months),
        "skipped": skipped,
    }
    return result


def status():
    state = load_state()
    months = state.get("months") or {}
    total = sum(entry.get("total", 0) for entry in months.values())
    stars = sum(entry.get("stars", 0) for entry in months.values())
    return {
        "configured": is_configured(),
        "connected": bool(state.get("location")),
        "location": (state.get("location") or {}).get("title"),
        "otherLocations": (state.get("location") or {}).get("others") or [],
        "reviewsKnown": total,
        "positiveKnown": sum(entry.get("positive", 0) for entry in months.values()),
        "averageStars": round(stars / total, 2) if total else None,
        "monthsKnown": len(months),
        "lastSync": state.get("lastSync"),
        "redirectUri": REDIRECT_URI,
    }
