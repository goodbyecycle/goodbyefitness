"""Calendar workout schema validation."""

import json
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "calendar-workout.schema.json"

REQUIRED_FIELDS = [
    "date", "type", "title", "objective", "durationMinutes",
    "intensity", "instructions", "explanation", "backup", "dataQuality",
]

VALID_TYPES = [
    "mtb_ride", "indoor_cardio", "strength", "mobility",
    "recovery", "rest", "assessment",
]

VALID_INTENSITY_METHODS = ["rpe", "heart_rate", "power", "mixed"]
VALID_CONFIDENCE = ["low", "medium", "high"]
VALID_TRAIL_STATUS = ["confirmed_open", "confirmed_closed", "unknown"]


def validate_workout(workout):
    errors = []

    for field in REQUIRED_FIELDS:
        if field not in workout:
            errors.append(f"Missing required field: {field}")

    if errors:
        return errors

    if workout["type"] not in VALID_TYPES:
        errors.append(f"Invalid type: {workout['type']}")

    if not isinstance(workout["durationMinutes"], int) or workout["durationMinutes"] < 0:
        errors.append("durationMinutes must be a non-negative integer")

    intensity = workout.get("intensity", {})
    if not isinstance(intensity, dict):
        errors.append("intensity must be an object")
    else:
        if "method" not in intensity or "target" not in intensity:
            errors.append("intensity requires method and target")
        elif intensity["method"] not in VALID_INTENSITY_METHODS:
            errors.append(f"Invalid intensity method: {intensity['method']}")

    if not isinstance(workout.get("instructions", []), list):
        errors.append("instructions must be an array")

    if not isinstance(workout.get("explanation", ""), str) or not workout["explanation"]:
        errors.append("explanation must be a non-empty string")

    backup = workout.get("backup", {})
    if not isinstance(backup, dict):
        errors.append("backup must be an object")
    else:
        if "title" not in backup or "instructions" not in backup:
            errors.append("backup requires title and instructions")

    dq = workout.get("dataQuality", {})
    if not isinstance(dq, dict):
        errors.append("dataQuality must be an object")
    else:
        if "inputsUsed" not in dq or "unknowns" not in dq:
            errors.append("dataQuality requires inputsUsed and unknowns")
        elif not isinstance(dq["inputsUsed"], list) or not isinstance(dq["unknowns"], list):
            errors.append("dataQuality.inputsUsed and unknowns must be arrays")

    if "confidence" in workout and workout["confidence"] not in VALID_CONFIDENCE:
        errors.append(f"Invalid confidence: {workout['confidence']}")

    trail = workout.get("trailRecommendation")
    if trail is not None:
        if not isinstance(trail, dict):
            errors.append("trailRecommendation must be an object or null")
        elif "status" in trail and trail["status"] not in VALID_TRAIL_STATUS:
            errors.append(f"Invalid trail status: {trail['status']}")

    if "targetMiles" in workout and workout["targetMiles"] is not None:
        if not isinstance(workout["targetMiles"], (int, float)) or workout["targetMiles"] < 0:
            errors.append("targetMiles must be a non-negative number or null")

    return errors
