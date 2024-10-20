import unidecode
from fuzzywuzzy import fuzz
from loguru import logger
from app.models import ProductMatch, ProductPublic
from typing import List, Optional


def find_closest_products_task(
    products: List[ProductPublic] = [],
    item_name: Optional[str] = None,
    item_price: Optional[float] = None,
    threshold: float = 60.0,
    max_matches: int = 10,
) -> List[ProductMatch]:
    """
    Task to find closest products based on name and price similarity.
    """
    logger.info(
        f"Processing product matching task for '{item_name}' with price {item_price}"
    )
    if not products:
        logger.warning("No products provided for matching.")
        return []
    matches = []

    for product in products:
        name_score: float = 0.0
        price_score: float = 0.0

        if item_name is not None:
            name_score = fuzz.token_set_ratio(
                unidecode.unidecode(item_name.lower()),
                unidecode.unidecode(product.name.lower()),
            )

        if item_price:
            price_diff = abs(product.price - item_price)
            price_score = max(0, 100 - (price_diff / item_price) * 100)

        combined_score = (name_score * 0.7) + (price_score * 0.3)

        if combined_score >= threshold:
            matches.append(
                ProductMatch(
                    score=combined_score, product=ProductPublic.model_validate(product)
                )
            )

    matches.sort(key=lambda x: x.score, reverse=True)
    logger.debug(
        f"Found {len(matches)} matches for item '{item_name}' with price {item_price}"
    )
    return matches[:max_matches]
