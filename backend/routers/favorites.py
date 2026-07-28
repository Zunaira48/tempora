from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from auth.dependencies import get_current_user
from schemas.favorites import FavoriteCreate, FavoriteResponse
import models

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=list[FavoriteResponse])
def list_favorites(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Favorite)
        .filter(models.Favorite.user_id == current_user.id)
        .order_by(models.Favorite.created_at.desc())
        .all()
    )


@router.post("", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
def add_favorite(
    payload: FavoriteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    existing = (
        db.query(models.Favorite)
        .filter(
            models.Favorite.user_id == current_user.id,
            models.Favorite.city_name == payload.city_name,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="City already in favorites")

    favorite = models.Favorite(user_id=current_user.id, **payload.model_dump())
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    favorite_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    favorite = (
        db.query(models.Favorite)
        .filter(models.Favorite.id == favorite_id, models.Favorite.user_id == current_user.id)
        .first()
    )
    if not favorite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")

    db.delete(favorite)
    db.commit()