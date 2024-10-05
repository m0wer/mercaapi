import asyncio
import time
from datetime import datetime

from app.models import Category, Product, ProductImage, PriceHistory
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import aiohttp

BASE_URL = "https://tienda.mercadona.es/api"


class RateLimiter:
    def __init__(self, rate_limit):
        self.rate_limit = rate_limit
        self.tokens = rate_limit
        self.updated_at = time.monotonic()

    async def acquire(self):
        while True:
            now = time.monotonic()
            time_passed = now - self.updated_at
            self.tokens += time_passed * self.rate_limit
            if self.tokens > self.rate_limit:
                self.tokens = self.rate_limit
            self.updated_at = now

            if self.tokens >= 1:
                self.tokens -= 1
                return
            else:
                await asyncio.sleep(1 / self.rate_limit)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    retry=retry_if_exception_type(
        (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            aiohttp.client_exceptions.ContentTypeError,
            aiohttp.client_exceptions.ClientResponseError,
        )
    ),
)
async def fetch(session, url, rate_limiter):
    await rate_limiter.acquire()
    async with session.get(url) as response:
        if response.status == 404:
            logger.warning(f"Resource not found: {url}")
            return None
        elif response.status == 429:
            logger.warning(f"Rate limit exceeded: {url}")
            await asyncio.sleep(60)  # Wait for 1 minute before retrying
            raise aiohttp.client_exceptions.ClientResponseError(
                response.request_info,
                response.history,
                status=429,
                message="Rate limit exceeded",
            )
        response.raise_for_status()
        return await response.json()


async def parse_categories(session, rate_limiter):
    categories = await fetch(session, f"{BASE_URL}/categories/", rate_limiter)
    if categories:
        for category in categories["results"]:
            yield Category(id=category["id"], name=category["name"])
            for subcategory in category.get("categories", []):
                yield Category(
                    id=subcategory["id"],
                    name=subcategory["name"],
                    parent_id=category["id"],
                )


async def parse_products(session, category_id, rate_limiter, existing_product_ids):
    category_data = await fetch(
        session, f"{BASE_URL}/categories/{category_id}", rate_limiter
    )
    if category_data and "categories" in category_data:
        for subcategory in category_data["categories"]:
            for product in subcategory.get("products", []):
                product_details = await fetch(
                    session, f"{BASE_URL}/products/{product['id']}", rate_limiter
                )
                if product_details:
                    yield Product(
                        id=product_details["id"],
                        ean=product_details.get("ean"),
                        slug=product_details["slug"],
                        brand=product_details.get("brand"),
                        name=product_details["display_name"],
                        price=float(
                            product_details["price_instructions"]["unit_price"]
                        ),
                        category_id=category_id,
                        description=product_details.get("details", {}).get(
                            "description"
                        ),
                        origin=product_details.get("origin"),
                        packaging=product_details.get("packaging"),
                        unit_name=product_details["price_instructions"].get(
                            "unit_name"
                        ),
                        unit_size=product_details["price_instructions"].get(
                            "unit_size"
                        ),
                        is_variable_weight=product_details.get(
                            "is_variable_weight", False
                        ),
                        is_pack=product_details["price_instructions"].get(
                            "is_pack", False
                        ),
                        images=[
                            ProductImage(
                                zoom_url=photo["zoom"],
                                regular_url=photo["regular"],
                                thumbnail_url=photo["thumbnail"],
                                perspective=photo["perspective"],
                            )
                            for photo in product_details.get("photos", [])
                        ],
                    )


async def parse_category_products(
    engine, session, category_id, rate_limiter, skip_existing_products=True
):
    with Session(engine) as db_session:
        existing_product_ids = set(
            db_session.exec(
                select(Product.id).where(Product.category_id == category_id)
            ).all()
        )

    new_products = []
    updated_products = []

    async for product in parse_products(
        session, category_id, rate_limiter, existing_product_ids
    ):
        if product.id in existing_product_ids:
            updated_products.append(product)
        else:
            new_products.append(product)

    with Session(engine) as db_session:
        for product in new_products:
            try:
                logger.info(f"Adding new product: {product.name}")
                db_session.add(product)
                db_session.add(
                    PriceHistory(
                        product_id=product.id,
                        price=product.price,
                        timestamp=datetime.now(),
                    )
                )
                db_session.commit()
            except IntegrityError:
                logger.warning(f"Product {product.id} already exists, skipping")
                db_session.rollback()

        for product in updated_products:
            try:
                logger.info(f"Updating existing product: ({product.id}) {product.name}")
                db_product = db_session.exec(
                    select(Product).where(Product.id == product.id)
                ).one()

                if db_product.price != product.price:
                    logger.info(
                        f"Price change for product {product.id}: {db_product.price} -> {product.price}"
                    )
                    db_session.add(
                        PriceHistory(
                            product_id=product.id,
                            price=product.price,
                            timestamp=datetime.now(),
                        )
                    )

                for key, value in product.dict().items():
                    setattr(db_product, key, value)
                db_session.commit()
            except Exception as e:
                logger.error(f"Error updating product {product.id}: {str(e)}")
                db_session.rollback()

    return len(new_products), len(updated_products)


async def parse_mercadona(engine, max_requests_per_second, skip_existing_products=True):
    logger.info("Starting Mercadona parsing")
    rate_limiter = RateLimiter(max_requests_per_second)
    async with aiohttp.ClientSession() as session:
        categories = [
            category async for category in parse_categories(session, rate_limiter)
        ]
        with Session(engine) as db_session:
            for category in categories:
                existing_category = db_session.exec(
                    select(Category).where(Category.id == category.id)
                ).first()
                if existing_category:
                    logger.info(
                        f"Updating existing category: ({category.id}) {category.name}"
                    )
                    existing_category.name = category.name
                    existing_category.parent_id = category.parent_id
                else:
                    logger.info(f"Adding new category: {category.name}")
                    db_session.add(category)
            db_session.commit()

        tasks = []
        for category in categories:
            task = asyncio.create_task(
                parse_category_products(
                    engine,
                    session,
                    category.id,
                    rate_limiter,
                    skip_existing_products=skip_existing_products,
                )
            )
            tasks.append(task)

        try:
            results = await asyncio.gather(*tasks)

            for category, (new_product_count, updated_product_count) in zip(
                categories, results
            ):
                logger.info(
                    f"Category {category.name} updated with {new_product_count} new products and {updated_product_count} updated products"
                )
        except Exception as e:
            logger.error(f"An unexpected error occurred: {str(e)}")

    logger.info("Mercadona parsing completed")
