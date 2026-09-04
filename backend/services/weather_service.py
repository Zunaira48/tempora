import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


class CityNotFoundError(Exception):
    pass


class WeatherProviderError(Exception):
    """Raised when Open-Meteo itself is unavailable or rate-limiting us -
    distinct from CityNotFoundError, which means the request succeeded but
    the city doesn't exist. This lets endpoints return a clean 503
    ('try again shortly') instead of a generic, unhelpful 500."""


async def _get(url: str, params: dict) -> dict:
    """Shared GET wrapper for every Open-Meteo call. Centralizing this
    means the 429/5xx handling only needs to be written once, not
    duplicated across six near-identical functions."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise WeatherProviderError("Weather provider rate limit reached") from exc
            if exc.response.status_code >= 500:
                raise WeatherProviderError("Weather provider is currently unavailable") from exc
            raise
        except httpx.RequestError as exc:
            raise WeatherProviderError("Could not reach weather provider") from exc
        return response.json()


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