from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from schemas.weather import (
    WeatherResponse,
    CurrentWeather,
    ForecastResponse,
    DailyForecast,
    HourlyResponse,
    HourlyForecast,
)
from services.weather_service import (
    resolve_city,
    fetch_current_weather,
    fetch_forecast,
    fetch_hourly_forecast,
    fetch_air_quality,
    CityNotFoundError,
)
from services.weather_codes import describe_condition
from routers.auth import router as auth_router
from routers.favorites import router as favorites_router
from routers.recent_searches import router as recent_searches_router
from starlette.exceptions import HTTPException as StarletteHTTPException
from error_handlers import http_exception_handler, unhandled_exception_middleware

import config


app = FastAPI(title="Tempora API")

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.middleware("http")(unhandled_exception_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(favorites_router)
app.include_router(recent_searches_router)


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

    aqi_value = None
    try:
        air_quality_raw = await fetch_air_quality(location["latitude"], location["longitude"])
        aqi_value = air_quality_raw.get("current", {}).get("us_aqi")
    except Exception:
        pass

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
            uv_index=daily.get("uv_index_max", [None])[0],
            air_quality_index=aqi_value,
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


@app.get("/weather/hourly", response_model=HourlyResponse)
async def get_hourly(city: str = Query(..., min_length=1)):
    try:
        location = await resolve_city(city)
    except CityNotFoundError:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found")

    raw = await fetch_hourly_forecast(
        location["latitude"], location["longitude"], location["timezone"]
    )
    hourly = raw["hourly"]

    hours = []
    for i in range(len(hourly["time"])):
        condition_text, condition_icon = describe_condition(hourly["weather_code"][i])
        hours.append(
            HourlyForecast(
                time=hourly["time"][i],
                temperature_c=hourly["temperature_2m"][i],
                condition_code=hourly["weather_code"][i],
                condition_text=condition_text,
                condition_icon=condition_icon,
            )
        )

    return HourlyResponse(
        city=location["name"],
        country=location["country"],
        hours=hours,
    )