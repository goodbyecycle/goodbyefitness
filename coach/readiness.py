"""Daily readiness check-in service."""

import json
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent
CHECKIN_FILE = DATA_DIR / "checkins.json"


def _load_checkins():
    if CHECKIN_FILE.exists():
        return json.loads(CHECKIN_FILE.read_text())
    return {}


def _save_checkins(data):
    CHECKIN_FILE.write_text(json.dumps(data, indent=2))


def save_checkin(checkin):
    required = ["sleepQuality", "energy", "soreness"]
    for field in required:
        if field not in checkin:
            raise ValueError(f"Missing required field: {field}")

    if not 1 <= checkin["sleepQuality"] <= 5:
        raise ValueError("sleepQuality must be 1-5")
    if not 1 <= checkin["energy"] <= 5:
        raise ValueError("energy must be 1-5")
    if not 0 <= checkin["soreness"] <= 10:
        raise ValueError("soreness must be 0-10")

    pain = checkin.get("pain", 0)
    if not 0 <= pain <= 10:
        raise ValueError("pain must be 0-10")
    if pain > 0 and not checkin.get("painLocation"):
        raise ValueError("painLocation required when pain > 0")

    stress = checkin.get("stress", 3)
    if not 1 <= stress <= 5:
        raise ValueError("stress must be 1-5")

    checkin_date = checkin.get("date", date.today().isoformat())

    record = {
        "date": checkin_date,
        "sleepQuality": checkin["sleepQuality"],
        "energy": checkin["energy"],
        "soreness": checkin["soreness"],
        "pain": pain,
        "painLocation": checkin.get("painLocation"),
        "stress": stress,
        "timeAvailableMinutes": checkin.get("timeAvailableMinutes"),
        "indoorOutdoor": checkin.get("indoorOutdoor", "no_preference"),
        "currentLocation": checkin.get("currentLocation"),
    }

    all_checkins = _load_checkins()
    all_checkins[checkin_date] = record
    _save_checkins(all_checkins)
    return record


def get_checkin(checkin_date=None):
    if checkin_date is None:
        checkin_date = date.today().isoformat()
    all_checkins = _load_checkins()
    return all_checkins.get(checkin_date)


def get_recent_checkins(days=7):
    all_checkins = _load_checkins()
    today = date.today()
    recent = {}
    for i in range(days):
        d = date(today.year, today.month, today.day)
        from datetime import timedelta
        d = today - timedelta(days=i)
        key = d.isoformat()
        if key in all_checkins:
            recent[key] = all_checkins[key]
    return recent


def compute_readiness_score(checkin):
    if checkin is None:
        return None, "no check-in data"

    sleep = checkin["sleepQuality"]
    energy = checkin["energy"]
    soreness = checkin["soreness"]
    pain = checkin.get("pain", 0)
    stress = checkin.get("stress", 3)

    if pain >= 7:
        return 1, "significant pain reported — rest or seek evaluation"

    score = (
        (sleep / 5.0) * 25 +
        (energy / 5.0) * 25 +
        ((10 - soreness) / 10.0) * 20 +
        ((10 - pain) / 10.0) * 15 +
        ((5 - stress) / 4.0) * 15
    )
    score = max(1, min(100, round(score)))

    if score >= 75:
        label = "good — normal training"
    elif score >= 50:
        label = "moderate — reduce intensity or volume"
    elif score >= 30:
        label = "low — recovery or easy movement only"
    else:
        label = "very low — rest recommended"

    return score, label
