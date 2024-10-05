from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.database import get_session
from app.models import Category
from app.shared.cache import cache

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/")
def get_categories(
    skip: int = 0, limit: int = 100, session: Session = Depends(get_session)
):
    categories = session.exec(select(Category).offset(skip).limit(limit)).all()
    return categories


def get_all_categories(session: Session):
    cached_categories = cache.get("all_categories")
    if cached_categories:
        return cached_categories

    categories = session.exec(select(Category)).all()
    cache.set("all_categories", categories)
    return categories
