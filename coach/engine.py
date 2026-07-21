"""Coaching engine — deterministic workout recommendation."""

from datetime import date, timedelta
from coach.profile import load_profile, get_unknowns
from coach.readiness import get_checkin, compute_readiness_score
from coach.history import get_provider
from coach.trails import search_trails, rank_trails
from coach.schema import validate_workout

PHASES = ["assessment", "base", "build", "specificity", "taper", "recovery", "return_to_training"]

WORKOUT_TEMPLATES = {
    "easy_trail_ride": {
        "type": "mtb_ride",
        "title": "Easy Trail Ride",
        "objective": "Aerobic base building at conversational pace",
        "durationMinutes": 75,
        "targetMiles": 12,
        "intensity": {"method": "rpe", "target": "RPE 3-4, conversational pace"},
        "instructions": [
            "Warm up for 10 minutes on easy terrain",
            "Maintain steady effort at RPE 3-4 for the main set",
            "Focus on smooth pedaling and relaxed upper body",
            "Cool down with 5 minutes easy spinning",
        ],
    },
    "interval_climbs": {
        "type": "mtb_ride",
        "title": "Climbing Intervals",
        "objective": "Build climbing power and threshold capacity",
        "durationMinutes": 90,
        "targetMiles": 15,
        "intensity": {"method": "rpe", "target": "RPE 7-8 during intervals, RPE 3-4 recovery"},
        "instructions": [
            "Warm up for 15 minutes at easy pace",
            "Perform 4x5 minute hill repeats at RPE 7-8",
            "Recover 3 minutes easy spinning between efforts",
            "Cool down 10 minutes easy",
        ],
    },
    "long_endurance_ride": {
        "type": "mtb_ride",
        "title": "Long Endurance Ride",
        "objective": "Build aerobic durability and fatigue resistance",
        "durationMinutes": 150,
        "targetMiles": 25,
        "intensity": {"method": "rpe", "target": "RPE 4-5, steady sustainable effort"},
        "instructions": [
            "Bring adequate nutrition and hydration for 2.5 hours",
            "Start at RPE 3-4 for first 30 minutes",
            "Settle into RPE 4-5 for the main set",
            "Include varied terrain — climbs, descents, technical sections",
            "Finish at RPE 3, spin easy for final 10 minutes",
        ],
    },
    "technical_skills": {
        "type": "mtb_ride",
        "title": "Technical Skills Session",
        "objective": "Improve cornering, body position, and descending confidence",
        "durationMinutes": 60,
        "targetMiles": 8,
        "intensity": {"method": "rpe", "target": "RPE 3-5, focus on technique not fitness"},
        "instructions": [
            "Choose a trail with varied technical features",
            "Repeat 3-4 technical sections, focusing on line choice",
            "Practice cornering: outside foot weighted, look through the turn",
            "Practice drops and rock gardens at comfortable speed",
            "Session RPE should feel moderate — technique degrades when exhausted",
        ],
    },
    "upper_body_strength": {
        "type": "strength",
        "title": "Upper Body + Core Strength",
        "objective": "Build upper body endurance and trunk stability for bike control",
        "durationMinutes": 40,
        "targetMiles": None,
        "intensity": {"method": "rpe", "target": "RPE 5-6, controlled movements"},
        "instructions": [
            "Push-ups: 3 sets of 12-15",
            "Inverted rows or band rows: 3 sets of 12",
            "Dead hang: 3 sets of 20-30 seconds",
            "Plank: 3 sets of 30-45 seconds",
            "Side plank: 2 sets of 20-30 seconds each side",
            "Pallof press or anti-rotation hold: 2 sets of 10 each side",
            "Rest 60-90 seconds between sets",
        ],
    },
    "lower_body_strength": {
        "type": "strength",
        "title": "Lower Body Strength",
        "objective": "Build leg strength and single-leg stability for pedaling and descending",
        "durationMinutes": 45,
        "targetMiles": None,
        "intensity": {"method": "rpe", "target": "RPE 5-7, challenging but controlled"},
        "instructions": [
            "Split squats: 3 sets of 10 each leg",
            "Goblet squat or bodyweight squat: 3 sets of 15",
            "Romanian deadlift (bodyweight or band): 3 sets of 12",
            "Step-ups: 3 sets of 10 each leg",
            "Calf raises: 2 sets of 15",
            "Single-leg glute bridge: 2 sets of 12 each side",
            "Rest 60-90 seconds between sets",
        ],
    },
    "morning_mobility": {
        "type": "mobility",
        "title": "Morning Mobility Routine",
        "objective": "Maintain range of motion and prepare for the day",
        "durationMinutes": 10,
        "targetMiles": None,
        "intensity": {"method": "rpe", "target": "RPE 1-2, gentle movement"},
        "instructions": [
            "Ankle circles: 10 each direction per foot",
            "Hip 90/90 switches: 8 per side",
            "Cat-cow: 10 reps",
            "Thoracic rotation: 8 per side",
            "Shoulder circles and wall slides: 10 reps",
            "Wrist circles and extensions: 10 each direction",
        ],
    },
    "recovery_ride": {
        "type": "recovery",
        "title": "Recovery Spin",
        "objective": "Promote blood flow and recovery without adding training stress",
        "durationMinutes": 30,
        "targetMiles": 5,
        "intensity": {"method": "rpe", "target": "RPE 1-2, truly easy"},
        "instructions": [
            "Flat or very gentle terrain only",
            "Keep effort conversational — if you're breathing hard, slow down",
            "Spin at high cadence, low resistance",
            "This should feel like doing nothing on the bike",
        ],
    },
    "rest_day": {
        "type": "rest",
        "title": "Full Rest Day",
        "objective": "Allow physical and mental recovery",
        "durationMinutes": 0,
        "targetMiles": None,
        "intensity": {"method": "rpe", "target": "None — full rest"},
        "instructions": [
            "No structured exercise",
            "Light walking is fine",
            "Focus on nutrition, hydration, and sleep",
            "Morning mobility routine is still encouraged",
        ],
    },
}


