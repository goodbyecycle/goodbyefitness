"""Instagram and Facebook connection for the bonus tracker.

One Meta app covers both: the Facebook Page's follower count and, through the
Instagram Business account linked to that Page, the Instagram follower count.

Meta only reports what the counts are *right now* — there's no reliable
historical follower series to ask for. So the server takes a snapshot every
night and keeps them by day; a month's closing figure is the last snapshot
inside that month. That means follower history starts the day you connect,
not before.
"""

import json
import math
import os
import time
from datetime import date
from pathlib import Path
from threading import Lock
from urllib.parse import urlencode

import requests as http_requests

from bonus import store

DATA_DIR = Path(os.environ.get("BONUS_DATA_DIR")
                or Path(__file__).parent.parent)
DATA_FILE = DATA_DIR / "bonus_meta.json"

APP_ID = os.environ.get("META_APP_ID", "")
APP_SECRET = os.environ.get("META_APP_SECRET", "")
REDIRECT_URI = os.environ.get("META_REDIRECT_URI", "https://goodbyefitness.com/callback/meta")
API_VERSION = os.environ.get("META_API_VERSION", "v21.0")
# Facebook Login for Business refuses a free-form scope list and takes its
# permissions from a saved configuration instead. Set META_CONFIG_ID to the
# configuration's ID and the sign-in uses that; leave it unset for a plain
# Facebook Login app, which still wants the scopes.
CONFIG_ID = os.environ.get("META_CONFIG_ID", "").strip()

GRAPH = "https://graph.facebook.com/" + API_VERSION
DIALOG = "https://www.facebook.com/" + API_VERSION + "/dialog/oauth"

SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "instagram_basic",
]

INSTAGRAM_METRIC = "instagram_followers"
FACEBOOK_METRIC = "facebook_followers"

# Instagram and Facebook are tracked separately everywhere except the sign-in
# itself, which Meta only grants for both together (Instagram's API works
# through the linked Page).
NETWORKS = {"instagram": INSTAGRAM_METRIC, "facebook": FACEBOOK_METRIC}

TIMEOUT = 20
KEEP_DAYS = 400

_LOCK = Lock()


class NotConfigured(RuntimeError):
    """No Meta app credentials set in the environment."""


class NotConnected(RuntimeError):
    """Nobody has connected the Page yet, or the token has expired."""


def is_configured():
    return bool(APP_ID and APP_SECRET)


def _blank():
    return {"days": {}, "page": None, "instagram": None, "token": None}


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
    if DATA_FILE.exists():
        state = load_state()
        state.update({"page": None, "instagram": None, "token": None})
        save_state(state)     # the daily history is kept; only the login goes
    return True


def auth_url(state_token):
    if not is_configured():
        raise NotConfigured("META_APP_ID and META_APP_SECRET are not set")
    params = {
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "state": state_token,
    }
    if CONFIG_ID:
        params["config_id"] = CONFIG_ID
    else:
        params["scope"] = ",".join(SCOPES)
    return DIALOG + "?" + urlencode(params)


def _graph(path, params=None, token=None):
    """One call to the Graph API. Tests replace this."""
    params = dict(params or {})
    if token:
        params["access_token"] = token
    res = http_requests.get(GRAPH + path, params=params, timeout=TIMEOUT)
    payload = res.json() if res.content else {}
    error = payload.get("error")
    if error:
        if error.get("code") in (190, 102):
            raise NotConnected("Meta sign-in expired — reconnect Instagram & Facebook")
        raise RuntimeError(error.get("message") or "Meta API error")
    return payload


def exchange_code(code):
    """Swap the callback code for a long-lived token and remember the Page."""
    if not is_configured():
        raise NotConfigured("META_APP_ID and META_APP_SECRET are not set")
    short = _graph("/oauth/access_token", {
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    })
    if "access_token" not in short:
        raise RuntimeError("Meta refused the sign-in")
    # Short-lived tokens last hours; trade up for the 60-day one.
    long_lived = _graph("/oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": short["access_token"],
    })
    token = long_lived.get("access_token", short["access_token"])
    expires_at = time.time() + long_lived.get("expires_in", 60 * 24 * 3600)

    state = load_state()
    state["token"] = {"value": token, "expiresAt": expires_at}
    save_state(state)
    choose_page(token=token)
    return load_state()


def _fetch_pages(token):
    """Every Page this sign-in can see, with its linked Instagram account."""
    payload = _graph("/me/accounts", {
        "fields": "id,name,access_token,followers_count,"
                  "instagram_business_account{id,username,followers_count}",
    }, token)
    pages = payload.get("data") or []
    if not pages:
        raise RuntimeError("That account manages no Facebook Pages")
    return pages


def list_pages(token=None):
    """The Pages available to track, for the picker. Never returns Page tokens."""
    state = load_state()
    token = token or (state.get("token") or {}).get("value")
    if not token:
        raise NotConnected("Instagram & Facebook are not connected yet")
    selected = (state.get("page") or {}).get("id")
    listed = []
    for page in _fetch_pages(token):
        instagram = page.get("instagram_business_account") or None
        listed.append({
            "id": page["id"],
            "name": page.get("name"),
            "followers": page.get("followers_count"),
            "instagram": {
                "username": instagram.get("username"),
                "followers": instagram.get("followers_count"),
            } if instagram else None,
            "selected": page["id"] == selected,
        })
    return listed


