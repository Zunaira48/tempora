from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from schemas.weather import WeatherResponse, CurrentWeather, ForecastResponse, DailyForecast
from services.weather_service import (
    resolve_city,
    fetch_current_weather,
    fetch_forecast,
    CityNotFoundError,
)
from services.weather_codes import describe_condition

app = FastAPI(title="Tempora API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

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
    daily = raw["daily"]
    condition_text, condition_icon = describe_condition(current["weather_code"])

    return WeatherResponse(
        city=location["name"],
        country=location["country"],
        latitude=location["latitude"],
        longitude=location["longitude"],
        local_time=current["time"],
        sunrise=daily["sunrise"][0],
        sunset=daily["sunset"][0],
        current=CurrentWeather(
            temperature_c=current["temperature_2m"],
            feels_like_c=current["apparent_temperature"],
            humidity_percent=current["relative_humidity_2m"],
            wind_speed_kmh=current["wind_speed_10m"],
            condition_code=current["weather_code"],
            condition_text=condition_text,
            condition_icon=condition_icon,
            is_day=bool(current["is_day"]),
        ),
    )


@app.get("/weather/forecast", response_model=ForecastResponse)
async def get_forecast(city: str = Query(..., min_length=1)):
    try:
        location = await resolve_city(city)
    except CityNotFoundError:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found")

    raw = await fetch_forecast(
        location["latitude"], location["longitude"], location["timezone"]
    )
    daily = raw["daily"]

    days = []
    for i in range(len(daily["time"])):
        condition_text, condition_icon = describe_condition(daily["weather_code"][i])
        days.append(
            DailyForecast(
                date=daily["time"][i],
                temperature_max_c=daily["temperature_2m_max"][i],
                temperature_min_c=daily["temperature_2m_min"][i],
                condition_code=daily["weather_code"][i],
                condition_text=condition_text,
                condition_icon=condition_icon,
                precipitation_probability_percent=daily["precipitation_probability_max"][i],
            )
        )

    return ForecastResponse(
        city=location["name"],
        country=location["country"],
        days=days,
    )