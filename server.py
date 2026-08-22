"""Fitness Test demo server with Twilio SMS and Strava integration."""

import json
import os
import random
import secrets
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from functools import wraps
from pathlib import Path

import requests as http_requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, redirect, request, send_from_directory, session

from bonus import auth as bonus_auth
from bonus import store as bonus_store

app = Flask(__name__, static_folder=".", static_url_path="")

# Sessions back the bonus tracker logins. Cookies are marked Secure unless
# BONUS_DEV=1, which is the escape hatch for running over http on localhost.
app.secret_key = bonus_auth.get_secret_key()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("BONUS_DEV", "") != "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

DATA_FILE = Path(__file__).parent / "user_data.json"
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# ─── Twilio config (set these env vars or they'll be prompted on first send) ───
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_PHONE_NUMBER", "")

# ─── Strava config ───
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID", "")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "")
STRAVA_REDIRECT_URI = os.environ.get("STRAVA_REDIRECT_URI", "https://goodbyefitness.com/callback/strava")

# ─── Email notifications ───
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "goodbyefitness@gmail.com")
NOTIFY_APP_PASSWORD = os.environ.get("NOTIFY_APP_PASSWORD", "")


def send_notification_email(subject, body):
    if not NOTIFY_APP_PASSWORD:
        print(f"[EMAIL] Not configured, skipping: {subject}")
        return False
    try:
        msg = MIMEText(body, "html")
        msg["Subject"] = subject
        msg["From"] = NOTIFY_EMAIL
        msg["To"] = NOTIFY_EMAIL
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(NOTIFY_EMAIL, NOTIFY_APP_PASSWORD)
            server.send_message(msg)
        print(f"[EMAIL] Sent: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL] Error: {e}")
        return False


def get_twilio_client():
    if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM]):
        return None
    from twilio.rest import Client
    return Client(TWILIO_SID, TWILIO_TOKEN)


def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {"profile": {}, "history": [], "training": []}


def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))


# ─── Static files ───

@app.route("/")
def landing():
    return send_from_directory(".", "landing.html")


@app.route("/app")
def index():
    return send_from_directory(".", "index.html")


@app.route("/andrew")
def andrew_dashboard():
    return send_from_directory(".", "andrew.html")


# ─── API: Notifications ───

@app.route("/api/notify/signup", methods=["POST"])
def notify_signup():
    body = request.json or {}
    name = body.get("name", "Unknown")
    email = body.get("email", "Unknown")
    opted_in = body.get("notificationsOptIn", False)
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    send_notification_email(
        f"New Signup: {name}",
        f"<h2>New Goodbye Fitness Signup</h2>"
        f"<p><b>Name:</b> {name}</p>"
        f"<p><b>Email:</b> {email}</p>"
        f"<p><b>Notifications opt-in:</b> {'Yes' if opted_in else 'No'}</p>"
        f"<p><b>Signed up:</b> {now}</p>"
    )
    return jsonify({"ok": True})


# ─── API: Profile ───

@app.route("/api/profile", methods=["GET"])
def get_profile():
    return jsonify(load_data().get("profile", {}))


@app.route("/api/profile", methods=["POST"])
def save_profile():
    data = load_data()
    data["profile"] = request.json
    save_data(data)
    reschedule_sms(data["profile"])
    return jsonify({"ok": True})


# ─── API: SMS ───

@app.route("/api/sms/test", methods=["POST"])
def test_sms():
    """Send a one-off test message."""
    body = request.json or {}
    phone = body.get("phone", "")
    message = body.get("message", "")
    if not phone or not message:
        return jsonify({"error": "phone and message required"}), 400

    client = get_twilio_client()
    if not client:
        return jsonify({
            "error": "Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER env vars.",
            "demo": True,
            "message": message,
        }), 200

    try:
        msg = client.messages.create(
            body=message,
            from_=TWILIO_FROM,
            to=phone,
        )
        return jsonify({"ok": True, "sid": msg.sid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sms/status", methods=["GET"])
def sms_status():
    """Check if Twilio is configured."""
    configured = all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM])
    return jsonify({
        "configured": configured,
        "from_number": TWILIO_FROM if configured else None,
    })


