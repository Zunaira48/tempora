import time
import logging

import httpx
import pytz

import config

logger = logging.getLogger("tempora")

# --- Visual Crossing Timeline API ------------------------------------------
# Switched from Open-Meteo because Open-Meteo's free tier is rate-limited
# *per IP*, and Render's shared free-tier IP pool is split across many other
# people's apps too - not just this one. That meant this app could be fully
# blocked by traffic that had nothing to do with it, with no fix available
# short of paying Open-Meteo directly (~EUR30/mo minimum).
#
# Visual Crossing's free tier (visualcrossing.com) is tied to an API key
# instead: 1,000 free "records" per day, no credit card required, and one
# Timeline call returns current conditions + hourly (48h) + daily forecast
# (up to 15 days) + resolved location together. That lets every function
# below share ONE cached call per location instead of each firing its own
# request, so a full page load costs ~2 API credits (one to resolve the
# city name, one shared for current/forecast/hourly/extended), nowhere near
# the free quota.
#
# Docs: https://www.visualcrossing.com/resources/documentation/weather-api/timeline-weather-api/
TIMELINE_BASE_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
FORECAST_DAYS = 15  # Visual Crossing free tier's max daily forecast range (Open-Meteo gave 16)

_CACHE_TTL_SECONDS = 60 * 10  # 10 minutes is plenty fresh for a weather app
# In-memory, single-process cache (same "no Redis, single Render instance"
# decision already made for rate_limiter.py). Key -> (cached_at, data).
# Entries are kept past their TTL on purpose as a stale-on-error fallback -
# see _fetch_timeline() below.
_cache: dict[str, tuple[float, dict]] = {}

# Visual Crossing uses its own fixed icon-name enum instead of WMO weather
# codes. This maps each icon to the closest WMO code so the existing
# describe_condition() lookup (services/weather_codes.py) - and everything
# downstream of it - keeps working completely unchanged.
_ICON_TO_WMO_CODE = {
    "clear-day": 0,
    "clear-night": 0,
    "partly-cloudy-day": 2,
    "partly-cloudy-night": 2,
    "cloudy": 3,
    "wind": 2,
    "fog": 45,
    "rain": 61,
    "showers-day": 80,
    "showers-night": 80,
    "snow": 71,
    "snow-showers-day": 85,
    "snow-showers-night": 85,
    "thunder-rain": 95,
    "thunder-showers-day": 95,
    "thunder-showers-night": 95,
}


# For a bare city name with no state/country hint (e.g. "Lahore"), Visual
# Crossing's resolvedAddress often comes back as just the city itself, with
# no country. Rather than leave that blank in the UI, fall back to deriving
# the country from the timezone it does give us (a standard, offline IANA
# timezone->country lookup - no extra network call, no new failure mode).
_TZ_TO_COUNTRY = {tz: pytz.country_names[cc] for cc, tzs in pytz.country_timezones.items() for tz in tzs}


class CityNotFoundError(Exception):
    pass


class WeatherProviderError(Exception):
    """Raised when the weather provider itself is unavailable or rate
    limiting us - distinct from CityNotFoundError, which means the request
    succeeded but the city doesn't exist. This lets endpoints return a clean
    503 ('try again shortly') instead of a generic, unhelpful 500."""


def _wmo_code_from_icon(icon: str) -> int:
    return _ICON_TO_WMO_CODE.get(icon, 3)  # 3 = "Overcast", closest generic fallback


def _time_part(value: str | None) -> str:
    """Normalizes a Visual Crossing time value to 'HH:MM:SS', whether it
    arrives as a bare time or a full ISO datetime."""
    if not value:
        return "00:00:00"
    return value.split("T")[-1][:8]


def _round_int(value, default=0) -> int:
    if value is None:
        return default
    try:
        return int(round(value))
    except (TypeError, ValueError):
        return default


def _cache_key(location: str) -> str:
    return location.strip().lower()


