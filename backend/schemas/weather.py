from pydantic import BaseModel


class CurrentWeather(BaseModel):
    temperature_c: float
    feels_like_c: float
    humidity_percent: int
    wind_speed_kmh: float
    condition_code: int
    is_day: bool


class WeatherResponse(BaseModel):
    city: str
    country: str
    latitude: float
    longitude: float
    local_time: str
    current: CurrentWeather