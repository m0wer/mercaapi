from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from sqlmodel import select, Session

from app.models import Product, NutritionalInformation, ProductImage


class Cache:
    def __init__(self, timeout: int = 3600):
        self.data: dict[str, Any] = {}
        self.timeout = timeout

    def get(self, key: str):
        if key in self.data:
            value, timestamp = self.data[key]
            if datetime.now() - timestamp < timedelta(seconds=self.timeout):
                return value
        return None

    def set(self, key: str, value: Any):
        self.data[key] = (value, datetime.now())


cache = Cache()


def get_all_products(session: Session):
    cached_products = cache.get("all_products")
    if cached_products:
        logger.debug("Retrieved products from cache")
        return cached_products

    logger.debug("Fetching all products from database")
    products = session.exec(
        select(Product)
        .join(NutritionalInformation, isouter=True)
        .join(ProductImage, isouter=True)
    ).all()
    cache.set("all_products", products)
    return products
