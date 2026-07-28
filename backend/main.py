from fastapi import FastAPI, HTTPException, Query

from schemas.weather import WeatherResponse, CurrentWeather
from services.weather_service import resolve_city, fetch_current_weather, CityNotFoundError

app = FastAPI(title="Tempora API")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/weather", response_model=WeatherResponse)
async def get_weather(city: str = Query(..., min_length=1)):
    try:
        location = await resolve_city(city)
    except CityNotFoundError:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found")

    raw = await fetch_current_weather(
        location["latitude"], location["longitude"], location["timezone"]
    )
    current = raw["current"]

    return WeatherResponse(
        city=location["name"],
        country=location["country"],
        latitude=location["latitude"],
        longitude=location["longitude"],
        local_time=current["time"],
        current=CurrentWeather(
            temperature_c=current["temperature_2m"],
            feels_like_c=current["apparent_temperature"],
            humidity_percent=current["relative_humidity_2m"],
            wind_speed_kmh=current["wind_speed_10m"],
            condition_code=current["weather_code"],
            is_day=bool(current["is_day"]),
        ),
    )