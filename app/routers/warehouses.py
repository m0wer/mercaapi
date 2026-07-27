from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Warehouse, WarehousePublic

router = APIRouter(prefix="/warehouses", tags=["warehouses"])


@router.get("/", response_model=List[WarehousePublic])
def get_warehouses(session: Session = Depends(get_session)):
    """List known Mercadona warehouses (discovered from postal codes)."""
    return session.exec(select(Warehouse)).all()
