import asyncio
import os
import sys
import time

import click
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from loguru import logger

from app.database import get_engine
from app.parser import parse_mercadona
from app.models import Category, Product, NutritionalInformation
from app.vision.nutrition_facts import NutritionFactsExtractor
from app.routers import products, categories, ticket

# Configure loguru
logger.remove()
logger.add(
    sys.stdout, colorize=True, format="<green>{time}</green> <level>{message}</level>"
)

app = FastAPI()

# API router
api_router = FastAPI()


@api_router.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Include routers
api_router.include_router(products.router)
api_router.include_router(categories.router)
api_router.include_router(ticket.router)

# Mount the API router
app.mount("/api", api_router)

# Serve static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")


# Redirect /api to /api/docs
@app.get("/api")
async def redirect_to_docs():
    return RedirectResponse(url="/api/docs")


@click.group()
def cli():
    pass


@cli.command()
@click.option("--max-requests", default=5, help="Maximum requests per minute")
@click.option("--update-existing", is_flag=True, help="Update existing products")
def parse(max_requests, update_existing=False):
    """Parse products from Mercadona API."""
    logger.info("Starting the Mercadona parser")
    engine = get_engine()
    asyncio.run(
        parse_mercadona(
            engine, max_requests, skip_existing_products=not update_existing
        )
    )
    logger.info("Parsing completed")


def _is_food_category(category_id: int) -> bool:
    if 1 <= category_id <= 19:
        return True
    return False


def is_food_category(category: Category) -> bool:
    if _is_food_category(category.id):
        return True
    if category.parent_id is not None:
        return _is_food_category(category.parent_id)
    return False


def clean_numeric(value):
    if isinstance(value, str):
        # Remove anything that's not a digit or a dot
        cleaned = "".join(char for char in value if char.isdigit() or char == ".")
        return float(cleaned) if cleaned else None
    return value


@cli.command()
def process_nutritional_information():
    logger.info("Processing nutritional information for existing products")
    api_key = os.environ.get("GEMINI_API_KEY")
    assert api_key, "Please set the GEMINI_API_KEY environment variable"
    nutrition_extractor = NutritionFactsExtractor(api_key)

    engine = get_engine()
    with Session(engine) as session:
        products = session.exec(
            select(Product)
            .where(Product.nutritional_information == None)  # noqa: E711
            .options(joinedload(Product.category))
        ).all()
        for product in products:
            if (
                product.category
                and is_food_category(product.category)
                and product.images
            ):
                logger.info(f"Processing product '{product.name}' ({product.id})")
                last_image_url = product.images[-1].zoom_url
                try:
                    nutritional_info = nutrition_extractor.extract_nutrition_facts(
                        last_image_url
                    )
                    if nutritional_info:
                        nutritional_info["calories"] = nutritional_info.pop(
                            "calories_kcal"
                        )
                        # Clean numeric values
                        cleaned_info = {
                            key: clean_numeric(value)
                            for key, value in nutritional_info.items()
                        }
                        db_nutritional_info = NutritionalInformation(
                            product_id=product.id, **cleaned_info
                        )
                        session.add(db_nutritional_info)
                        session.commit()
                        logger.info(
                            f"Added nutritional information for product {product.id}"
                        )
                except Exception as e:
                    logger.error(
                        f"Error processing nutritional information for product {product.id}: {str(e)}"
                    )
            else:
                logger.debug(
                    f"Skipping product '{product.name}' ({product.id}), not a food product."
                )

    logger.info("Nutritional information processing completed")


if __name__ == "__main__":
    cli()