async def _fetch_timeline(location: str) -> dict:
    """Single shared fetch: one Visual Crossing Timeline call returns
    resolved location + current conditions + hourly + up to 15-day daily
    forecast together. Every public function below calls this with either
    a city name (resolve_city) or a 'lat,lon' string (everything else), so
    calls for the same location within the cache TTL are free."""
    if not config.VISUALCROSSING_API_KEY:
        raise WeatherProviderError("Weather provider is not configured (missing API key)")

    key = _cache_key(location)
    now = time.monotonic()

    cached = _cache.get(key)
    if cached is not None and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    url = f"{TIMELINE_BASE_URL}/{location}"
    params = {
        "key": config.VISUALCROSSING_API_KEY,
        "unitGroup": "metric",
        "include": "days,hours,current",
        "elements": "+aqius",  # add US AQI on top of the default element set
        "contentType": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if cached is not None:
            logger.warning("Serving stale cached data for %s after provider error (%s)", location, status)
            return cached[1]
        if status == 400:
            # Visual Crossing returns 400 for a location string it can't resolve.
            raise CityNotFoundError(f"No location found for '{location}'") from exc
        if status == 429:
            raise WeatherProviderError("Weather provider rate limit reached") from exc
        if status >= 500:
            raise WeatherProviderError("Weather provider is currently unavailable") from exc
        raise WeatherProviderError(f"Weather provider error ({status})") from exc
    except httpx.RequestError as exc:
        if cached is not None:
            logger.warning("Serving stale cached data for %s after provider error: could not reach provider", location)
            return cached[1]
        raise WeatherProviderError("Could not reach weather provider") from exc

    _cache[key] = (now, data)
    return data


async def resolve_city(city_name: str) -> dict:
    data = await _fetch_timeline(city_name)

    resolved = data.get("resolvedAddress") or data.get("address") or city_name
    parts = [p.strip() for p in resolved.split(",") if p.strip()]
    name = parts[0] if parts else city_name
    country = parts[-1] if len(parts) > 1 else ""
    timezone = data.get("timezone", "UTC")

    if not country:
        # resolvedAddress didn't include a country (common for bare city
        # names) - derive it from the timezone instead of leaving it blank.
        country = _TZ_TO_COUNTRY.get(timezone, "")

    return {
        "name": name,
        "country": country,
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "timezone": timezone,
    }


async def fetch_current_weather(latitude: float, longitude: float, timezone: str) -> dict:
    data = await _fetch_timeline(f"{latitude},{longitude}")
    current = data.get("currentConditions", {}) or {}
    today = (data.get("days") or [{}])[0]
    date_part = today.get("datetime", "")

    current_time = _time_part(current.get("datetime"))
    sunrise_time = _time_part(today.get("sunrise"))
    sunset_time = _time_part(today.get("sunset"))
    is_day = sunrise_time <= current_time <= sunset_time

    return {
        "current": {
            "time": f"{date_part}T{current_time[:5]}" if date_part else current_time,
            "temperature_2m": current.get("temp"),
            "apparent_temperature": current.get("feelslike", current.get("temp")),
            "relative_humidity_2m": _round_int(current.get("humidity")),
            "wind_speed_10m": current.get("windspeed"),
            "weather_code": _wmo_code_from_icon(current.get("icon", "")),
            "is_day": is_day,
        },
        "daily": {
            "sunrise": [f"{date_part}T{sunrise_time[:5]}" if date_part else sunrise_time],
            "sunset": [f"{date_part}T{sunset_time[:5]}" if date_part else sunset_time],
            "uv_index_max": [today.get("uvindex")],
        },
    }


async def fetch_forecast(latitude: float, longitude: float, timezone: str) -> dict:
    """5-day daily forecast for the homepage view."""
    data = await _fetch_timeline(f"{latitude},{longitude}")
    days = (data.get("days") or [])[:5]

    return {
        "daily": {
            "time": [d.get("datetime") for d in days],
            "temperature_2m_max": [d.get("tempmax") for d in days],
            "temperature_2m_min": [d.get("tempmin") for d in days],
            "weather_code": [_wmo_code_from_icon(d.get("icon", "")) for d in days],
            "precipitation_probability_max": [_round_int(d.get("precipprob")) for d in days],
        },
    }


async def fetch_hourly_forecast(latitude: float, longitude: float, timezone: str) -> dict:
    """48-hour hourly forecast (first two daily entries' worth of hours)."""
    data = await _fetch_timeline(f"{latitude},{longitude}")
    days = (data.get("days") or [])[:2]

    times, temps, codes, precip, wind, feels = [], [], [], [], [], []
    for day in days:
        date_part = day.get("datetime", "")
        for hour in day.get("hours", []):
            hour_time = _time_part(hour.get("datetime"))
            times.append(f"{date_part}T{hour_time[:5]}" if date_part else hour_time)
            temps.append(hour.get("temp"))
            codes.append(_wmo_code_from_icon(hour.get("icon", "")))
            precip.append(_round_int(hour.get("precipprob")))
            wind.append(hour.get("windspeed"))
            feels.append(hour.get("feelslike", hour.get("temp")))

    return {
        "hourly": {
            "time": times,
            "temperature_2m": temps,
            "weather_code": codes,
            "precipitation_probability": precip,
            "wind_speed_10m": wind,
            "apparent_temperature": feels,
        },
    }


async def fetch_air_quality(latitude: float, longitude: float) -> dict:
    """US AQI, requested via elements=+aqius (see
    https://www.visualcrossing.com/resources/documentation/weather-api/air-quality-elements-in-the-weather-api/).
    Air quality coverage is more limited than core weather data, so this
    returns None when absent - callers already treat AQI fetch
    failures/missing values as non-fatal and just show air quality as
    unavailable, rather than erroring the whole page."""
    data = await _fetch_timeline(f"{latitude},{longitude}")
    current = data.get("currentConditions", {}) or {}
    return {"current": {"us_aqi": current.get("aqius")}}


async def fetch_extended_daily_forecast(latitude: float, longitude: float, timezone: str, forecast_days: int = 16) -> dict:
    """Longer daily forecast window for multi-day trip planning. Visual
    Crossing's free tier supports up to 15 forecast days (one less than
    Open-Meteo's 16); requests for more are silently clamped."""
    data = await _fetch_timeline(f"{latitude},{longitude}")
    days = (data.get("days") or [])[:min(forecast_days, FORECAST_DAYS)]

    return {
        "daily": {
            "time": [d.get("datetime") for d in days],
            "temperature_2m_max": [d.get("tempmax") for d in days],
            "temperature_2m_min": [d.get("tempmin") for d in days],
            "weather_code": [_wmo_code_from_icon(d.get("icon", "")) for d in days],
            "precipitation_probability_max": [_round_int(d.get("precipprob")) for d in days],
            "wind_speed_10m_max": [d.get("windspeed") for d in days],
        },
    }