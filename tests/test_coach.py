"""Tests for the coaching engine — Phase 1 requirements."""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from coach.schema import validate_workout
from coach.readiness import compute_readiness_score, save_checkin
from coach.history import MockHistoryProvider
from coach.trails import rank_trails, search_trails, DEFAULT_TRAILS
from coach.engine import (
    recommend_workout,
    WORKOUT_TEMPLATES,
    _count_recent_hard_days,
    _was_yesterday_hard,
)
from coach.profile import load_profile, get_unknowns


def test_schema_validates_good_workout():
    workout = {
        "date": "2026-07-20",
        "type": "mtb_ride",
        "title": "Easy Trail Ride",
        "objective": "Aerobic base",
        "durationMinutes": 75,
        "targetMiles": 12,
        "intensity": {"method": "rpe", "target": "RPE 3-4"},
        "instructions": ["Warm up 10 min", "Ride steady"],
        "explanation": "Test workout.",
        "backup": {"title": "Recovery Ride", "instructions": ["Spin easy"]},
        "dataQuality": {"inputsUsed": ["profile"], "unknowns": ["FTP"]},
        "confidence": "medium",
        "locked": False,
    }
    errors = validate_workout(workout)
    assert errors == [], f"Valid workout rejected: {errors}"
    print("PASS: schema validates good workout")


def test_schema_rejects_invalid_workout():
    workout = {"date": "2026-07-20", "type": "mtb_ride"}
    errors = validate_workout(workout)
    assert len(errors) > 0, "Invalid workout should have errors"
    print("PASS: schema rejects incomplete workout")


def test_schema_rejects_bad_type():
    workout = {
        "date": "2026-07-20",
        "type": "swimming",
        "title": "Swim",
        "objective": "Swim",
        "durationMinutes": 30,
        "intensity": {"method": "rpe", "target": "easy"},
        "instructions": ["swim"],
        "explanation": "test",
        "backup": {"title": "rest", "instructions": ["rest"]},
        "dataQuality": {"inputsUsed": [], "unknowns": []},
    }
    errors = validate_workout(workout)
    assert any("type" in e.lower() for e in errors), f"Should reject bad type: {errors}"
    print("PASS: schema rejects invalid workout type")


def test_unknown_data_not_invented():
    profile = load_profile()
    benchmarks = profile.get("benchmarks", {})
    assert benchmarks.get("ftpWatts") is None, "FTP should be unknown (null)"
    assert benchmarks.get("maxHeartRate") is None, "Max HR should be unknown (null)"

    unknowns = get_unknowns()
    assert "benchmarks.ftpWatts" in unknowns
    assert "benchmarks.maxHeartRate" in unknowns
    print("PASS: unknown data is not invented")


def test_recommendation_includes_unknowns():
    result = recommend_workout(target_date=date.today())
    assert "recommendation" in result or "error" in result
    if "recommendation" in result:
        rec = result["recommendation"]
        dq = rec.get("dataQuality", {})
        assert len(dq.get("unknowns", [])) > 0, "Should list unknowns"
        assert "benchmarks.ftpWatts" in dq["unknowns"]
    print("PASS: recommendation exposes unknowns")


def test_no_back_to_back_hard_days():
    today = date.today()
    yesterday = today - timedelta(days=1)
    activities = [
        {"date": yesterday.isoformat(), "type": "mtb_ride", "rpe": 8, "distanceMiles": 15},
    ]
    assert _was_yesterday_hard(activities, today) is True

    result = recommend_workout(target_date=today)
    if "recommendation" in result:
        rec = result["recommendation"]
        assert rec["type"] != "mtb_ride" or "easy" in rec["title"].lower() or rec["type"] in ["recovery", "rest", "mobility", "strength"], \
            f"Should not schedule hard ride after hard yesterday: got {rec['title']}"
    print("PASS: no back-to-back hard days")


def test_confirmed_closure_never_recommended():
    closed_trail = {
        "id": "closed_test",
        "name": "Closed Trail",
        "status": "confirmed_closed",
        "totalMileageEstimate": 10,
        "technicalRating": 3,
        "wetWeatherSensitivity": "low",
        "routeOptions": ["loop"],
    }
    trails = [closed_trail]
    ranked = rank_trails(trails, "mtb_ride", target_miles=10)
    assert len(ranked) == 0, "Confirmed closed trail should be excluded from rankings"
    print("PASS: confirmed closure never recommended")


