"""
Builds the compact, minimal weather context object sent to the AI provider.
Only ever includes real, already-fetched values - never fabricated ones.
"""


def build_current_context(location: dict, current_weather: dict, aqi: int | None) -> dict:
    current = current_weather.get("current", {})
    daily = current_weather.get("daily", {})
    uv_values = daily.get("uv_index_max", [])

    return {
        "location": {
            "city": location.get("name"),
            "country": location.get("country"),
        },
        "current": {
            "temperature_c": current.get("temperature_2m"),
            "feels_like_c": current.get("apparent_temperature"),
            "humidity_percent": current.get("relative_humidity_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "uv_index": uv_values[0] if uv_values else None,
            "aqi": aqi,
        },
    }