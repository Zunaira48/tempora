from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
from auth.dependencies import get_current_user
from database import get_db
from services.weather_service import resolve_city, fetch_current_weather, fetch_air_quality, CityNotFoundError
from services.ai.context import build_current_context
from services.ai.prompts import COPILOT_SYSTEM_PROMPT
from services.ai.provider import generate_text, AIProviderError
from services.ai.rate_limiter import check_rate_limit, RateLimitExceeded
from services.ai.schemas import CopilotRequest, CopilotResponse

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
    except AIProviderError:
        raise HTTPException(
            status_code=503,
            detail="Tempora Copilot is temporarily unavailable. Weather data is still available.",
        )

    return CopilotResponse(reply=reply)