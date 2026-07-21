"""Athlete profile service."""

import json
from copy import deepcopy
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent
PROFILE_FILE = DATA_DIR / "athlete_profile.json"

DEFAULT_PROFILE = {
    "athlete": {
        "name": "Andrew",
        "ageGroup": 50,
        "primarySport": "Enduro MTB",
        "primaryGoal": "Become a highly competitive 50-year-old Enduro MTB racer",
        "weeklyMtbMileageTargetMiles": 70,
        "preferredStrengthStyle": ["bodyweight", "portable equipment"],
        "homeTimezone": "America/Detroit",
    },
    "knownRoutines": {
        "morningMobilityMinutes": 10,
        "eveningPreparation": True,
    },
    "dataSources": {
        "strava": "planned",
        "appleHealth": "planned",
        "whoop": "later",
        "manualCheckIn": "required until integrations are complete",
    },
    "availability": {
        "weeklyHours": None,
        "preferredTrainingDays": [],
        "workCalendarConnected": False,
    },
    "benchmarks": {
        "ftpWatts": None,
        "maxHeartRate": None,
        "lactateThresholdHeartRate": None,
        "longestRecentRideMiles": None,
        "averageWeeklyRideMiles42d": None,
        "currentStrengthBenchmarks": {},
    },
    "limitations": {
        "injuries": [],
        "pain": [],
        "medicalRestrictions": [],
    },
    "status": "incomplete",
}


def load_profile():
    if PROFILE_FILE.exists():
        return json.loads(PROFILE_FILE.read_text())
    return deepcopy(DEFAULT_PROFILE)


def save_profile(profile):
    PROFILE_FILE.write_text(json.dumps(profile, indent=2))


def update_profile(updates):
    profile = load_profile()
    for section, values in updates.items():
        if section in profile and isinstance(profile[section], dict) and isinstance(values, dict):
            profile[section].update(values)
        else:
            profile[section] = values
    save_profile(profile)
    return profile


def get_unknowns():
    profile = load_profile()
    unknowns = []

    benchmarks = profile.get("benchmarks", {})
    for key, val in benchmarks.items():
        if val is None or val == {}:
            unknowns.append(f"benchmarks.{key}")

    avail = profile.get("availability", {})
    if avail.get("weeklyHours") is None:
        unknowns.append("availability.weeklyHours")
    if not avail.get("preferredTrainingDays"):
        unknowns.append("availability.preferredTrainingDays")

    return unknowns