def _get_day_position_in_week(target_date):
    return target_date.weekday()


def _count_recent_hard_days(activities, target_date, lookback=7):
    cutoff = (target_date - timedelta(days=lookback)).isoformat()
    target_str = target_date.isoformat()
    count = 0
    for a in activities:
        if cutoff <= a["date"] < target_str and (a.get("rpe") or 0) >= 7:
            count += 1
    return count


def _was_yesterday_hard(activities, target_date):
    yesterday = (target_date - timedelta(days=1)).isoformat()
    for a in activities:
        if a["date"] == yesterday and (a.get("rpe") or 0) >= 7:
            return True
    return False


def _get_weekly_miles(activities, target_date):
    week_start = target_date - timedelta(days=target_date.weekday())
    ws = week_start.isoformat()
    td = target_date.isoformat()
    total = 0
    for a in activities:
        if ws <= a["date"] <= td and a.get("distanceMiles"):
            total += a["distanceMiles"]
    return total


def recommend_workout(target_date=None, calendar_events=None):
    if target_date is None:
        target_date = date.today()

    if calendar_events is None:
        calendar_events = []

    for event in calendar_events:
        if event.get("date") == target_date.isoformat() and event.get("locked"):
            return {
                "recommendation": event,
                "source": "locked_calendar",
                "message": "This workout is locked and will not be changed.",
            }

    profile = load_profile()
    checkin = get_checkin(target_date.isoformat())
    readiness_score, readiness_label = compute_readiness_score(checkin)

    provider = get_provider("mock")
    activities = provider.get_activities(days=42)

    recent_hard_days = _count_recent_hard_days(activities, target_date)
    yesterday_hard = _was_yesterday_hard(activities, target_date)
    weekly_miles = _get_weekly_miles(activities, target_date)
    day_of_week = _get_day_position_in_week(target_date)

    inputs_used = ["athlete_profile", "day_of_week", "mock_training_history"]
    unknowns = list(get_unknowns())

    if checkin:
        inputs_used.append("daily_check_in")
    else:
        unknowns.append("today's readiness check-in")

    if readiness_score is not None and readiness_score < 30:
        template_key = "rest_day"
        explanation = (
            f"Readiness score is {readiness_score}/100 ({readiness_label}). "
            "Rest is the safest choice today."
        )
        recovery_warning = "Very low readiness — rest recommended. If this persists, consider evaluating sleep and stress."
        confidence = "high"
    elif readiness_score is not None and readiness_score < 50:
        template_key = "recovery_ride" if day_of_week not in [6] else "morning_mobility"
        explanation = (
            f"Readiness score is {readiness_score}/100 ({readiness_label}). "
            "Reducing to recovery-level activity."
        )
        recovery_warning = "Moderate readiness — avoid high intensity today."
        confidence = "medium"
    elif yesterday_hard:
        template_key = _select_non_hard_workout(day_of_week)
        explanation = (
            "Yesterday included high-intensity work (RPE 7+). "
            "Avoiding back-to-back hard days per safety guidelines."
        )
        recovery_warning = None
        confidence = "medium"
    elif recent_hard_days >= 2:
        template_key = _select_non_hard_workout(day_of_week)
        explanation = (
            f"Already {recent_hard_days} high-intensity days in the last 7 days. "
            "Limiting to two per week per athlete guidelines."
        )
        recovery_warning = None
        confidence = "medium"
    else:
        template_key = _select_workout_for_day(day_of_week, weekly_miles)
        explanation = _build_normal_explanation(day_of_week, weekly_miles, readiness_score)
        recovery_warning = None
        confidence = "medium" if checkin else "low"

    template = WORKOUT_TEMPLATES[template_key]

    trail_rec = None
    if template["type"] == "mtb_ride":
        available_trails = search_trails(exclude_closed=True)
        ranked = rank_trails(available_trails, template["type"],
                             target_miles=template.get("targetMiles"),
                             target_tech=3)
        if ranked:
            best = ranked[0]["trail"]
            trail_rec = {
                "name": best["name"],
                "route": best["routeOptions"][0] if best["routeOptions"] else "full loop",
                "status": best["status"],
                "trailforksUrl": best["trailforksUrl"],
                "reason": f"Best match for {template['title']} — "
                          f"{best['totalMileageEstimate']}mi, "
                          f"tech rating {best['technicalRating']}/5",
            }

    backup_key = _get_backup(template_key)
    backup_template = WORKOUT_TEMPLATES[backup_key]

    workout = {
        "date": target_date.isoformat(),
        "type": template["type"],
        "title": template["title"],
        "objective": template["objective"],
        "durationMinutes": template["durationMinutes"],
        "targetMiles": template.get("targetMiles"),
        "intensity": template["intensity"],
        "instructions": template["instructions"],
        "trailRecommendation": trail_rec,
        "explanation": explanation,
        "backup": {
            "title": backup_template["title"],
            "instructions": backup_template["instructions"],
        },
        "recoveryWarning": recovery_warning,
        "confidence": confidence,
        "dataQuality": {
            "inputsUsed": inputs_used,
            "unknowns": unknowns,
        },
        "locked": False,
    }

    errors = validate_workout(workout)
    if errors:
        return {"error": "Schema validation failed", "details": errors, "workout": workout}

    return {"recommendation": workout, "source": "coaching_engine"}


