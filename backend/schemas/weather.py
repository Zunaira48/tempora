from pydantic import BaseModel


class CurrentWeather(BaseModel):
    temperature_c: float
    feels_like_c: float
    humidity_percent: int
    wind_speed_kmh: float
    condition_code: int
    condition_text: str
    condition_icon: str
    is_day: bool


class WeatherResponse(BaseModel):
    city: str
    country: str
    latitude: float
    longitude: float
    local_time: str
    sunrise: str
    sunset: str
    current: CurrentWeather