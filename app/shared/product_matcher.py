import unidecode
from thefuzz import process, fuzz
from loguru import logger
from app.models import ProductMatch, ProductPublic
from typing import List, Optional


def find_closest_products_task(
    products: List[ProductPublic],
    item_name: Optional[str] = None,
    item_price: Optional[float] = None,
    threshold: float = 60.0,
    max_matches: int = 10,
    price_tolerance: float = 0.2,
) -> List[ProductMatch]:
    """
    Find closest products based on name and price similarity using thefuzz process.
    """
    logger.info(
        f"Processing product matching task for '{item_name}' with price {item_price}"
    )
    if not products:
        logger.warning("No products provided for matching.")
        return []

    matches = []
    if item_name is not None:
        product_names = [unidecode.unidecode(p.name.lower()) for p in products]
        name_matches = process.extract(
            unidecode.unidecode(item_name.lower()),
            product_names,
            scorer=fuzz.token_set_ratio,
            limit=len(products),
        )
        for name, name_score in name_matches:
            index = product_names.index(name)
            product = products[index]
            # Calculate price score if price is provided
            price_score = 100.0
            if item_price is not None:
                price_diff = abs(product.price - item_price)
                if price_diff / item_price > price_tolerance:
                    price_score = 0.0
                else:
                    price_score = max(0, 100 - (price_diff / item_price) * 100)
            # Calculate combined score
            combined_score = (name_score * 0.7) + (price_score * 0.3)
            if combined_score >= threshold:
                matches.append(
                    ProductMatch(
                        score=combined_score,
                        product=ProductPublic.model_validate(product),
                    )
                )

    # Sort matches by score in descending order
    matches.sort(key=lambda x: x.score, reverse=True)
    # Remove duplicate products, keeping the highest scoring match for each product
    unique_matches = []
    seen_products = set()
    for match in matches:
        if match.product.id not in seen_products:
            unique_matches.append(match)
            seen_products.add(match.product.id)
    # Log debug information
    logger.debug(
        f"Found {len(unique_matches)} unique matches for item '{item_name}' with price {item_price}"
    )
    for match in unique_matches[:5]:
        logger.debug(
            f"  Match: {match.product.name}, {match.product.price:.2f} € (Score: {match.score:.2f})"
        )
    return unique_matches[:max_matches]
