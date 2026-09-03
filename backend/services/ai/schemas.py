from pydantic import BaseModel, Field

import config


class AIRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=config.AI_MAX_INPUT_CHARS)


class AIResponse(BaseModel):
    reply: str


class CopilotRequest(BaseModel):
    city: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=config.AI_MAX_INPUT_CHARS)


class CopilotResponse(BaseModel):
    reply: str


class ExplainWeatherRequest(BaseModel):
    city: str = Field(..., min_length=1, max_length=100)


class ExplainWeatherResponse(BaseModel):
    summary: str
    score: int
    score_components: dict[str, int]



class ActivityAdvisorRequest(BaseModel):
    city: str = Field(..., min_length=1, max_length=100)
    activity: str


class ActivityAdvisorResponse(BaseModel):
    activity_label: str
    best_window_start: str
    best_window_end: str
    score: int
    reasons: list[str]
    summary: str



class PlanMyDayRequest(BaseModel):
    city: str = Field(..., min_length=1, max_length=100)
    plan_text: str = Field(..., min_length=1, max_length=500)


class PlanEventResult(BaseModel):
    time: str
    label: str
    temperature_c: float
    condition_score: int
    comfort_label: str


class PlanMyDayResponse(BaseModel):
    schedule: list[PlanEventResult]
    summary: str



class CityComparisonRequest(BaseModel):
    city_a: str = Field(..., min_length=1, max_length=100)
    city_b: str = Field(..., min_length=1, max_length=100)
    purpose: str = Field(default="", max_length=200)


class CityWeatherSummary(BaseModel):
    city: str
    country: str
    temperature_c: float
    feels_like_c: float
    humidity_percent: int
    wind_speed_kmh: float
    aqi: int | None
    uv_index: float | None


class CityComparisonResponse(BaseModel):
    city_a: CityWeatherSummary
    city_b: CityWeatherSummary
    summary: str



class FavoriteCitiesResponse(BaseModel):
    cities: list[CityWeatherSummary]
    summary: str



class TravelBriefRequest(BaseModel):
    city: str = Field(..., min_length=1, max_length=100)
    start_date: str
    end_date: str
    purpose: str = Field(default="", max_length=200)


class TravelBriefDay(BaseModel):
    date: str
    has_data: bool
    temperature_max_c: float | None = None
    temperature_min_c: float | None = None
    score: int | None = None
    watch_out_for: list[str] = []


class TravelBriefResponse(BaseModel):
    days: list[TravelBriefDay]
    best_day: str | None
    summary: str