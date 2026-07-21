"""Training history adapter with mock and future provider interfaces."""

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests as http_requests

DATA_DIR = Path(__file__).parent.parent
USER_DATA_FILE = DATA_DIR / "user_data.json"

STRAVA_TYPE_MAP = {
    "ride": "mtb_ride",
    "mountainbikeride": "mtb_ride",
    "virtualride": "mtb_ride",
    "ebikeride": "mtb_ride",
    "gravelride": "mtb_ride",
    "run": "run",
    "walk": "walk",
    "hike": "hike",
    "weighttraining": "strength",
    "workout": "strength",
    "yoga": "mobility",
}


def _load_user_data():
    if USER_DATA_FILE.exists():
        return json.loads(USER_DATA_FILE.read_text())
    return {}


def _save_user_data(data):
    USER_DATA_FILE.write_text(json.dumps(data, indent=2))


def _refresh_strava_token(strava_data):
    if strava_data.get("expires_at", 0) > time.time() + 60:
        return strava_data["access_token"]

    client_id = os.environ.get("STRAVA_CLIENT_ID", "")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return None

    resp = http_requests.post("https://www.strava.com/oauth/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": strava_data["refresh_token"],
        "grant_type": "refresh_token",
    }, timeout=15)

    if resp.status_code != 200:
        return None

    tokens = resp.json()
    data = _load_user_data()
    data["strava"]["access_token"] = tokens["access_token"]
    data["strava"]["refresh_token"] = tokens["refresh_token"]
    data["strava"]["expires_at"] = tokens["expires_at"]
    _save_user_data(data)
    return tokens["access_token"]


def _estimate_rpe(activity):
    """Estimate RPE from Strava suffer_score and avg HR."""
    suffer = activity.get("suffer_score")
    if suffer is not None:
        if suffer >= 150:
            return 9
        if suffer >= 100:
            return 8
        if suffer >= 60:
            return 7
        if suffer >= 30:
            return 5
        return 3
    avg_hr = activity.get("avg_hr")
    if avg_hr is not None:
        if avg_hr >= 170:
            return 8
        if avg_hr >= 150:
            return 7
        if avg_hr >= 130:
            return 5
        return 3
    duration = activity.get("duration_min", 0)
    if duration >= 120:
        return 6
    if duration >= 60:
        return 5
    return 4


def _normalize_strava_activity(raw):
    strava_type = raw.get("type", "").lower().replace(" ", "")
    mapped_type = STRAVA_TYPE_MAP.get(strava_type, "other")

    date_str = raw.get("date", raw.get("start_date_local", ""))
    if "T" in date_str:
        date_str = date_str[:10]

    distance_miles = raw.get("distance", 0)
    if isinstance(distance_miles, (int, float)) and distance_miles > 100:
        distance_miles = round(distance_miles / 1609.34, 2)

    duration_min = raw.get("duration_min", 0)
    if duration_min == 0:
        duration_min = round(raw.get("moving_time", 0) / 60, 1) if raw.get("moving_time") else 0

    elevation_feet = raw.get("elevation_gain", 0)
    if elevation_feet == 0 and raw.get("total_elevation_gain"):
        elevation_feet = round(raw["total_elevation_gain"] * 3.281, 0)

    normalized = {
        "strava_id": raw.get("id"),
        "date": date_str,
        "type": mapped_type,
        "title": raw.get("name", "Strava Activity"),
        "durationMinutes": duration_min,
        "distanceMiles": distance_miles,
        "elevationFeet": elevation_feet,
        "avg_hr": raw.get("avg_hr") or raw.get("average_heartrate"),
        "max_hr": raw.get("max_hr") or raw.get("max_heartrate"),
        "suffer_score": raw.get("suffer_score"),
        "source": "strava",
    }
    normalized["rpe"] = _estimate_rpe(normalized)
    return normalized


class TrainingHistoryProvider:
    def get_activities(self, days=42):
        raise NotImplementedError

    def get_weekly_summary(self, weeks=6):
        raise NotImplementedError