# ─── Strava OAuth + API ───

@app.route("/api/strava/connect")
def strava_connect():
    """Redirect user to Strava authorization."""
    url = (
        "https://www.strava.com/oauth/authorize"
        f"?client_id={STRAVA_CLIENT_ID}"
        f"&redirect_uri={STRAVA_REDIRECT_URI}"
        "&response_type=code"
        "&scope=read,activity:read_all"
    )
    return redirect(url)


@app.route("/callback/strava")
def strava_callback():
    """Handle Strava OAuth callback."""
    code = request.args.get("code")
    if not code:
        return "Authorization denied.", 400

    resp = http_requests.post("https://www.strava.com/oauth/token", data={
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }, timeout=15)

    if resp.status_code != 200:
        return f"Token exchange failed: {resp.text}", 500

    tokens = resp.json()
    data = load_data()
    data["strava"] = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_at": tokens["expires_at"],
        "athlete": tokens.get("athlete", {}),
    }
    save_data(data)

    return """
    <html><body style="background:#1a1a2e;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh">
    <div style="text-align:center">
      <h1>Strava Connected!</h1>
      <p>You can close this tab and go back to the app.</p>
      <script>window.opener && window.opener.postMessage('strava_connected','*'); setTimeout(()=>window.close(),2000);</script>
    </div></body></html>
    """


def refresh_strava_token(strava_data):
    """Refresh the Strava access token if expired."""
    if strava_data.get("expires_at", 0) > time.time() + 60:
        return strava_data["access_token"]

    resp = http_requests.post("https://www.strava.com/oauth/token", data={
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "refresh_token": strava_data["refresh_token"],
        "grant_type": "refresh_token",
    }, timeout=15)

    if resp.status_code != 200:
        return None

    tokens = resp.json()
    data = load_data()
    data["strava"]["access_token"] = tokens["access_token"]
    data["strava"]["refresh_token"] = tokens["refresh_token"]
    data["strava"]["expires_at"] = tokens["expires_at"]
    save_data(data)
    return tokens["access_token"]


@app.route("/api/strava/status")
def strava_status():
    """Check if Strava is connected."""
    data = load_data()
    strava = data.get("strava")
    if not strava or not strava.get("access_token"):
        return jsonify({"connected": False})
    athlete = strava.get("athlete", {})
    return jsonify({
        "connected": True,
        "athlete": f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
    })


@app.route("/api/strava/activities")
def strava_activities():
    """Fetch recent activities from Strava."""
    data = load_data()
    strava = data.get("strava")
    if not strava:
        return jsonify({"error": "Not connected"}), 401

    token = refresh_strava_token(strava)
    if not token:
        return jsonify({"error": "Token refresh failed"}), 401

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 30))

    resp = http_requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {token}"},
        params={"page": page, "per_page": per_page},
        timeout=15,
    )

    if resp.status_code != 200:
        return jsonify({"error": resp.text}), resp.status_code

    activities = []
    for a in resp.json():
        activities.append({
            "id": a["id"],
            "name": a["name"],
            "type": a["type"].lower(),
            "date": a["start_date_local"],
            "distance": round(a.get("distance", 0) / 1609.34, 2),
            "distance_m": a.get("distance", 0),
            "duration_min": round(a.get("moving_time", 0) / 60, 1),
            "elevation_gain": round(a.get("total_elevation_gain", 0) * 3.281, 0),
            "avg_speed_mph": round(a.get("average_speed", 0) * 2.237, 1),
            "max_speed_mph": round(a.get("max_speed", 0) * 2.237, 1),
            "avg_hr": a.get("average_heartrate"),
            "max_hr": a.get("max_heartrate"),
            "suffer_score": a.get("suffer_score"),
            "source": "strava",
        })

    return jsonify({"activities": activities})


@app.route("/api/strava/disconnect", methods=["POST"])
def strava_disconnect():
    """Remove Strava tokens."""
    data = load_data()
    data.pop("strava", None)
    save_data(data)
    return jsonify({"ok": True})


# ─── Daily message generation ───

