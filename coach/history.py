"""Training history adapter with mock and future provider interfaces."""

from datetime import date, timedelta


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
    """Placeholder for future Strava integration."""
    def get_activities(self, days=42):
        raise NotImplementedError("Strava integration not yet implemented")

    def get_weekly_summary(self, weeks=6):
        raise NotImplementedError("Strava integration not yet implemented")


class AppleHealthProvider(TrainingHistoryProvider):
    """Placeholder for future Apple Health import."""
    def get_activities(self, days=42):
        raise NotImplementedError("Apple Health import not yet implemented")

    def get_weekly_summary(self, weeks=6):
        raise NotImplementedError("Apple Health import not yet implemented")


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
