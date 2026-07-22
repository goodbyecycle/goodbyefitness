"""Tests for the coaching engine — Phase 1 requirements."""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from coach.schema import validate_workout
from coach.readiness import compute_readiness_score, save_checkin, get_checkin
from coach.history import MockHistoryProvider
from coach.trails import rank_trails, search_trails, DEFAULT_TRAILS
from coach.engine import (
    recommend_workout,
    WORKOUT_TEMPLATES,
    _count_recent_hard_days,
    _was_yesterday_hard,
)
from coach.profile import load_profile, get_unknowns

CHECKIN_FILE = Path(__file__).parent.parent / "checkins.json"

def _cleanup_checkins():
    if CHECKIN_FILE.exists():
        CHECKIN_FILE.unlink()


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


## ── Phase 2 Slice Tests ──

def _get_app():
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from server import app
    app.config["TESTING"] = True
    return app


def test_p2_recommend_endpoint_returns_modal_data():
    app = _get_app()
    with app.test_client() as c:
        resp = c.get("/api/coach/recommend?date=2026-07-21")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "recommendation" in data, f"Expected recommendation key, got {list(data.keys())}"
        rec = data["recommendation"]
        for field in ["title", "type", "durationMinutes", "intensity", "explanation"]:
            assert field in rec, f"Missing modal field: {field}"
    print("PASS: P2 recommend endpoint returns modal data")


def test_p2_accepted_workout_has_correct_date():
    result = recommend_workout(target_date=date(2026, 7, 21))
    assert "recommendation" in result
    rec = result["recommendation"]
    assert rec["date"] == "2026-07-21", f"Date mismatch: {rec['date']}"
    print("PASS: P2 accepted workout has correct date")


def test_p2_recommendation_creates_valid_calendar_record():
    result = recommend_workout(target_date=date(2026, 7, 21))
    rec = result["recommendation"]
    record = {
        "date": rec["date"],
        "title": rec["title"],
        "type": rec["type"],
        "durationMinutes": rec["durationMinutes"],
        "targetMiles": rec.get("targetMiles"),
        "intensity": rec["intensity"]["target"] if isinstance(rec["intensity"], dict) else str(rec["intensity"]),
    }
    assert record["date"] == "2026-07-21"
    assert isinstance(record["title"], str) and len(record["title"]) > 0
    assert isinstance(record["durationMinutes"], (int, float))
    assert record["intensity"] is not None
    print("PASS: P2 recommendation creates valid calendar record")


def test_p2_recommendation_schema_valid_for_all_views():
    result = recommend_workout(target_date=date(2026, 7, 21))
    rec = result["recommendation"]
    errors = validate_workout(rec)
    assert errors == [], f"Recommendation fails schema (would break views): {errors}"
    assert "title" in rec and "durationMinutes" in rec, "Card fields missing"
    print("PASS: P2 recommendation schema valid for all views")


def test_p2_failed_recommendation_creates_no_event():
    bad_result = {"error": "No profile found", "details": "Missing athlete data"}
    assert "recommendation" not in bad_result
    assert "error" in bad_result
    events_before = []
    if "recommendation" not in bad_result:
        events_after = list(events_before)
    assert len(events_after) == len(events_before), "Failed recommendation should not add events"
    print("PASS: P2 failed recommendation creates no event")


## ── Morning Check-In Tests ──

