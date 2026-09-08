import time
import logging

import httpx

logger = logging.getLogger("tempora")

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Open-Meteo's free tier is limited *per IP*, not per app - and on Render's
# shared free-tier IP pool, that quota is split across everyone else's free
# apps too, not just this one. Caching cuts how often we call Open-Meteo at
# all, which is the only lever we actually control. City coordinates never
# change, so geocoding is safe to cache for a long time; weather/AQI numbers
# are cached briefly since they do change, but not minute to minute.
_CACHE_TTL_SECONDS = {
    GEOCODING_URL: 60 * 60 * 24,  # 24h - city coordinates are effectively static
    FORECAST_URL: 60 * 10,        # 10m - fresh enough for a weather app
    AIR_QUALITY_URL: 60 * 10,
}
_DEFAULT_TTL_SECONDS = 60 * 10

# In-memory, single-process cache (consistent with rate_limiter.py's existing
# "no Redis, single Render instance" decision). Key -> (cached_at, data).
# Entries are kept around past their TTL on purpose, as a stale fallback for
# when Open-Meteo is actively rate-limiting or down - see _get() below.
_cache: dict[str, tuple[float, dict]] = {}


class CityNotFoundError(Exception):
    pass


class WeatherProviderError(Exception):
    """Raised when Open-Meteo itself is unavailable or rate-limiting us -
    distinct from CityNotFoundError, which means the request succeeded but
    the city doesn't exist. This lets endpoints return a clean 503
    ('try again shortly') instead of a generic, unhelpful 500."""


def _cache_key(url: str, params: dict) -> str:
    return url + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))


async def _get(url: str, params: dict) -> dict:
    """Shared GET wrapper for every Open-Meteo call. Centralizing this
    means the 429/5xx handling only needs to be written once, not
    duplicated across six near-identical functions.

    Also caches responses (see _CACHE_TTL_SECONDS above) and, if a fresh
    fetch fails because Open-Meteo is rate-limiting or unavailable, falls
    back to serving a stale cached value for that exact query rather than
    failing outright - so a transient provider outage degrades to slightly
    stale data instead of an error screen, wherever we've seen that query
    succeed before."""
    key = _cache_key(url, params)
    ttl = _CACHE_TTL_SECONDS.get(url, _DEFAULT_TTL_SECONDS)
    now = time.monotonic()

    cached = _cache.get(key)
    if cached is not None and (now - cached[0]) < ttl:
        return cached[1]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            provider_error = WeatherProviderError("Weather provider rate limit reached")
        elif exc.response.status_code >= 500:
            provider_error = WeatherProviderError("Weather provider is currently unavailable")
        else:
            raise
        if cached is not None:
            logger.warning("Serving stale cached data for %s after provider error: %s", url, provider_error)
            return cached[1]
        raise provider_error from exc
    except httpx.RequestError as exc:
        if cached is not None:
            logger.warning("Serving stale cached data for %s after provider error: could not reach provider", url)
            return cached[1]
        raise WeatherProviderError("Could not reach weather provider") from exc

    _cache[key] = (now, data)
    return data


async def resolve_city(city_name: str) -> dict:
    data = await _get(GEOCODING_URL, {"name": city_name, "count": 1})

    results = data.get("results")
    if not results:
        raise CityNotFoundError(f"No location found for '{city_name}'")

    match = results[0]
    return {
        "name": match["name"],
        "country": match.get("country", ""),
        "latitude": match["latitude"],
        "longitude": match["longitude"],
        "timezone": match["timezone"],
    }


async def fetch_current_weather(latitude: float, longitude: float, timezone: str) -> dict:
    return await _get(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day",
            "daily": "sunrise,sunset,uv_index_max",
            "timezone": timezone,
        },
    )


async def fetch_forecast(latitude: float, longitude: float, timezone: str) -> dict:
    return await _get(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max",
            "forecast_days": 5,
            "timezone": timezone,
        },
    )


async def fetch_hourly_forecast(latitude: float, longitude: float, timezone: str) -> dict:
    return await _get(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,weather_code,precipitation_probability,wind_speed_10m,apparent_temperature",
            "forecast_days": 2,
            "timezone": timezone,
        },
    )


async def fetch_air_quality(latitude: float, longitude: float) -> dict:
    return await _get(
        AIR_QUALITY_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "us_aqi",
        },
    )




async def fetch_extended_daily_forecast(latitude: float, longitude: float, timezone: str, forecast_days: int = 16) -> dict:
    """Fetches a longer daily forecast window than the homepage's 5-day
    view uses, for multi-day trip planning. Open-Meteo's free tier
    supports up to 16 forecast days."""
    return await _get(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max,wind_speed_10m_max",
            "forecast_days": min(forecast_days, 16),
            "timezone": timezone,
        },
    )