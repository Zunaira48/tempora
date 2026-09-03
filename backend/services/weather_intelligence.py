"""
Deterministic weather-suitability scoring.

This module contains no AI calls and no network calls. It takes weather
values Tempora has already fetched from Open-Meteo and turns them into
transparent, explainable 0-100 scores. AI (added in later phases) is only
ever allowed to *explain* these numbers in natural language — never to
invent or override them.
"""

from dataclasses import dataclass


def _linear_score(value: float, ideal_min: float, ideal_max: float, zero_at: float) -> int:
    """
    Returns 100 within [ideal_min, ideal_max], falling off linearly to 0
    at `zero_at` (which may be above ideal_max or below ideal_min depending
    on the factor). Never returns below 0 or above 100.
    """
    if ideal_min <= value <= ideal_max:
        return 100

    if value > ideal_max:
        span = zero_at - ideal_max
        if span <= 0:
            return 0
        fraction = (value - ideal_max) / span
    else:
        span = ideal_min - zero_at
        if span <= 0:
            return 0
        fraction = (ideal_min - value) / span

    score = 100 * (1 - fraction)
    return max(0, min(100, round(score)))


def temperature_score(feels_like_c: float) -> int:
    return _linear_score(feels_like_c, ideal_min=18, ideal_max=25, zero_at=40)


def precipitation_score(precipitation_probability_percent: float) -> int:
    if precipitation_probability_percent <= 0:
        return 100
    fraction = min(precipitation_probability_percent / 80, 1)
    return max(0, round(100 * (1 - fraction)))


def wind_score(wind_speed_kmh: float) -> int:
    return _linear_score(wind_speed_kmh, ideal_min=0, ideal_max=15, zero_at=50)


def uv_score(uv_index: float) -> int:
    return _linear_score(uv_index, ideal_min=0, ideal_max=5, zero_at=11)


def aqi_score(aqi: float) -> int:
    return _linear_score(aqi, ideal_min=0, ideal_max=50, zero_at=200)


@dataclass
class OutdoorScore:
    overall: int
    components: dict[str, int]


def score_current_conditions(
    feels_like_c: float,
    wind_speed_kmh: float,
    uv_index: float | None,
    aqi: int | None,
) -> OutdoorScore:
    """
    Full 5-factor score for 'right now', using current-conditions data.
    Precipitation isn't included here since current weather doesn't carry
    a precipitation probability - only the forecast does.
    """
    components = {
        "temperature": temperature_score(feels_like_c),
        "wind": wind_score(wind_speed_kmh),
    }
    if uv_index is not None:
        components["uv"] = uv_score(uv_index)
    if aqi is not None:
        components["aqi"] = aqi_score(aqi)

    overall = round(sum(components.values()) / len(components))
    return OutdoorScore(overall=overall, components=components)


def score_hourly_slot(
    feels_like_c: float,
    precipitation_probability_percent: float,
    wind_speed_kmh: float,
) -> OutdoorScore:
    """
    3-factor score for a single hourly forecast slot. UV/AQI are
    deliberately excluded - Open-Meteo doesn't provide them hourly, and we
    never fabricate values we don't have.
    """
    components = {
        "temperature": temperature_score(feels_like_c),
        "precipitation": precipitation_score(precipitation_probability_percent),
        "wind": wind_score(wind_speed_kmh),
    }
    overall = round(sum(components.values()) / len(components))
    return OutdoorScore(overall=overall, components=components)