GREETINGS = [
    "Rise and grind, {name}.",
    "New day, new gains, {name}.",
    "Morning {name}. Time to move.",
    "Hey {name} -- your body is ready even if your brain isn't.",
    "{name}, yesterday's you would be jealous of today's workout.",
    "Let's go {name}. No excuses today.",
]

CLOSERS = [
    "12 minutes. That's it. Go.",
    "You don't need motivation. You need to start.",
    "The workout you skip is the one that mattered most.",
    "Burpees don't care about your excuses.",
    "Lace up. Show up. The rest handles itself.",
    "Even a walk counts. Just move.",
    "Your dog believes in you. Don't let them down.",
]

WALK_NUDGES = [
    "Even 20 minutes outside resets your head. Walk it out.",
    "No gym needed. Grab the leash and go.",
    "A walk isn't nothing -- it's everything on a rest day.",
    "Fresh air > screen time. Get outside.",
]


def build_daily_message(profile, history, training):
    name = profile.get("name", "there")
    lines = []

    lines.append(random.choice(GREETINGS).format(name=name))

    # Streak
    today = datetime.now().date()
    streak = 0
    for i in range(30):
        d = (today - timedelta(days=i)).isoformat()
        has = any(t.get("date", "")[:10] == d for t in training)
        if has:
            streak += 1
        elif i > 0:
            break

    if streak > 0:
        lines.append(f"🔥 {streak}-day streak. Don't break the chain.")
    else:
        lines.append("No activity yesterday. Today fixes that.")

    # Benchmark nudge
    last_test = history[0] if history else None
    if last_test:
        test_date = datetime.fromisoformat(last_test["date"].replace("Z", "+00:00"))
        days_ago = (datetime.now(test_date.tzinfo) - test_date).days
        if days_ago > 14:
            lines.append(f"It's been {days_ago} days since your last test. Time to retest.")
        else:
            tname = {"garage": "Garage Test", "cooper": "Cooper Test"}.get(
                last_test.get("type", ""), last_test.get("route", "test")
            )
            score = last_test.get("score", "--")
            lines.append(f"Last {tname}: {score} pts. Keep training and beat it.")
    else:
        lines.append("You haven't benchmarked yet. Set your baseline when you're ready.")

    lines.append(random.choice(CLOSERS))
    return "\n".join(lines)


def send_daily_sms():
    """Called by the scheduler."""
    data = load_data()
    profile = data.get("profile", {})
    phone = profile.get("phone", "")
    msg_time = profile.get("msgTime", "none")
    if not phone or msg_time == "none":
        return

    client = get_twilio_client()
    if not client:
        print("[SMS] Twilio not configured, skipping daily message")
        return

    message = build_daily_message(
        profile,
        data.get("history", []),
        data.get("training", []),
    )
    try:
        client.messages.create(body=message, from_=TWILIO_FROM, to=phone)
        print(f"[SMS] Sent daily message to {phone}")
    except Exception as e:
        print(f"[SMS] Error: {e}")


# ─── Scheduler ───

scheduler = BackgroundScheduler()


def reschedule_sms(profile):
    scheduler.remove_all_jobs()
    msg_time = profile.get("msgTime", "none")
    if msg_time == "none" or not profile.get("phone"):
        print("[SMS] Daily messages disabled")
        return

    hour_map = {"6am": 6, "7am": 7, "8am": 8}
    hour = hour_map.get(msg_time, 7)
    scheduler.add_job(send_daily_sms, "cron", hour=hour, minute=0, id="daily_sms")
    print(f"[SMS] Scheduled daily message at {hour}:00")


@app.route("/api/sms/generate", methods=["POST"])
def generate_message():
    """Generate a preview message without sending."""
    data = load_data()
    body = request.json or {}
    profile = data.get("profile", {})
    if body.get("name"):
        profile["name"] = body["name"]
    message = build_daily_message(
        profile,
        data.get("history", []),
        data.get("training", []),
    )
    return jsonify({"message": message})


# ─── Coach API ───

