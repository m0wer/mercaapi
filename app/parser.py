import asyncio
import aiohttp
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from sqlmodel import Session, select
from app.models import Category, Product, ProductImage
from app.database import engine
from loguru import logger
import time

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


async def parse_products(session, category_id, rate_limiter):
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


async def parse_category_products(session, category_id, rate_limiter):
    products = [
        product async for product in parse_products(session, category_id, rate_limiter)
    ]
    with Session(engine) as db_session:
        for product in products:
            existing_product = db_session.exec(
                select(Product).where(Product.id == product.id)
            ).first()
            if existing_product:
                logger.info(f"Updating existing product: {product.name}")
                for key, value in product.dict(exclude={"images"}).items():
                    setattr(existing_product, key, value)

                # Update images
                db_session.exec(
                    select(ProductImage).where(
                        ProductImage.product_id == existing_product.id
                    )
                ).delete()
                existing_product.images = product.images
            else:
                logger.info(f"Adding new product: {product.name}")
                db_session.add(product)
        db_session.commit()


async def parse_mercadona(max_requests_per_second):
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
                parse_category_products(session, category.id, rate_limiter)
            )
            tasks.append(task)
        await asyncio.gather(*tasks)
