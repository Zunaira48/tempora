from pydantic import BaseModel, Field

import config


class AIRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=config.AI_MAX_INPUT_CHARS)


class AIResponse(BaseModel):
    reply: str