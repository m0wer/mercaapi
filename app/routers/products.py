from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from app.database import get_session
from app.models import ProductMatch, ProductPublic


from app.shared.cache import get_all_products
from app.shared.product_matcher import find_closest_products
from typing import List
import logging

router = APIRouter(prefix="/products", tags=["products"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[ProductPublic])
def get_products(
    skip: int = 0, limit: int = 100, session: Session = Depends(get_session)
):
    products = get_all_products(session)[skip : skip + limit]
    return [ProductPublic.model_validate(product) for product in products]


@router.get("/closest", response_model=List[ProductMatch])
def get_closest_product(
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

    products = get_all_products(session)

    matches = find_closest_products(
        products=products, item_name=name, item_price=unit_price, threshold=threshold
    )

    logger.info(
        f"Found {len(matches)} matches for query: name='{name}', price={unit_price}"
    )
    for match in matches[:5]:
        logger.debug(
            f"  Match: {match.product.name}, {match.product.price:.2f} € (Score: {match.score:.2f})"
        )

    return [
        ProductMatch(
            score=match.score, product=ProductPublic.model_validate(match.product)
        )
        for match in matches[:max_results]
    ]


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