def choose_page(*, page_id=None, token=None):
    """Select the Page to track.

    With no page_id, pick the first Page that has an Instagram account attached
    — the sensible default when only one brand is involved. Pass a page_id to
    choose explicitly; with several Pages on one account the default is only a
    guess, and a wrong guess is invisible on the page.

    Switching to a different Page clears the recorded follower history, because
    those counts belong to the Page that was being tracked before. Keeping them
    would make the next month's gain a subtraction between two unrelated
    accounts.
    """
    state = load_state()
    token = token or (state.get("token") or {}).get("value")
    if not token:
        raise NotConnected("Instagram & Facebook are not connected yet")
    pages = _fetch_pages(token)
    if page_id:
        page = next((p for p in pages if p["id"] == str(page_id)), None)
        if page is None:
            raise RuntimeError("That Page is not on this Meta account")
    else:
        page = next((p for p in pages if p.get("instagram_business_account")), pages[0])

    previous = (state.get("page") or {}).get("id")
    if previous and previous != page["id"]:
        state["days"] = {}

    state["page"] = {
        "id": page["id"],
        "name": page.get("name"),
        "token": page.get("access_token"),
        "otherPages": [p.get("name") for p in pages if p["id"] != page["id"]],
    }
    instagram = page.get("instagram_business_account")
    state["instagram"] = {
        "id": instagram["id"],
        "username": instagram.get("username"),
    } if instagram else None
    save_state(state)
    return state


def current_counts():
    """Follower counts as they stand right now."""
    state = load_state()
    page = state.get("page")
    if not page:
        raise NotConnected("Instagram & Facebook are not connected yet")
    page_token = page.get("token") or (state.get("token") or {}).get("value")

    counts = {}
    facebook = _graph("/" + page["id"], {"fields": "followers_count,fan_count"}, page_token)
    counts["facebook"] = facebook.get("followers_count", facebook.get("fan_count"))

    if state.get("instagram"):
        instagram = _graph("/" + state["instagram"]["id"], {"fields": "followers_count"}, page_token)
        counts["instagram"] = instagram.get("followers_count")
    return counts


def snapshot(today=None, counts=None):
    """Record today's follower counts. Called nightly, and on every sync."""
    today = today or date.today().isoformat()
    counts = counts if counts is not None else current_counts()
    with _LOCK:
        state = load_state()
        day = dict(state["days"].get(today, {}))
        for network in ("facebook", "instagram"):
            if counts.get(network) is not None:
                day[network] = int(counts[network])
        state["days"][today] = day
        for old in sorted(state["days"])[:-KEEP_DAYS]:
            state["days"].pop(old, None)
        save_state(state)
    return {"date": today, **day}


def closing_count(month, network, state=None):
    """The last snapshot taken inside a month, or None if there wasn't one."""
    state = state or load_state()
    days = sorted(day for day in state["days"] if day.startswith(month))
    for day in reversed(days):
        value = state["days"][day].get(network)
        if value is not None:
            return value
    return None


def sync_month(month, force=False, today=None, counts=None, networks=None):
    """Fill the Instagram and/or Facebook row from the recorded snapshots.

    `networks` limits the sync to one of them; by default both are done.
    """
    if not store.valid_month(month):
        raise ValueError("month must look like 2026-08")
    networks = list(networks or NETWORKS)
    for network in networks:
        if network not in NETWORKS:
            raise ValueError("unknown network: %s" % network)
    this_month = (today or date.today().isoformat())[:7]
    if month == this_month:
        snapshot(today, counts)      # take a fresh one for the running month

    state = load_state()
    view = store.compute_month(month)
    rows = {row["key"]: row for row in view["rows"]}
    previous = store.shift_month(month, -1)

    values, skipped, missing = {}, [], []
    for network in networks:
        metric = NETWORKS[network]
        row = rows[metric]
        closing = closing_count(month, network, state)
        if closing is None:
            missing.append(metric)
            continue
        if row["source"] == "manual" and row["curr"] is not None and not force:
            skipped.append(metric)
            continue
        prev = closing_count(previous, network, state)
        if prev is None:
            prev = row["prev"]
        values[metric] = {"prev": prev, "curr": closing}

    if values:
        store.save_month(month, values, editor="Meta", source="meta")

    result = store.compute_month(month)
    result["sync"] = {
        "networks": networks,
        "instagram": closing_count(month, "instagram", state),
        "facebook": closing_count(month, "facebook", state),
        "skipped": skipped,
        "missing": missing,
        "days": len([d for d in state["days"] if d.startswith(month)]),
    }
    return result


def _latest(state, network):
    """The most recent snapshot of one network, or None."""
    for day in sorted(state.get("days", {}), reverse=True):
        value = state["days"][day].get(network)
        if value is not None:
            return {"date": day, "count": value}
    return None


def status():
    state = load_state()
    token = state.get("token") or {}
    expires_at = token.get("expiresAt")
    return {
        "configured": is_configured(),
        "connected": bool(state.get("page")),
        "page": (state.get("page") or {}).get("name"),
        "otherPages": (state.get("page") or {}).get("otherPages") or [],
        "instagram": (state.get("instagram") or {}).get("username"),
        "daysRecorded": len(state.get("days", {})),
        "networks": {
            network: {
                "daysRecorded": sum(1 for day in state.get("days", {}).values()
                                    if day.get(network) is not None),
                "latest": _latest(state, network),
            }
            for network in NETWORKS
        },
        "expiresAt": expires_at,
        "expiresInDays": int(math.ceil((expires_at - time.time()) / 86400)) if expires_at else None,
        "redirectUri": REDIRECT_URI,
    }
