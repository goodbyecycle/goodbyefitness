"""Athlytic health score storage and readiness integration."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent
HEALTH_FILE = DATA_DIR / "health_scores.json"


def _load_scores():
    if HEALTH_FILE.exists():
        return json.loads(HEALTH_FILE.read_text())
    return {}


def _save_scores(data):
    HEALTH_FILE.write_text(json.dumps(data, indent=2))


def save_health_score(entry):
    if "date" not in entry:
        raise ValueError("Missing required field: date")

    recovery = entry.get("recovery")
    if recovery is None or not (0 <= recovery <= 100):
        raise ValueError("recovery must be 0-100")

    sleep = entry.get("sleep")
    if sleep is None or not (0 <= sleep <= 100):
        raise ValueError("sleep must be 0-100")

    exertion = entry.get("exertion")
    if exertion is None or not (0 <= exertion <= 10):
        raise ValueError("exertion must be 0-10")

    record = {
        "date": entry["date"],
        "recovery": recovery,
        "sleep": sleep,
        "exertion": round(float(exertion), 1),
        "hasScreenshot": bool(entry.get("hasScreenshot", False)),
    }

    all_scores = _load_scores()
    all_scores[entry["date"]] = record
    _save_scores(all_scores)
    return record


def get_health_score(score_date):
    all_scores = _load_scores()
    return all_scores.get(score_date)


def get_yesterday_exertion(today_str):
    from datetime import date, timedelta
    parts = today_str.split("-")
    today = date(int(parts[0]), int(parts[1]), int(parts[2]))
    yesterday = (today - timedelta(days=1)).isoformat()
    all_scores = _load_scores()
    yesterday_score = all_scores.get(yesterday)
    if yesterday_score:
        return yesterday_score.get("exertion", 0)
    return None


def compute_health_readiness(health_score, yesterday_exertion=None):
    if health_score is None:
        return None, "no health score"

    recovery = health_score["recovery"]
    sleep = health_score["sleep"]
    exertion = health_score.get("exertion", 0)

    score = (recovery * 0.5) + (sleep * 0.5)

    if yesterday_exertion is not None and yesterday_exertion >= 7:
        penalty = (yesterday_exertion - 6) * 5
        score = max(1, score - penalty)

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
