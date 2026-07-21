"""Local trail provider service."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent
TRAILS_FILE = DATA_DIR / "trails.json"

VALID_STATUSES = ["confirmed_open", "confirmed_closed", "unknown"]

DEFAULT_TRAILS = [
    {
        "id": "potawatomi",
        "name": "Potawatomi Trail",
        "city": "Pinckney",
        "state": "MI",
        "latitude": 42.4339,
        "longitude": -83.9458,
        "trailforksUrl": "https://www.trailforks.com/region/potawatomi-trail/",
        "totalMileageEstimate": 17.5,
        "routeOptions": ["full loop", "east loop (10mi)", "west loop (7mi)"],
        "difficulty": "intermediate",
        "technicalRating": 3,
        "climbingCharacter": "rolling hills, short punchy climbs",
        "surface": "singletrack, dirt",
        "directionRules": "one-way counterclockwise",
        "wetWeatherSensitivity": "high",
        "typicalDurationMinutes": 120,
        "status": "unknown",
        "statusSource": "local database — not verified",
        "statusCheckedAt": None,
        "notes": "Popular SE Michigan trail. Sandy soil drains moderately.",
    },
    {
        "id": "dw",
        "name": "DTE Energy Foundation Trail (DW)",
        "city": "Brighton",
        "state": "MI",
        "latitude": 42.5200,
        "longitude": -83.8100,
        "trailforksUrl": "https://www.trailforks.com/region/brighton-recreation-area/",
        "totalMileageEstimate": 18,
        "routeOptions": ["full loop", "north loop (8mi)", "south loop (10mi)"],
        "difficulty": "intermediate-advanced",
        "technicalRating": 4,
        "climbingCharacter": "sustained climbs, rocky technical sections",
        "surface": "singletrack, rocky, rooty",
        "directionRules": "one-way",
        "wetWeatherSensitivity": "moderate",
        "typicalDurationMinutes": 130,
        "status": "unknown",
        "statusSource": "local database — not verified",
        "statusCheckedAt": None,
        "notes": "Technical Michigan trail with good elevation for the area.",
    },
    {
        "id": "island_lake",
        "name": "Island Lake Recreation Area",
        "city": "Brighton",
        "state": "MI",
        "latitude": 42.5100,
        "longitude": -83.7400,
        "trailforksUrl": "https://www.trailforks.com/region/island-lake-recreation-area/",
        "totalMileageEstimate": 8,
        "routeOptions": ["full loop"],
        "difficulty": "beginner-intermediate",
        "technicalRating": 2,
        "climbingCharacter": "gentle rolling",
        "surface": "singletrack, packed dirt",
        "directionRules": "one-way",
        "wetWeatherSensitivity": "high",
        "typicalDurationMinutes": 60,
        "status": "unknown",
        "statusSource": "local database — not verified",
        "statusCheckedAt": None,
        "notes": "Good recovery/easy day trail.",
    },
    {
        "id": "stony_creek",
        "name": "Stony Creek Metropark",
        "city": "Shelby Township",
        "state": "MI",
        "latitude": 42.7300,
        "longitude": -83.0700,
        "trailforksUrl": "https://www.trailforks.com/region/stony-creek-metropark/",
        "totalMileageEstimate": 6,
        "routeOptions": ["full loop"],
        "difficulty": "beginner",
        "technicalRating": 1,
        "climbingCharacter": "flat to gentle",
        "surface": "singletrack, packed dirt",
        "directionRules": "two-way",
        "wetWeatherSensitivity": "moderate",
        "typicalDurationMinutes": 45,
        "status": "unknown",
        "statusSource": "local database — not verified",
        "statusCheckedAt": None,
        "notes": "Easy loop for recovery rides.",
    },
    {
        "id": "holdridge",
        "name": "Holdridge Lakes Mountain Bike Area",
        "city": "Clarkston",
        "state": "MI",
        "latitude": 42.7200,
        "longitude": -83.4300,
        "trailforksUrl": "https://www.trailforks.com/region/holdridge-lakes-mba/",
        "totalMileageEstimate": 12,
        "routeOptions": ["full system", "intermediate loop (7mi)"],
        "difficulty": "intermediate-advanced",
        "technicalRating": 4,
        "climbingCharacter": "steep punchy climbs, fast descents",
        "surface": "singletrack, rocky, sandy",
        "directionRules": "one-way varies by trail",
        "wetWeatherSensitivity": "low",
        "typicalDurationMinutes": 90,
        "status": "confirmed_open",
        "statusSource": "local user report",
        "statusCheckedAt": "2026-07-18",
        "notes": "Sandy soil drains fast. Good race-simulation terrain.",
    },
]


def _load_trails():
    if TRAILS_FILE.exists():
        return json.loads(TRAILS_FILE.read_text())
    return list(DEFAULT_TRAILS)


def _save_trails(trails):
    TRAILS_FILE.write_text(json.dumps(trails, indent=2))


def get_all_trails():
    return _load_trails()


def get_trail(trail_id):
    trails = _load_trails()
    for t in trails:
        if t["id"] == trail_id:
            return t
    return None


def update_trail_status(trail_id, status, source, checked_at):
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    trails = _load_trails()
    for t in trails:
        if t["id"] == trail_id:
            t["status"] = status
            t["statusSource"] = source
            t["statusCheckedAt"] = checked_at
            _save_trails(trails)
            return t
    raise ValueError(f"Trail not found: {trail_id}")


def search_trails(workout_objective=None, min_miles=None, max_miles=None,
                  max_difficulty=None, exclude_closed=True):
    trails = _load_trails()
    results = []

    for t in trails:
        if exclude_closed and t["status"] == "confirmed_closed":
            continue
        if min_miles and t["totalMileageEstimate"] < min_miles:
            continue
        if max_miles and t["totalMileageEstimate"] > max_miles:
            continue
        results.append(t)

    return results


def rank_trails(trails, workout_type, target_miles=None, target_tech=None):
    scored = []
    for t in trails:
        if t["status"] == "confirmed_closed":
            continue

        score = 0.0

        if workout_type == "mtb_ride":
            if t.get("technicalRating", 0) >= 3:
                score += 30
            else:
                score += 15
        elif workout_type == "recovery":
            if t.get("technicalRating", 0) <= 2:
                score += 30
            else:
                score += 10

        if target_miles:
            diff = abs(t["totalMileageEstimate"] - target_miles)
            score += max(0, 20 - diff * 2)

        if target_tech:
            diff = abs(t.get("technicalRating", 2) - target_tech)
            score += max(0, 15 - diff * 5)

        if t["status"] == "confirmed_open":
            score += 10
        elif t["status"] == "unknown":
            score += 3

        if t.get("wetWeatherSensitivity") == "low":
            score += 5

        scored.append({"trail": t, "score": round(score, 1)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
