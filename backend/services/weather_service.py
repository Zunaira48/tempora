import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


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
                "daily": "sunrise,sunset",
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