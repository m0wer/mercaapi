from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.database import get_session
from app.models import Product, NutritionalInformation, ProductImage, ProductMatch
from app.shared.cache import cache
from fuzzywuzzy import fuzz
from typing import List

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/")
def get_products(
    skip: int = 0, limit: int = 100, session: Session = Depends(get_session)
):
    products = session.exec(select(Product).offset(skip).limit(limit)).all()
    return products


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


@router.get("/closest", response_model=List[ProductMatch])
def get_closest_product(
    name: str | None = None,
    unit_price: float | None = None,
    max_results: int = Query(default=10, le=100),
    session: Session = Depends(get_session),
):
    if name is None and unit_price is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of name or unit_price must be provided",
        )

    products = get_all_products(session)
    matches = []

    for product in products:
        score: float = 0.0
        if name:
            name_score = fuzz.token_set_ratio(name.lower(), product.name.lower())
            score += name_score * 0.7  # Weight name match more heavily

        if unit_price is not None:
            price_diff = abs(product.price - unit_price)
            price_score = max(0, 100 - (price_diff / unit_price) * 100)
            score += price_score * 0.3

        if score > 0:
            matches.append(ProductMatch(score=score, product=product))

    # Sort matches by score in descending order and limit to max_results
    matches.sort(key=lambda x: x.score, reverse=True)
    return matches[:max_results]


def get_all_products(session: Session):
    cached_products = cache.get("all_products")
    if cached_products:
        return cached_products

    products = session.exec(select(Product)).all()
    cache.set("all_products", products)
    return products