def find_best_outdoor_window(hourly: dict, window_hours: int = 2) -> dict | None:
    """
    Scans the raw Open-Meteo hourly dict (as returned by fetch_hourly_forecast)
    and finds the contiguous block of `window_hours` hours with the highest
    average outdoor score. Returns None if there isn't enough hourly data.
    """
    times = hourly.get("time", [])
    temps = hourly.get("apparent_temperature", [])
    precip = hourly.get("precipitation_probability", [])
    wind = hourly.get("wind_speed_10m", [])

    hour_count = len(times)
    if hour_count < window_hours:
        return None

    hourly_scores = [
        score_hourly_slot(temps[i], precip[i], wind[i]).overall
        for i in range(hour_count)
    ]

    best_start_index = 0
    best_average = -1

    for start in range(hour_count - window_hours + 1):
        window_scores = hourly_scores[start:start + window_hours]
        average = sum(window_scores) / window_hours
        if average > best_average:
            best_average = average
            best_start_index = start

    return {
        "start_time": times[best_start_index],
        "end_time": times[best_start_index + window_hours - 1],
        "average_score": round(best_average),
    }


def detect_condition_flags(
    feels_like_c: float,
    uv_index: float | None,
    aqi: int | None,
    wind_speed_kmh: float,
) -> list[dict]:
    """
    Deterministic threshold checks. Returns a list of flags, each with a
    machine-readable code and a plain-language reason. AI (Phase 10's
    Alert Explainer) explains *why these matter*; it never decides
    *whether* they apply - that's this function's job, using fixed
    thresholds only.
    """
    flags = []

    if feels_like_c >= 40:
        flags.append({"code": "extreme_heat", "reason": f"Feels-like temperature is {feels_like_c:.0f}°C"})

    if uv_index is not None and uv_index >= 8:
        flags.append({"code": "high_uv", "reason": f"UV index is {uv_index:.1f}"})

    if aqi is not None and aqi > 150:
        flags.append({"code": "poor_air_quality", "reason": f"Air Quality Index is {aqi}"})

    if wind_speed_kmh >= 40:
        flags.append({"code": "strong_wind", "reason": f"Wind speed is {wind_speed_kmh:.0f} km/h"})

    return flags


ACTIVITY_PROFILES = {
    # allowed_hours is the realistic local-time window this activity happens in,
    # so the scorer never suggests a technically-comfortable time nobody would
    # actually do this activity at (e.g. a picnic at 3 AM).
    "running": {"label": "Running", "ideal_min": 10, "ideal_max": 20, "zero_low": -5, "zero_high": 35, "allowed_hours": (5, 20)},
    "walking": {"label": "Walking", "ideal_min": 15, "ideal_max": 25, "zero_low": -5, "zero_high": 38, "allowed_hours": (6, 21)},
    "cycling": {"label": "Cycling", "ideal_min": 12, "ideal_max": 24, "zero_low": -5, "zero_high": 36, "allowed_hours": (6, 19)},
    "beach": {"label": "Beach", "ideal_min": 26, "ideal_max": 34, "zero_low": 10, "zero_high": 42, "allowed_hours": (8, 18)},
    "photography": {"label": "Photography", "ideal_min": 15, "ideal_max": 28, "zero_low": -5, "zero_high": 40, "allowed_hours": (5, 19)},
    "picnic": {"label": "Picnic", "ideal_min": 18, "ideal_max": 27, "zero_low": 0, "zero_high": 38, "allowed_hours": (9, 17)},
    "hiking": {"label": "Hiking", "ideal_min": 10, "ideal_max": 22, "zero_low": -5, "zero_high": 33, "allowed_hours": (6, 16)},
    "travel": {"label": "Travel", "ideal_min": 10, "ideal_max": 30, "zero_low": -10, "zero_high": 42, "allowed_hours": (5, 21)},
    "university": {"label": "University", "ideal_min": 10, "ideal_max": 30, "zero_low": -10, "zero_high": 42, "allowed_hours": (7, 17)},
    "outdoor_event": {"label": "Outdoor Event", "ideal_min": 18, "ideal_max": 27, "zero_low": 0, "zero_high": 38, "allowed_hours": (9, 20)},
}


