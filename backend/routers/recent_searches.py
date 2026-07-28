from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from auth.dependencies import get_current_user
from schemas.recent_searches import RecentSearchCreate, RecentSearchResponse
import models

router = APIRouter(prefix="/recent-searches", tags=["recent-searches"])

MAX_RECENT_SEARCHES = 5


@router.get("", response_model=list[RecentSearchResponse])
def list_recent_searches(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.RecentSearch)
        .filter(models.RecentSearch.user_id == current_user.id)
        .order_by(models.RecentSearch.searched_at.desc())
        .limit(MAX_RECENT_SEARCHES)
        .all()
    )


@router.post("", response_model=RecentSearchResponse, status_code=201)
def record_search(
    payload: RecentSearchCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    existing = (
        db.query(models.RecentSearch)
        .filter(
            models.RecentSearch.user_id == current_user.id,
            models.RecentSearch.city_name == payload.city_name,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()

    entry = models.RecentSearch(user_id=current_user.id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)

    all_entries = (
        db.query(models.RecentSearch)
        .filter(models.RecentSearch.user_id == current_user.id)
        .order_by(models.RecentSearch.searched_at.desc())
        .offset(MAX_RECENT_SEARCHES)
        .all()
    )
    for old_entry in all_entries:
        db.delete(old_entry)
    db.commit()

    return entry