from coach.profile import load_profile as load_athlete_profile, update_profile, get_unknowns
from coach.readiness import save_checkin, get_checkin, get_recent_checkins, compute_readiness_score
from coach.health import save_health_score, get_health_score, get_yesterday_exertion, compute_health_readiness
from coach.history import get_provider as get_history_provider
from coach.trails import get_all_trails, get_trail, update_trail_status, search_trails
from coach.engine import recommend_workout


@app.route("/api/coach/profile", methods=["GET"])
def coach_profile():
    return jsonify(load_athlete_profile())


@app.route("/api/coach/profile", methods=["POST"])
def coach_profile_update():
    updates = request.json or {}
    return jsonify(update_profile(updates))


@app.route("/api/coach/profile/unknowns", methods=["GET"])
def coach_unknowns():
    return jsonify({"unknowns": get_unknowns()})


@app.route("/api/coach/checkin", methods=["POST"])
def coach_checkin():
    body = request.json or {}
    try:
        record = save_checkin(body)
        score, label = compute_readiness_score(record)
        return jsonify({"checkin": record, "readiness": {"score": score, "label": label}})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/coach/checkin/<checkin_date>", methods=["GET"])
def coach_checkin_get(checkin_date):
    checkin = get_checkin(checkin_date)
    if not checkin:
        return jsonify({"error": "No check-in for this date"}), 404
    score, label = compute_readiness_score(checkin)
    return jsonify({"checkin": checkin, "readiness": {"score": score, "label": label}})


@app.route("/api/coach/checkins/recent", methods=["GET"])
def coach_checkins_recent():
    days = int(request.args.get("days", 7))
    return jsonify(get_recent_checkins(days))


@app.route("/api/coach/health", methods=["POST"])
def coach_health_save():
    body = request.json or {}
    try:
        record = save_health_score(body)
        yesterday_ex = get_yesterday_exertion(record["date"])
        score, label = compute_health_readiness(record, yesterday_ex)
        return jsonify({"health": record, "readiness": {"score": score, "label": label}})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/coach/health/<health_date>", methods=["GET"])
def coach_health_get(health_date):
    health = get_health_score(health_date)
    if not health:
        return jsonify({"error": "No health score for this date"}), 404
    yesterday_ex = get_yesterday_exertion(health_date)
    score, label = compute_health_readiness(health, yesterday_ex)
    return jsonify({"health": health, "readiness": {"score": score, "label": label}})


@app.route("/api/coach/health/upload", methods=["POST"])
def coach_health_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".heic"):
        return jsonify({"error": "Unsupported file type"}), 400
    health_date = request.form.get("date", "")
    if not health_date:
        return jsonify({"error": "Missing date"}), 400
    safe_name = health_date + ext
    dest = UPLOADS_DIR / safe_name
    f.save(str(dest))
    return jsonify({"filename": safe_name, "date": health_date})


@app.route("/api/coach/history", methods=["GET"])
def coach_history():
    source = request.args.get("source", "mock")
    days = int(request.args.get("days", 42))
    try:
        provider = get_history_provider(source)
        return jsonify({"activities": provider.get_activities(days)})
    except (ValueError, NotImplementedError) as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/coach/history/weekly", methods=["GET"])
def coach_history_weekly():
    source = request.args.get("source", "mock")
    weeks = int(request.args.get("weeks", 6))
    try:
        provider = get_history_provider(source)
        return jsonify({"summaries": provider.get_weekly_summary(weeks)})
    except (ValueError, NotImplementedError) as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/coach/recommend", methods=["GET"])
def coach_recommend():
    from datetime import date as dt_date
    date_str = request.args.get("date")
    if date_str:
        parts = date_str.split("-")
        target = dt_date(int(parts[0]), int(parts[1]), int(parts[2]))
    else:
        target = dt_date.today()
    result = recommend_workout(target_date=target)
    return jsonify(result)


@app.route("/api/coach/trails", methods=["GET"])
def coach_trails():
    return jsonify({"trails": get_all_trails()})


@app.route("/api/coach/trails/<trail_id>", methods=["GET"])
def coach_trail(trail_id):
    trail = get_trail(trail_id)
    if not trail:
        return jsonify({"error": "Trail not found"}), 404
    return jsonify(trail)


