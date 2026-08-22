#!/usr/bin/env python3
"""Get the bonus tracker running, and check it stays that way.

    python tools/bonus_setup.py check     # what's set up, what isn't
    python tools/bonus_setup.py init      # create the two logins, then check

Nothing here talks to the internet — it reports what this server knows.
"""

import argparse
import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent

OK, NO, WARN = "  ok ", "  -- ", " warn"

REQUIRED = [("flask", "flask"), ("apscheduler", "apscheduler"), ("requests", "requests")]
OPTIONAL = [("twilio", "twilio (daily SMS)"), ("openpyxl", "openpyxl (spreadsheet builder)")]


def line(mark, label, detail=""):
    print("[%s] %-34s %s" % (mark, label, detail))


def check_dependencies():
    print("\nDependencies")
    missing = []
    for module, label in REQUIRED:
        found = importlib.util.find_spec(module) is not None
        line(OK if found else NO, label, "" if found else "pip install -r requirements.txt")
        if not found:
            missing.append(module)
    for module, label in OPTIONAL:
        found = importlib.util.find_spec(module) is not None
        line(OK if found else WARN, label, "" if found else "optional")
    return not missing


def check_logins():
    print("\nLogins")
    from bonus import auth
    users = auth.load_users()
    if not users:
        line(NO, "no logins yet", "python tools/bonus_setup.py init")
        return False
    admins = [name for name, user in users.items() if user.get("role") == "admin"]
    for name, user in sorted(users.items()):
        line(OK, "%s (%s)" % (name, user.get("role", "member")), user.get("displayName", ""))
    if not admins:
        line(WARN, "no admin login", "only an admin can connect accounts or set rates")
    return bool(admins)


def check_server():
    print("\nServer")
    dev = os.environ.get("BONUS_DEV", "") == "1"
    line(WARN if dev else OK, "session cookies",
         "BONUS_DEV=1 — Secure flag off, development only" if dev else "Secure (serve over https)")
    secret = os.environ.get("BONUS_SECRET_KEY", "")
    key_file = ROOT / "bonus_secret.key"
    line(OK, "session key",
         "from BONUS_SECRET_KEY" if secret else
         ("saved in bonus_secret.key" if key_file.exists() else "will be generated on first run"))
    autosync = os.environ.get("BONUS_AUTOSYNC", "1") != "0"
    hour = int(os.environ.get("BONUS_AUTOSYNC_HOUR", 3))
    line(OK if autosync else WARN, "nightly sync",
         "%02d:15 every night" % hour if autosync else "off (BONUS_AUTOSYNC=0)")


def check_connections():
    print("\nConnected accounts")
    from bonus import google_reviews, meta, traffic, youtube

    for label, module, setup in (
        ("YouTube", youtube, "YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET"),
        ("Instagram & Facebook", meta, "META_APP_ID / META_APP_SECRET"),
        ("Google reviews", google_reviews, "GOOGLE_BUSINESS_CLIENT_ID / GOOGLE_BUSINESS_CLIENT_SECRET"),
    ):
        state = module.status()
        if not state["configured"]:
            line(NO, label, "set " + setup)
        elif not state["connected"]:
            line(WARN, label, "credentials set — now hit Connect on /bonus")
        else:
            detail = state.get("channel") or state.get("page") or state.get("location") or ""
            if isinstance(detail, dict):
                detail = detail.get("title", "")
            line(OK, label, "connected%s" % (" · " + detail if detail else ""))

    counted = traffic.status()
    line(OK, "Website visitors",
         "counting since %s" % counted["countingSince"] if counted["countingSince"]
         else "starts counting on first visit")


def check_rates():
    print("\nBonus rates")
    from bonus import store
    rates, bases = store.get_rates(), store.get_bases()
    for metric in store.METRICS:
        rate = rates.get(metric["key"], metric["defaultRate"])
        basis = "on the month's total" if bases.get(metric["key"]) == "total" else "on the gain"
        line(OK if rate else WARN, metric["label"],
             "$%.2f %s · %s" % (rate, metric["unit"], basis) if rate
             else "no rate set — pays nothing")


def run_check():
    ready = check_dependencies()
    if not ready:
        print("\nInstall the dependencies first, then run this again.\n")
        return 1
    logged_in = check_logins()
    check_server()
    check_connections()
    check_rates()
    print("\nOpen /bonus once the server is running.%s\n"
          % ("" if logged_in else " Create the logins first."))
    return 0


def run_init():
    if not check_dependencies():
        print("\nInstall the dependencies first, then run this again.\n")
        return 1
    from bonus import auth
    from tools.bonus_user import prompt_password

    users = auth.load_users()
    print("\nCreating the two logins. Passwords are typed here and stored only as hashes.")
    for role, prompt in (("admin", "Your username (admin — can set rates and connect accounts)"),
                         ("member", "Her username (member — enters numbers, sees totals)")):
        existing = [name for name, user in users.items() if user.get("role") == role]
        if existing:
            print("\n%s login already exists: %s" % (role, ", ".join(existing)))
            continue
        print("\n%s: " % prompt, end="")
        username = input().strip()
        if not username:
            print("Skipped.")
            continue
        display = input("Display name [%s]: " % username.title()).strip() or None
        auth.add_user(username, prompt_password(), display, role)
        print("Created %s." % username.lower())
    print()
    return run_check()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["check", "init"], nargs="?", default="check")
    args = parser.parse_args()
    return run_init() if args.command == "init" else run_check()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        sys.exit("\nStopped.")
