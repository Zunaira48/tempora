import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


class CityNotFoundError(Exception):
    pass


async def resolve_city(city_name: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GEOCODING_URL,
            params={"name": city_name, "count": 1},
        )
        response.raise_for_status()
        data = response.json()

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
    async with httpx.AsyncClient() as client:
        response = await client.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day",
                "daily": "sunrise,sunset,uv_index_max",
                "timezone": timezone,
            },
        )
        response.raise_for_status()
        return response.json()


async def fetch_forecast(latitude: float, longitude: float, timezone: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max",
                "forecast_days": 5,
                "timezone": timezone,
            },
        )
        response.raise_for_status()
        return response.json()


async def fetch_hourly_forecast(latitude: float, longitude: float, timezone: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "hourly": "temperature_2m,weather_code,precipitation_probability,wind_speed_10m,apparent_temperature",
                "forecast_days": 2,
                "timezone": timezone,
            },
        )
        response.raise_for_status()
        return response.json()


async def fetch_air_quality(latitude: float, longitude: float) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            AIR_QUALITY_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "us_aqi",
            },
        )
        response.raise_for_status()
        return response.json()




async def fetch_extended_daily_forecast(latitude: float, longitude: float, timezone: str, forecast_days: int = 16) -> dict:
    """Fetches a longer daily forecast window than the homepage's 5-day
    view uses, for multi-day trip planning. Open-Meteo's free tier
    supports up to 16 forecast days."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max,wind_speed_10m_max",
                "forecast_days": min(forecast_days, 16),
                "timezone": timezone,
            },
        )
        response.raise_for_status()
        return response.json()