def _select_workout_for_day(day_of_week, weekly_miles):
    schedule = {
        0: "easy_trail_ride",
        1: "upper_body_strength",
        2: "interval_climbs",
        3: "morning_mobility",
        4: "lower_body_strength",
        5: "long_endurance_ride",
        6: "rest_day",
    }
    return schedule.get(day_of_week, "easy_trail_ride")


def _select_non_hard_workout(day_of_week):
    options = {
        0: "easy_trail_ride",
        1: "upper_body_strength",
        2: "easy_trail_ride",
        3: "morning_mobility",
        4: "lower_body_strength",
        5: "easy_trail_ride",
        6: "rest_day",
    }
    return options.get(day_of_week, "recovery_ride")


def _get_backup(primary_key):
    backups = {
        "easy_trail_ride": "recovery_ride",
        "interval_climbs": "easy_trail_ride",
        "long_endurance_ride": "easy_trail_ride",
        "technical_skills": "easy_trail_ride",
        "upper_body_strength": "morning_mobility",
        "lower_body_strength": "morning_mobility",
        "morning_mobility": "rest_day",
        "recovery_ride": "rest_day",
        "rest_day": "morning_mobility",
    }
    return backups.get(primary_key, "rest_day")


def _build_normal_explanation(day_of_week, weekly_miles, readiness_score):
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    parts = [f"Today is {day_names[day_of_week]}."]

    if weekly_miles > 0:
        parts.append(f"Weekly mileage so far: {weekly_miles} miles.")

    if readiness_score:
        parts.append(f"Readiness: {readiness_score}/100.")
    else:
        parts.append("No check-in data — using default schedule.")

    parts.append("Workout selected based on weekly structure and recovery status.")
    return " ".join(parts)
