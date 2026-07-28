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
    uv_index: float | None = None
    air_quality_index: int | None = None


class WeatherResponse(BaseModel):
    city: str
    country: str
    latitude: float
    longitude: float
    local_time: str
    sunrise: str
    sunset: str
    current: CurrentWeather


class DailyForecast(BaseModel):
    date: str
    temperature_max_c: float
    temperature_min_c: float
    condition_code: int
    condition_text: str
    condition_icon: str
    precipitation_probability_percent: int


class ForecastResponse(BaseModel):
    city: str
    country: str
    days: list[DailyForecast]


class HourlyForecast(BaseModel):
    time: str
    temperature_c: float
    condition_code: int
    condition_text: str
    condition_icon: str


class HourlyResponse(BaseModel):
    city: str
    country: str
    hours: list[HourlyForecast]