class MockHistoryProvider(TrainingHistoryProvider):
    def __init__(self):
        self._activities = self._generate_mock_data()

    def _generate_mock_data(self):
        today = date.today()
        activities = []

        for week_offset in range(6):
            week_start = today - timedelta(days=today.weekday() + 7 * week_offset)

            activities.append({
                "date": (week_start).isoformat(),
                "type": "mtb_ride",
                "title": "Easy Trail Spin",
                "durationMinutes": 75,
                "distanceMiles": 12,
                "elevationFeet": 800,
                "rpe": 4,
                "notes": None,
                "source": "mock",
            })

            activities.append({
                "date": (week_start + timedelta(days=1)).isoformat(),
                "type": "strength",
                "title": "Upper Body + Core",
                "durationMinutes": 40,
                "distanceMiles": None,
                "elevationFeet": None,
                "rpe": 6,
                "notes": None,
                "source": "mock",
            })

            activities.append({
                "date": (week_start + timedelta(days=2)).isoformat(),
                "type": "mtb_ride",
                "title": "Interval Climbs",
                "durationMinutes": 90,
                "distanceMiles": 15,
                "elevationFeet": 2200,
                "rpe": 7 + (1 if week_offset < 2 else 0),
                "notes": None,
                "source": "mock",
            })

            activities.append({
                "date": (week_start + timedelta(days=3)).isoformat(),
                "type": "mobility",
                "title": "Morning Mobility",
                "durationMinutes": 10,
                "distanceMiles": None,
                "elevationFeet": None,
                "rpe": 2,
                "notes": None,
                "source": "mock",
            })

            activities.append({
                "date": (week_start + timedelta(days=4)).isoformat(),
                "type": "strength",
                "title": "Lower Body",
                "durationMinutes": 45,
                "distanceMiles": None,
                "elevationFeet": None,
                "rpe": 6,
                "notes": None,
                "source": "mock",
            })

            activities.append({
                "date": (week_start + timedelta(days=5)).isoformat(),
                "type": "mtb_ride",
                "title": "Long Endurance Ride",
                "durationMinutes": 150,
                "distanceMiles": 25,
                "elevationFeet": 3000,
                "rpe": 5,
                "notes": None,
                "source": "mock",
            })

        return sorted(activities, key=lambda a: a["date"], reverse=True)

    def get_activities(self, days=42):
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        return [a for a in self._activities if a["date"] >= cutoff]

    def get_weekly_summary(self, weeks=6):
        activities = self.get_activities(days=weeks * 7)
        summaries = []
        today = date.today()

        for w in range(weeks):
            week_start = today - timedelta(days=today.weekday() + 7 * w)
            week_end = week_start + timedelta(days=6)
            ws = week_start.isoformat()
            we = week_end.isoformat()

            week_acts = [a for a in activities if ws <= a["date"] <= we]

            rides = [a for a in week_acts if a["type"] == "mtb_ride"]
            total_miles = sum(a.get("distanceMiles") or 0 for a in rides)
            total_elevation = sum(a.get("elevationFeet") or 0 for a in rides)
            total_ride_min = sum(a.get("durationMinutes") or 0 for a in rides)
            total_duration = sum(a.get("durationMinutes") or 0 for a in week_acts)

            high_intensity_days = len([a for a in week_acts if (a.get("rpe") or 0) >= 7])

            summaries.append({
                "weekStart": ws,
                "weekEnd": we,
                "totalSessions": len(week_acts),
                "rideSessions": len(rides),
                "totalRideMiles": total_miles,
                "totalElevationFeet": total_elevation,
                "totalRideMinutes": total_ride_min,
                "totalDurationMinutes": total_duration,
                "highIntensityDays": high_intensity_days,
            })

        return summaries


class StravaProvider(TrainingHistoryProvider):
    def __init__(self):
        data = _load_user_data()
        self._strava = data.get("strava")
        if not self._strava or not self._strava.get("access_token"):
            raise ConnectionError("Strava not connected")

    def _fetch_activities(self, days):
        token = _refresh_strava_token(self._strava)
        if not token:
            raise ConnectionError("Strava token refresh failed")

        after = int((date.today() - timedelta(days=days)).strftime("%s"))
        all_activities = []
        page = 1
        while True:
            resp = http_requests.get(
                "https://www.strava.com/api/v3/athlete/activities",
                headers={"Authorization": f"Bearer {token}"},
                params={"after": after, "page": page, "per_page": 100},
                timeout=15,
            )
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            all_activities.extend(batch)
            if len(batch) < 100:
                break
            page += 1

        return all_activities

    def get_activities(self, days=42):
        raw_activities = self._fetch_activities(days)
        seen_ids = set()
        normalized = []
        for raw in raw_activities:
            sid = raw.get("id")
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            act = _normalize_strava_activity(raw)
            normalized.append(act)

        return sorted(normalized, key=lambda a: a["date"], reverse=True)

    def get_weekly_summary(self, weeks=6):
        activities = self.get_activities(days=weeks * 7)
        summaries = []
        today = date.today()

        for w in range(weeks):
            week_start = today - timedelta(days=today.weekday() + 7 * w)
            week_end = week_start + timedelta(days=6)
            ws = week_start.isoformat()
            we = week_end.isoformat()

            week_acts = [a for a in activities if ws <= a["date"] <= we]

            rides = [a for a in week_acts if a["type"] == "mtb_ride"]
            total_miles = sum(a.get("distanceMiles") or 0 for a in rides)
            total_elevation = sum(a.get("elevationFeet") or 0 for a in rides)
            total_ride_min = sum(a.get("durationMinutes") or 0 for a in rides)
            total_duration = sum(a.get("durationMinutes") or 0 for a in week_acts)

            high_intensity_days = len([a for a in week_acts if (a.get("rpe") or 0) >= 7])

            summaries.append({
                "weekStart": ws,
                "weekEnd": we,
                "totalSessions": len(week_acts),
                "rideSessions": len(rides),
                "totalRideMiles": total_miles,
                "totalElevationFeet": total_elevation,
                "totalRideMinutes": total_ride_min,
                "totalDurationMinutes": total_duration,
                "highIntensityDays": high_intensity_days,
            })

        return summaries


class AppleHealthProvider(TrainingHistoryProvider):
    """Placeholder for future Apple Health import."""
    def get_activities(self, days=42):
        raise NotImplementedError("Apple Health import not yet implemented")

    def get_weekly_summary(self, weeks=6):
        raise NotImplementedError("Apple Health import not yet implemented")


def is_strava_connected():
    try:
        data = _load_user_data()
        strava = data.get("strava")
        return bool(strava and strava.get("access_token"))
    except Exception:
        return False


def get_provider(source="mock"):
    providers = {
        "mock": MockHistoryProvider,
        "strava": StravaProvider,
        "apple_health": AppleHealthProvider,
    }
    cls = providers.get(source)
    if cls is None:
        raise ValueError(f"Unknown history provider: {source}")
    return cls()
