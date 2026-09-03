import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger("tempora")

import models
from auth.dependencies import get_current_user
from database import get_db
from services.weather_service import resolve_city, fetch_current_weather, fetch_air_quality, CityNotFoundError
from services.ai.context import build_current_context
from services.ai.prompts import COPILOT_SYSTEM_PROMPT
from services.ai.provider import generate_text, AIProviderError
from services.ai.rate_limiter import check_rate_limit, RateLimitExceeded
from services.ai.schemas import CopilotRequest, CopilotResponse, ExplainWeatherRequest, ExplainWeatherResponse
from services.ai.prompts import EXPLAIN_WEATHER_SYSTEM_PROMPT
from services.weather_intelligence import score_current_conditions, ACTIVITY_PROFILES, find_best_activity_window, build_activity_reasons
from services.weather_service import fetch_hourly_forecast
from services.ai.prompts import ACTIVITY_ADVISOR_SYSTEM_PROMPT
from services.ai.schemas import ActivityAdvisorRequest, ActivityAdvisorResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/copilot", response_model=CopilotResponse)
async def ask_copilot(
    payload: CopilotRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        check_rate_limit(current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        location = await resolve_city(payload.city)
    except CityNotFoundError:
        raise HTTPException(status_code=404, detail=f"City '{payload.city}' not found")

    current_weather = await fetch_current_weather(
        location["latitude"], location["longitude"], location["timezone"]
    )

    aqi_value = None
    try:
        air_quality_raw = await fetch_air_quality(location["latitude"], location["longitude"])
        aqi_value = air_quality_raw.get("current", {}).get("us_aqi")
    except Exception:
        pass

    context = build_current_context(location, current_weather, aqi_value)

    user_prompt = (
        f"Weather context (JSON): {context}\n\n"
        f"User's question: {payload.message}"
    )

    try:
        reply = await generate_text(system_prompt=COPILOT_SYSTEM_PROMPT, user_prompt=user_prompt)
    except AIProviderError as exc:
        logger.warning("AI provider error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Tempora Copilot is temporarily unavailable. Weather data is still available.",
        )

    return CopilotResponse(reply=reply)



@router.post("/explain-weather", response_model=ExplainWeatherResponse)
async def explain_weather(
    payload: ExplainWeatherRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        check_rate_limit(current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        location = await resolve_city(payload.city)
    except CityNotFoundError:
        raise HTTPException(status_code=404, detail=f"City '{payload.city}' not found")

    current_weather = await fetch_current_weather(
        location["latitude"], location["longitude"], location["timezone"]
    )

    aqi_value = None
    try:
        air_quality_raw = await fetch_air_quality(location["latitude"], location["longitude"])
        aqi_value = air_quality_raw.get("current", {}).get("us_aqi")
    except Exception:
        pass

    context = build_current_context(location, current_weather, aqi_value)
    current = context["current"]

    outdoor_score = score_current_conditions(
        feels_like_c=current["feels_like_c"],
        wind_speed_kmh=current["wind_speed_kmh"],
        uv_index=current["uv_index"],
        aqi=current["aqi"],
    )

    user_prompt = (
        f"Weather context (JSON): {context}\n\n"
        f"Outdoor suitability score: {outdoor_score.overall}/100\n"
        f"Score breakdown by factor: {outdoor_score.components}\n\n"
        f"Write the Explain My Weather summary."
    )

    try:
        summary = await generate_text(system_prompt=EXPLAIN_WEATHER_SYSTEM_PROMPT, user_prompt=user_prompt)
    except AIProviderError as exc:
        logger.warning("AI provider error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Tempora Copilot is temporarily unavailable. Weather data is still available.",
        )

    return ExplainWeatherResponse(
        summary=summary,
        score=outdoor_score.overall,
        score_components=outdoor_score.components,
    )




@router.post("/activity-advisor", response_model=ActivityAdvisorResponse)
async def activity_advisor(
    payload: ActivityAdvisorRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.activity not in ACTIVITY_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown activity '{payload.activity}'")

    try:
        check_rate_limit(current_user.id)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        location = await resolve_city(payload.city)
    except CityNotFoundError:
        raise HTTPException(status_code=404, detail=f"City '{payload.city}' not found")

    hourly = await fetch_hourly_forecast(location["latitude"], location["longitude"], location["timezone"])

    window = find_best_activity_window(hourly["hourly"], payload.activity)
    if window is None:
        raise HTTPException(
            status_code=503,
            detail="No suitable time was found for this activity in the current forecast window. Try again later.",
        )

    reasons = build_activity_reasons(window["components"])
    activity_label = ACTIVITY_PROFILES[payload.activity]["label"]

    user_prompt = (
        f"Activity: {activity_label}\n"
        f"Location: {location.get('name')}, {location.get('country')}\n"
        f"Best window: {window['start_time']} to {window['end_time']}\n"
        f"Score: {window['average_score']}/100\n"
        f"Checklist: {reasons}\n\n"
        f"Write the recommendation."
    )

    try:
        summary = await generate_text(system_prompt=ACTIVITY_ADVISOR_SYSTEM_PROMPT, user_prompt=user_prompt)
    except AIProviderError as exc:
        logger.warning("AI provider error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Tempora Copilot is temporarily unavailable. Weather data is still available.",
        )

    return ActivityAdvisorResponse(
        activity_label=activity_label,
        best_window_start=window["start_time"],
        best_window_end=window["end_time"],
        score=window["average_score"],
        reasons=reasons,
        summary=summary,
    )