def _linear_score_range(value: float, ideal_min: float, ideal_max: float, zero_low: float, zero_high: float) -> int:
    """Like _linear_score, but with independent falloff points on each side
    of the ideal range - needed because e.g. Beach's 'too cold' cutoff and
    'too hot' cutoff aren't symmetric around its ideal band."""
    if ideal_min <= value <= ideal_max:
        return 100

    if value > ideal_max:
        span = zero_high - ideal_max
        fraction = (value - ideal_max) / span if span > 0 else 1
    else:
        span = ideal_min - zero_low
        fraction = (ideal_min - value) / span if span > 0 else 1

    return max(0, min(100, round(100 * (1 - fraction))))


def score_activity_hourly_slot(
    feels_like_c: float,
    precipitation_probability_percent: float,
    wind_speed_kmh: float,
    activity_key: str,
) -> OutdoorScore:
    profile = ACTIVITY_PROFILES[activity_key]
    components = {
        "temperature": _linear_score_range(
            feels_like_c, profile["ideal_min"], profile["ideal_max"], profile["zero_low"], profile["zero_high"]
        ),
        "precipitation": precipitation_score(precipitation_probability_percent),
        "wind": wind_score(wind_speed_kmh),
    }
    overall = round(sum(components.values()) / len(components))
    return OutdoorScore(overall=overall, components=components)


def _hour_of(iso_time: str) -> int:
    # Open-Meteo hourly "time" strings look like "2026-09-03T06:00" - the
    # hour is always at a fixed position, so a plain slice is reliable and
    # avoids pulling in a full datetime parse for something this simple.
    return int(iso_time[11:13])


def find_best_activity_window(hourly: dict, activity_key: str, window_hours: int = 2) -> dict | None:
    times = hourly.get("time", [])
    temps = hourly.get("apparent_temperature", [])
    precip = hourly.get("precipitation_probability", [])
    wind = hourly.get("wind_speed_10m", [])

    hour_count = len(times)
    if hour_count < window_hours:
        return None

    allowed_start, allowed_end = ACTIVITY_PROFILES[activity_key]["allowed_hours"]

    hourly_scores = [
        score_activity_hourly_slot(temps[i], precip[i], wind[i], activity_key)
        for i in range(hour_count)
    ]

    best_start = None
    best_average = -1
    best_components = None

    for start in range(hour_count - window_hours + 1):
        window_start_hour = _hour_of(times[start])
        window_end_hour = _hour_of(times[start + window_hours - 1])

        # Only consider windows that fall entirely within this activity's
        # realistic time-of-day range - a high weather score at 3 AM is
        # irrelevant if nobody would do this activity at 3 AM.
        if not (allowed_start <= window_start_hour <= allowed_end and allowed_start <= window_end_hour <= allowed_end):
            continue

        window = hourly_scores[start:start + window_hours]
        average = sum(s.overall for s in window) / window_hours
        if average > best_average:
            best_average = average
            best_start = start
            keys = window[0].components.keys()
            best_components = {k: round(sum(s.components[k] for s in window) / window_hours) for k in keys}

    if best_start is None:
        # No slot in the forecast window falls within realistic hours for
        # this activity (e.g. forecast data doesn't reach tomorrow's daytime
        # yet) - be honest about that rather than returning a nonsense time.
        return None

    return {
        "start_time": times[best_start],
        "end_time": times[best_start + window_hours - 1],
        "average_score": round(best_average),
        "components": best_components,
    }


def build_activity_reasons(components: dict) -> list[str]:
    """Deterministic checklist, generated only from real component scores -
    never claims metrics (like cloud cover or visibility) we don't have."""
    reasons = []

    if components["temperature"] >= 70:
        reasons.append("Comfortable temperature for this activity")
    else:
        reasons.append("Temperature is less than ideal for this activity")

    if components["precipitation"] >= 80:
        reasons.append("Low chance of rain")
    elif components["precipitation"] < 50:
        reasons.append("Notable chance of rain")

    if components["wind"] >= 70:
        reasons.append("Calm winds")
    else:
        reasons.append("Breezy conditions")

    return reasons