@app.route("/api/coach/trails/<trail_id>/status", methods=["POST"])
def coach_trail_status(trail_id):
    body = request.json or {}
    try:
        trail = update_trail_status(
            trail_id,
            body.get("status", "unknown"),
            body.get("source", "manual"),
            body.get("checkedAt"),
        )
        return jsonify(trail)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ─── Bonus tracker (social media growth → bonus owed) ───

def _csrf_token():
    token = session.get("bonus_csrf")
    if not token:
        token = secrets.token_urlsafe(24)
        session["bonus_csrf"] = token
    return token


def _current_user():
    return session.get("bonus_user")


def require_login(view):
    """Logged-in only. Writes must also carry the CSRF token from /api/bonus/me."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if not user:
            return jsonify({"error": "login required"}), 401
        if request.method != "GET":
            sent = request.headers.get("X-CSRF-Token", "")
            if not sent or not secrets.compare_digest(sent, session.get("bonus_csrf", "")):
                return jsonify({"error": "bad or missing CSRF token"}), 403
        return view(*args, **kwargs)
    return wrapper


def require_admin(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if not user or user.get("role") != "admin":
            return jsonify({"error": "admins only"}), 403
        return view(*args, **kwargs)
    return wrapper


@app.route("/bonus")
def bonus_page():
    return send_from_directory(".", "bonus.html")


@app.route("/api/bonus/login", methods=["POST"])
def bonus_login():
    body = request.json or {}
    try:
        user = bonus_auth.verify(body.get("username"), body.get("password"))
    except PermissionError as locked:
        minutes = max(1, int(locked.args[0]) // 60)
        return jsonify({"error": "Too many attempts. Try again in %d minutes." % minutes}), 429
    if not user:
        return jsonify({"error": "Wrong username or password."}), 401
    session.clear()
    session.permanent = True
    session["bonus_user"] = user
    return jsonify({"user": user, "csrfToken": _csrf_token()})


@app.route("/api/bonus/logout", methods=["POST"])
def bonus_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/bonus/me")
def bonus_me():
    user = _current_user()
    if not user:
        return jsonify({"user": None, "hasAccounts": bool(bonus_auth.load_users())}), 401
    return jsonify({"user": user, "csrfToken": _csrf_token(), "metrics": bonus_store.METRICS})


@app.route("/api/bonus/months")
@require_login
def bonus_months():
    return jsonify({"months": bonus_store.list_months()})


@app.route("/api/bonus/rates")
@require_login
def bonus_rates():
    return jsonify({"rates": bonus_store.get_rates()})


@app.route("/api/bonus/rates", methods=["POST"])
@require_login
@require_admin
def bonus_rates_update():
    try:
        rates = bonus_store.set_rates((request.json or {}).get("rates"))
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"rates": rates})


@app.route("/api/bonus/month/<month>")
@require_login
def bonus_month(month):
    try:
        return jsonify(bonus_store.compute_month(month))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/bonus/month/<month>", methods=["POST"])
@require_login
def bonus_month_save(month):
    body = request.json or {}
    try:
        view = bonus_store.save_month(month, body.get("values"), _current_user()["displayName"])
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(view)


@app.route("/api/bonus/month/<month>/paid", methods=["POST"])
@require_login
@require_admin
def bonus_month_paid(month):
    body = request.json or {}
    paid = bool(body.get("paid"))
    paid_on = body.get("paidOn") or datetime.now().strftime("%Y-%m-%d")
    try:
        view = bonus_store.set_paid(month, paid, paid_on, _current_user()["displayName"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(view)


# ─── Boot ───

if __name__ == "__main__":
    scheduler.start()
    data = load_data()
    if data.get("profile"):
        reschedule_sms(data["profile"])
    print("\n  Fitness Test Demo")
    print("  http://localhost:8090\n")
    if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM]):
        print("  ⚠  Twilio not configured. Set env vars to enable SMS:")
        print("     TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER\n")
    else:
        print(f"  ✓  Twilio ready (from {TWILIO_FROM})\n")
    port = int(os.environ.get("PORT", 8090))
    app.run(host="0.0.0.0", port=port, debug=False)
