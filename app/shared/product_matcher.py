import unidecode
from fuzzywuzzy import fuzz
from loguru import logger
from app.models import Product, ProductMatch, ProductPublic


def find_closest_products(
    products: list[Product],
    item_name: str | None = None,
    item_price: float | None = None,
    threshold: float = 0.0,
) -> list[ProductMatch]:
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
        # Combine name and price scores with weights
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
    for match in matches[:5]:
        logger.debug(
            f"  Match: {match.product.name}, {match.product.price:.2f} € (Score: {match.score:.2f})"
        )
    return matches
