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