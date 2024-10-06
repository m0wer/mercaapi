from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models import Product, NutritionalInformation, ProductImage, ProductMatch
from app.shared.cache import get_all_products
from app.shared.product_matcher import find_closest_products
from typing import List
import logging

router = APIRouter(prefix="/products", tags=["products"])
logger = logging.getLogger(__name__)


@router.get("/")
def get_products(
    skip: int = 0, limit: int = 100, session: Session = Depends(get_session)
):
    products = session.exec(select(Product).offset(skip).limit(limit)).all()
    return products


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

    return matches[:max_results]


@router.get("/{product_id}")
def get_product(product_id: str, session: Session = Depends(get_session)):
    result = session.exec(
        select(Product)
        .join(NutritionalInformation, isouter=True)
        .join(ProductImage, isouter=True)
        .where(Product.id == product_id)
    ).first()

    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")

    product = result

    return {
        **product.model_dump(),
        "nutritional_information": product.nutritional_information.model_dump(
            exclude={"id"}
        )
        if product.nutritional_information is not None
        else None,
        "images": [
            image.model_dump(exclude={"id", "product_id"}) for image in product.images
        ],
    }
