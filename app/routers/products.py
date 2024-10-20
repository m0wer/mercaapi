from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from app.database import get_session
from app.models import ProductMatch, ProductPublic
from app.worker import find_closest_products_with_preload
from app.shared.cache import get_all_products
from typing import List
from loguru import logger

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=List[ProductPublic])
def get_products(
    skip: int = 0, limit: int = 100, session: Session = Depends(get_session)
):
    products = get_all_products(session)[skip : skip + limit]
    return [ProductPublic.model_validate(product) for product in products]


@router.get("/closest", response_model=List[ProductMatch])
async def get_closest_product(
    name: str | None = None,
    unit_price: float | None = None,
    max_results: int = Query(default=10, le=100),
    threshold: int = Query(default=60, ge=0, le=100),
    session: Session = Depends(get_session),
):
    if name is None and unit_price is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of name or unit_price must be provided",
        )

    logger.info(
        f"Enqueueing product matching task for name='{name}', price={unit_price}"
    )

    # Use the task directly from the worker
    task = find_closest_products_with_preload.delay(
        item_name=name,
        item_price=unit_price,
        threshold=threshold,
    )

    try:
        matches = task.get(timeout=10)  # Wait for up to 10 seconds for the result
    except Exception as e:
        logger.error(f"Error getting task result: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing product matching")

    if not matches:
        logger.warning(f"No matches found for query: name='{name}', price={unit_price}")
        return []

    logger.info(
        f"Found {len(matches)} matches for query: name='{name}', price={unit_price}"
    )
    return matches[:max_results]


@router.get("/{product_id}", response_model=ProductPublic)
def get_product(product_id: str, session: Session = Depends(get_session)):
    products = get_all_products(session)
    result = next(
        iter([product for product in products if product.id == product_id]), None
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    product = result
    return ProductPublic.model_validate(product)