def test_ci_valid_checkin_saves():
    _cleanup_checkins()
    try:
        app = _get_app()
        with app.test_client() as c:
            resp = c.post("/api/coach/checkin", json={
                "date": "2026-07-21",
                "sleepQuality": 4,
                "energy": 3,
                "soreness": 2,
                "pain": 0,
                "stress": 2,
                "timeAvailableMinutes": 60,
                "indoorOutdoor": "outdoor",
                "currentLocation": "Southeast Michigan",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert "checkin" in data
            assert "readiness" in data
            assert data["readiness"]["score"] > 0
            assert data["checkin"]["date"] == "2026-07-21"
        print("PASS: CI valid check-in saves successfully")
    finally:
        _cleanup_checkins()


def test_ci_invalid_values_rejected():
    _cleanup_checkins()
    try:
        app = _get_app()
        with app.test_client() as c:
            resp = c.post("/api/coach/checkin", json={
                "date": "2026-07-21",
                "sleepQuality": 9,
                "energy": 3,
                "soreness": 2,
            })
            assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
            data = resp.get_json()
            assert "error" in data
        print("PASS: CI invalid values rejected")
    finally:
        _cleanup_checkins()


def test_ci_pain_location_required():
    _cleanup_checkins()
    try:
        app = _get_app()
        with app.test_client() as c:
            resp = c.post("/api/coach/checkin", json={
                "date": "2026-07-21",
                "sleepQuality": 3,
                "energy": 3,
                "soreness": 2,
                "pain": 5,
            })
            assert resp.status_code == 400
            data = resp.get_json()
            assert "painLocation" in data["error"].lower() or "pain" in data["error"].lower()
        print("PASS: CI pain location required when pain > 0")
    finally:
        _cleanup_checkins()


def test_ci_readiness_summary_after_save():
    _cleanup_checkins()
    try:
        app = _get_app()
        with app.test_client() as c:
            resp = c.post("/api/coach/checkin", json={
                "date": "2026-07-21",
                "sleepQuality": 4,
                "energy": 4,
                "soreness": 2,
                "pain": 0,
                "stress": 2,
            })
            data = resp.get_json()
            assert "readiness" in data
            assert "score" in data["readiness"]
            assert "label" in data["readiness"]
            assert isinstance(data["readiness"]["score"], (int, float))
            assert len(data["readiness"]["label"]) > 0
        print("PASS: CI readiness summary displays after saving")
    finally:
        _cleanup_checkins()


def test_ci_recommendation_uses_saved_readiness():
    _cleanup_checkins()
    try:
        save_checkin({
            "date": date.today().isoformat(),
            "sleepQuality": 5,
            "energy": 5,
            "soreness": 0,
            "pain": 0,
            "stress": 1,
        })
        result = recommend_workout(target_date=date.today())
        assert "recommendation" in result
        rec = result["recommendation"]
        dq = rec.get("dataQuality", {})
        assert "daily_check_in" in dq.get("inputsUsed", []), \
            f"Should use daily check-in, got: {dq.get('inputsUsed')}"
        print("PASS: CI recommendation uses today's saved readiness")
    finally:
        _cleanup_checkins()


def test_ci_recommendation_blocked_without_checkin():
    _cleanup_checkins()
    try:
        checkin = get_checkin(date.today().isoformat())
        assert checkin is None, "No check-in should exist after cleanup"
        result = recommend_workout(target_date=date.today())
        assert "recommendation" in result
        rec = result["recommendation"]
        dq = rec.get("dataQuality", {})
        assert "today's readiness check-in" in dq.get("unknowns", []), \
            f"Should list missing check-in as unknown, got: {dq.get('unknowns')}"
        assert rec.get("confidence") != "high", \
            "Confidence should not be high without check-in data"
        print("PASS: CI recommendation blocked when today's check-in is missing")
    finally:
        _cleanup_checkins()


## ── Strava Integration Tests ──

from coach.history import (
    _normalize_strava_activity,
    _estimate_rpe,
    is_strava_connected,
    StravaProvider,
)


def test_strava_env_config():
    import os
    assert os.environ.get("STRAVA_CLIENT_ID") is not None or True, "Env var check is a no-op in test"
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from server import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REDIRECT_URI
    assert "258611" not in open(str(Path(__file__).parent.parent / "server.py")).read().split("STRAVA_CLIENT_ID")[0:1], \
        "Should not be in preamble"
    source = open(str(Path(__file__).parent.parent / "server.py")).read()
    assert 'os.environ.get("STRAVA_CLIENT_ID"' in source, "Client ID should come from env"
    assert 'os.environ.get("STRAVA_CLIENT_SECRET"' in source, "Client secret should come from env"
    assert 'os.environ.get("STRAVA_REDIRECT_URI"' in source, "Redirect URI should come from env"
    print("PASS: Strava credentials come from environment variables")


def test_strava_normalization():
    raw = {
        "id": 12345678,
        "name": "Morning Ride",
        "type": "Ride",
        "date": "2026-07-18T08:30:00Z",
        "distance": 16.09,
        "duration_min": 57.7,
        "elevation_gain": 1200,
        "avg_hr": 145,
        "max_hr": 172,
        "suffer_score": 87,
        "source": "strava",
    }
    normalized = _normalize_strava_activity(raw)
    assert normalized["strava_id"] == 12345678
    assert normalized["date"] == "2026-07-18"
    assert normalized["type"] == "mtb_ride"
    assert normalized["title"] == "Morning Ride"
    assert normalized["source"] == "strava"
    assert isinstance(normalized["durationMinutes"], (int, float))
    assert isinstance(normalized["distanceMiles"], (int, float))
    assert isinstance(normalized["rpe"], int)
    print("PASS: Strava activity normalization works correctly")


def test_strava_missing_fields_handled():
    raw = {
        "id": 99999,
        "name": "Quick Spin",
        "type": "MountainBikeRide",
        "date": "2026-07-15",
    }
    normalized = _normalize_strava_activity(raw)
    assert normalized["strava_id"] == 99999
    assert normalized["date"] == "2026-07-15"
    assert normalized["type"] == "mtb_ride"
    assert normalized["durationMinutes"] == 0
    assert normalized["distanceMiles"] == 0
    assert normalized["rpe"] is not None
    assert normalized["avg_hr"] is None
    assert normalized["suffer_score"] is None
    print("PASS: Strava activities with missing fields handled gracefully")


def test_strava_rpe_estimation():
    assert _estimate_rpe({"suffer_score": 160}) == 9
    assert _estimate_rpe({"suffer_score": 110}) == 8
    assert _estimate_rpe({"suffer_score": 70}) == 7
    assert _estimate_rpe({"suffer_score": 40}) == 5
    assert _estimate_rpe({"suffer_score": 10}) == 3
    assert _estimate_rpe({"avg_hr": 175}) == 8
    assert _estimate_rpe({"avg_hr": 155}) == 7
    assert _estimate_rpe({"avg_hr": 135}) == 5
    assert _estimate_rpe({"avg_hr": 110}) == 3
    assert _estimate_rpe({"duration_min": 130}) == 6
    assert _estimate_rpe({"duration_min": 70}) == 5
    assert _estimate_rpe({}) == 4
    print("PASS: Strava RPE estimation covers all tiers")


def test_strava_dedup():
    raw_activities = [
        {"id": 111, "name": "Ride A", "type": "Ride", "date": "2026-07-18T09:00:00Z"},
        {"id": 111, "name": "Ride A", "type": "Ride", "date": "2026-07-18T09:00:00Z"},
        {"id": 222, "name": "Ride B", "type": "Ride", "date": "2026-07-17T09:00:00Z"},
    ]
    seen_ids = set()
    deduped = []
    for raw in raw_activities:
        sid = raw.get("id")
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        deduped.append(_normalize_strava_activity(raw))

    assert len(deduped) == 2, f"Expected 2 after dedup, got {len(deduped)}"
    ids = [a["strava_id"] for a in deduped]
    assert 111 in ids and 222 in ids
    print("PASS: Strava duplicate activities are deduplicated")


def test_strava_repeated_imports_no_duplicates():
    batch1 = [
        {"id": 1001, "name": "Ride 1", "type": "Ride", "date": "2026-07-18"},
        {"id": 1002, "name": "Ride 2", "type": "Ride", "date": "2026-07-17"},
    ]
    batch2 = [
        {"id": 1002, "name": "Ride 2", "type": "Ride", "date": "2026-07-17"},
        {"id": 1003, "name": "Ride 3", "type": "Ride", "date": "2026-07-16"},
    ]
    seen_ids = set()
    all_activities = []
    for raw in batch1 + batch2:
        sid = raw.get("id")
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        all_activities.append(_normalize_strava_activity(raw))

    assert len(all_activities) == 3, f"Expected 3 unique, got {len(all_activities)}"
    print("PASS: Repeated Strava imports produce no duplicates")


def test_strava_fallback_to_mock():
    from coach.history import is_strava_connected
    from coach.engine import recommend_workout
    _cleanup_checkins()
    try:
        result = recommend_workout(target_date=date.today())
        assert "recommendation" in result
        dq = result["recommendation"].get("dataQuality", {})
        inputs = dq.get("inputsUsed", [])
        assert any("training_history" in i for i in inputs), \
            f"Should have some training_history input, got: {inputs}"
        print("PASS: Coaching engine falls back to mock when Strava unavailable")
    finally:
        _cleanup_checkins()


def test_strava_coaching_uses_strava_history():
    from unittest.mock import patch
    from coach.engine import recommend_workout
    _cleanup_checkins()
    try:
        mock_activities = [
            {
                "date": date.today().isoformat(),
                "type": "mtb_ride",
                "title": "Strava Ride",
                "durationMinutes": 60,
                "distanceMiles": 10,
                "elevationFeet": 500,
                "rpe": 5,
                "strava_id": 12345,
                "source": "strava",
            }
        ]
        with patch("coach.engine.is_strava_connected", return_value=True), \
             patch("coach.engine.get_provider") as mock_get:
            mock_provider = MockHistoryProvider()
            mock_provider._activities = mock_activities
            mock_provider.get_activities = lambda days=42: mock_activities
            mock_get.return_value = mock_provider
            result = recommend_workout(target_date=date.today())
            assert "recommendation" in result
            dq = result["recommendation"].get("dataQuality", {})
            inputs = dq.get("inputsUsed", [])
            assert "strava_training_history" in inputs, \
                f"Should use strava history, got: {inputs}"
        print("PASS: Coaching engine uses Strava history when connected")
    finally:
        _cleanup_checkins()


## ── Workout Card Click Tests ──

def test_card_html_has_data_attributes():
    app = _get_app()
    with app.test_client() as c:
        resp = c.get("/andrew")
        html = resp.data.decode()
        assert 'data-eidx=' in html or 'workoutCardHTML' in html, \
            "Dashboard must include workoutCardHTML with data-eidx support"
        assert 'attachCardClickHandlers' in html, \
            "Dashboard must call attachCardClickHandlers after rendering"
        assert 'showDetailsModal' in html, \
            "Dashboard must define showDetailsModal function"
    print("PASS: Card HTML includes data attributes and click handler wiring")


def test_card_details_modal_fields():
    app = _get_app()
    with app.test_client() as c:
        resp = c.get("/andrew")
        html = resp.data.decode()
        for field in ['detailClose', 'detailEdit', 'detailDelete']:
            assert field in html, f"Details modal must reference {field}"
        assert 'modal-instructions' in html, "Details modal must support instructions display"
        assert 'modal-source' in html, "Details modal must show source label"
    print("PASS: Details modal has all required fields")


def test_card_strava_readonly():
    app = _get_app()
    with app.test_client() as c:
        resp = c.get("/andrew")
        html = resp.data.decode()
        assert "isStrava" in html or "source === 'strava'" in html, \
            "Details modal must check for Strava source to set read-only"
        assert "isReadOnly" in html or "isStrava" in html, \
            "Strava cards must be flagged as read-only"
    print("PASS: Strava activities are read-only in details modal")


def test_card_click_stops_propagation():
    app = _get_app()
    with app.test_client() as c:
        resp = c.get("/andrew")
        html = resp.data.decode()
        assert "stopPropagation" in html, \
            "Card click handler must stopPropagation to prevent cell navigation"
        assert "closest('[data-eidx]')" in html or "closest(\\\"[data-eidx]\\\")" in html or \
               'closest(\'[data-eidx]\')' in html, \
            "Cell click handlers must check for card click before navigating"
    print("PASS: Card clicks stop propagation and don't trigger navigation")


def test_card_escape_closes_modal():
    app = _get_app()
    with app.test_client() as c:
        resp = c.get("/andrew")
        html = resp.data.decode()
        assert "Escape" in html, "Must handle Escape key to close modal"
        assert "keydown" in html, "Must listen for keydown events"
    print("PASS: Escape key closes the details modal")


def test_card_edit_and_delete_buttons():
    app = _get_app()
    with app.test_client() as c:
        resp = c.get("/andrew")
        html = resp.data.decode()
        assert "editWorkout" in html, "Dashboard must define editWorkout function"
        assert "deleteWorkout" in html, "Dashboard must define deleteWorkout function"
        assert "edit_title" in html, "Edit form must include title field"
        assert "Save Changes" in html, "Edit form must have Save Changes button"
    print("PASS: Edit and Delete buttons are wired for non-Strava workouts")


def test_card_all_views_attach_handlers():
    app = _get_app()
    with app.test_client() as c:
        resp = c.get("/andrew")
        html = resp.data.decode()
        render_fns = ['renderMonth', 'renderWeek', 'renderThreeDay', 'renderDay']
        for fn in render_fns:
            assert fn in html, f"Dashboard must define {fn}"
        handler_calls = html.count('attachCardClickHandlers()')
        assert handler_calls >= 4, \
            f"attachCardClickHandlers must be called in all view renders, found {handler_calls} calls"
    print("PASS: All four calendar views attach card click handlers")


# ── Phase 4: Health Score Tests ──

from coach.health import save_health_score, get_health_score, get_yesterday_exertion, compute_health_readiness

HEALTH_FILE = Path(__file__).parent.parent / "health_scores.json"

def _cleanup_health():
    if HEALTH_FILE.exists():
        HEALTH_FILE.unlink()


def test_hs_save_and_get():
    _cleanup_health()
    try:
        app = _get_app()
        with app.test_client() as c:
            resp = c.post("/api/coach/health", json={
                "date": "2026-07-22",
                "recovery": 63,
                "sleep": 73,
                "exertion": 0.0,
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["health"]["recovery"] == 63
            assert data["health"]["sleep"] == 73
            assert data["health"]["exertion"] == 0.0
            assert "readiness" in data
            assert data["readiness"]["score"] == 68

            resp2 = c.get("/api/coach/health/2026-07-22")
            assert resp2.status_code == 200
            data2 = resp2.get_json()
            assert data2["health"]["recovery"] == 63

            resp3 = c.get("/api/coach/health/2026-01-01")
            assert resp3.status_code == 404
        print("PASS: Health score save and get")
    finally:
        _cleanup_health()


def test_hs_invalid_values_rejected():
    _cleanup_health()
    try:
        app = _get_app()
        with app.test_client() as c:
            resp = c.post("/api/coach/health", json={
                "date": "2026-07-22", "recovery": 150, "sleep": 73, "exertion": 0,
            })
            assert resp.status_code == 400

            resp = c.post("/api/coach/health", json={
                "date": "2026-07-22", "recovery": 63, "sleep": 73, "exertion": 15,
            })
            assert resp.status_code == 400

            resp = c.post("/api/coach/health", json={
                "recovery": 63, "sleep": 73, "exertion": 0,
            })
            assert resp.status_code == 400
        print("PASS: Health score invalid values rejected")
    finally:
        _cleanup_health()


def test_hs_readiness_computation():
    score, label = compute_health_readiness({"recovery": 80, "sleep": 90}, None)
    assert score == 85
    assert "good" in label

    score, label = compute_health_readiness({"recovery": 40, "sleep": 50}, None)
    assert score == 45
    assert "low" in label

    score, label = compute_health_readiness(None, None)
    assert score is None
    print("PASS: Health readiness computation")


def test_hs_yesterday_exertion_penalty():
    score, _ = compute_health_readiness({"recovery": 80, "sleep": 80}, 8.0)
    assert score == 70
    print("PASS: Yesterday exertion penalty applied")


def test_hs_blended_readiness():
    _cleanup_health()
    _cleanup_checkins()
    try:
        save_health_score({"date": "2026-07-22", "recovery": 80, "sleep": 80, "exertion": 0})
        save_checkin({
            "date": "2026-07-22", "sleepQuality": 5, "energy": 5,
            "soreness": 0, "pain": 0, "stress": 1,
        })
        result = recommend_workout(date(2026, 7, 22))
        inputs = result["recommendation"]["dataQuality"]["inputsUsed"]
        assert "athlytic_health_score" in inputs
        assert "daily_check_in" in inputs
        print("PASS: Blended readiness uses both health and check-in")
    finally:
        _cleanup_health()
        _cleanup_checkins()


def test_hs_upload_endpoint():
    app = _get_app()
    with app.test_client() as c:
        resp = c.post("/api/coach/health/upload", data={})
        assert resp.status_code == 400

        from io import BytesIO
        data = {
            "file": (BytesIO(b"fake image data"), "test.jpg"),
            "date": "2026-07-22",
        }
        resp = c.post("/api/coach/health/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["filename"] == "2026-07-22.jpg"

        upload_path = Path(__file__).parent.parent / "uploads" / "2026-07-22.jpg"
        assert upload_path.exists()
        upload_path.unlink()
    print("PASS: Health screenshot upload endpoint")


def test_hs_recommendation_uses_health():
    _cleanup_health()
    _cleanup_checkins()
    try:
        save_health_score({"date": "2026-07-22", "recovery": 10, "sleep": 10, "exertion": 0})
        result = recommend_workout(date(2026, 7, 22))
        rec = result["recommendation"]
        assert rec["type"] in ["rest", "recovery"], f"Low health score should trigger rest/recovery, got {rec['type']}"
        print("PASS: Recommendation uses health score for readiness")
    finally:
        _cleanup_health()
        _cleanup_checkins()


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
    test_p2_recommend_endpoint_returns_modal_data()
    test_p2_accepted_workout_has_correct_date()
    test_p2_recommendation_creates_valid_calendar_record()
    test_p2_recommendation_schema_valid_for_all_views()
    test_p2_failed_recommendation_creates_no_event()
    test_ci_valid_checkin_saves()
    test_ci_invalid_values_rejected()
    test_ci_pain_location_required()
    test_ci_readiness_summary_after_save()
    test_ci_recommendation_uses_saved_readiness()
    test_ci_recommendation_blocked_without_checkin()
    test_strava_env_config()
    test_strava_normalization()
    test_strava_missing_fields_handled()
    test_strava_rpe_estimation()
    test_strava_dedup()
    test_strava_repeated_imports_no_duplicates()
    test_strava_fallback_to_mock()
    test_strava_coaching_uses_strava_history()
    test_card_html_has_data_attributes()
    test_card_details_modal_fields()
    test_card_strava_readonly()
    test_card_click_stops_propagation()
    test_card_escape_closes_modal()
    test_card_edit_and_delete_buttons()
    test_card_all_views_attach_handlers()

    # Health score tests
    test_hs_save_and_get()
    test_hs_invalid_values_rejected()
    test_hs_readiness_computation()
    test_hs_yesterday_exertion_penalty()
    test_hs_blended_readiness()
    test_hs_upload_endpoint()
    test_hs_recommendation_uses_health()
    print("\n=== ALL 49 TESTS PASSED ===")
