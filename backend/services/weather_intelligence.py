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