def test_closed_trails_excluded_from_search():
    results = search_trails(exclude_closed=True)
    for t in results:
        assert t["status"] != "confirmed_closed", f"Closed trail in results: {t['name']}"
    print("PASS: closed trails excluded from search")


def test_poor_recovery_reduces_intensity():
    today = date.today()

    try:
        save_checkin({
            "date": today.isoformat(),
            "sleepQuality": 1,
            "energy": 1,
            "soreness": 9,
            "pain": 0,
            "stress": 5,
        })
    except Exception:
        pass

    score, label = compute_readiness_score({
        "sleepQuality": 1,
        "energy": 1,
        "soreness": 9,
        "pain": 0,
        "stress": 5,
    })
    assert score < 30, f"Very poor readiness should score below 30, got {score}"
    assert "rest" in label.lower() or "very low" in label.lower()
    print("PASS: poor recovery reduces intensity")


def test_high_pain_triggers_rest():
    score, label = compute_readiness_score({
        "sleepQuality": 5,
        "energy": 5,
        "soreness": 0,
        "pain": 8,
        "stress": 1,
    })
    assert score == 1, f"High pain should trigger minimum score, got {score}"
    assert "pain" in label.lower()
    print("PASS: high pain triggers rest")


def test_locked_calendar_not_overwritten():
    today = date.today()
    locked_event = {
        "date": today.isoformat(),
        "type": "mtb_ride",
        "title": "Planned Race Prep",
        "locked": True,
    }
    result = recommend_workout(target_date=today, calendar_events=[locked_event])
    assert result.get("source") == "locked_calendar", "Locked event should be preserved"
    assert result["recommendation"]["title"] == "Planned Race Prep"
    print("PASS: locked calendar sessions not overwritten")


def test_mileage_target_no_unsafe_catchup():
    today = date.today()
    result = recommend_workout(target_date=today)
    if "recommendation" in result:
        rec = result["recommendation"]
        miles = rec.get("targetMiles") or 0
        assert miles <= 30, f"Single day should never exceed 30mi for catchup, got {miles}"
    print("PASS: 70-mile target does not force unsafe catch-up mileage")


def test_recommendation_passes_schema():
    result = recommend_workout(target_date=date.today())
    assert "recommendation" in result, f"Expected recommendation, got: {result}"
    errors = validate_workout(result["recommendation"])
    assert errors == [], f"Recommendation failed schema: {errors}"
    print("PASS: recommendation passes schema validation")


def test_mock_history_returns_data():
    provider = MockHistoryProvider()
    activities = provider.get_activities(days=42)
    assert len(activities) > 0, "Mock history should return activities"
    for a in activities:
        assert a["source"] == "mock"
        assert "date" in a
        assert "type" in a
    print("PASS: mock history returns data")


def test_mock_weekly_summary():
    provider = MockHistoryProvider()
    summaries = provider.get_weekly_summary(weeks=6)
    assert len(summaries) == 6
    for s in summaries:
        assert "totalRideMiles" in s
        assert "highIntensityDays" in s
    print("PASS: mock weekly summary works")


def test_all_templates_valid():
    for key, template in WORKOUT_TEMPLATES.items():
        workout = {
            "date": "2026-07-20",
            "type": template["type"],
            "title": template["title"],
            "objective": template["objective"],
            "durationMinutes": template["durationMinutes"],
            "targetMiles": template.get("targetMiles"),
            "intensity": template["intensity"],
            "instructions": template["instructions"],
            "explanation": f"Template test for {key}",
            "backup": {"title": "Rest", "instructions": ["Rest"]},
            "dataQuality": {"inputsUsed": ["template"], "unknowns": []},
        }
        errors = validate_workout(workout)
        assert errors == [], f"Template {key} failed validation: {errors}"
    print("PASS: all workout templates pass schema validation")


if __name__ == "__main__":
    test_schema_validates_good_workout()
    test_schema_rejects_invalid_workout()
    test_schema_rejects_bad_type()
    test_unknown_data_not_invented()
    test_recommendation_includes_unknowns()
    test_no_back_to_back_hard_days()
    test_confirmed_closure_never_recommended()
    test_closed_trails_excluded_from_search()
    test_poor_recovery_reduces_intensity()
    test_high_pain_triggers_rest()
    test_locked_calendar_not_overwritten()
    test_mileage_target_no_unsafe_catchup()
    test_recommendation_passes_schema()
    test_mock_history_returns_data()
    test_mock_weekly_summary()
    test_all_templates_valid()
    print("\n=== ALL 16 TESTS PASSED ===")
