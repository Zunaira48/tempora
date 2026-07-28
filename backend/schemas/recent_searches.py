from datetime import datetime
from pydantic import BaseModel


class RecentSearchCreate(BaseModel):
    city_name: str
    country: str | None = None


class RecentSearchResponse(BaseModel):
    id: int
    city_name: str
    country: str | None
    searched_at: datetime

    class Config:
        from_attributes = True
        