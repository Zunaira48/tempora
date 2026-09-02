"""
Thin wrapper around the Gemini API's REST endpoint. This module knows
nothing about weather, Tempora, or prompts - it only knows how to send a
system+user prompt to Gemini and return text, or raise a clear error.

Swapping AI providers later means rewriting this one file; nothing that
calls generate_text() needs to change.
"""

import httpx

import config

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AIProviderError(Exception):
    """Raised whenever the AI provider can't be used - missing config,
    network failure, timeout, rate limit, or an unexpected response shape."""


async def generate_text(system_prompt: str, user_prompt: str, max_output_tokens: int = 400) -> str:
    if not config.GEMINI_API_KEY:
        raise AIProviderError("AI provider is not configured")

    url = GEMINI_ENDPOINT.format(model=config.AI_MODEL)

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_output_tokens,
            "temperature": 0.4,
            "thinkingConfig": {"thinkingLevel": "minimal"},
        },
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                headers={"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise AIProviderError("AI provider timed out") from exc
    except httpx.RequestError as exc:
        raise AIProviderError("Could not reach AI provider") from exc

    if response.status_code == 429:
        raise AIProviderError("AI provider rate limit reached")
    if response.status_code >= 400:
        raise AIProviderError(f"AI provider returned an error ({response.status_code})")

    try:
        data = response.json()
        candidate = data["candidates"][0]
        text = candidate["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AIProviderError("AI provider returned an unexpected response") from exc

    if candidate.get("finishReason") == "MAX_TOKENS":
        raise AIProviderError("AI response was cut off before completing")

    return text.strip()