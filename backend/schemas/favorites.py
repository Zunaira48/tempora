from datetime import datetime
from pydantic import BaseModel


class FavoriteCreate(BaseModel):
    city_name: str
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class FavoriteResponse(BaseModel):
    id: int
    city_name: str
    country: str | None
    latitude: float | None
    longitude: float | None
    created_at: datetime

    class Config:
        from_attributes = True