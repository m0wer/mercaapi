import asyncio
import os

import click
from loguru import logger
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload

from app.database import get_engine
from app.parser import parse_mercadona
from app.models import Product, NutritionalInformation, is_food_category
from app.ai.nutrition_facts import NutritionFactsExtractor
from app.ai.nutrition_estimator import estimate_nutritional_info


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


def clean_numeric(value):
    if isinstance(value, str):
        cleaned = "".join(char for char in value if char.isdigit() or char == ".")
        return float(cleaned) if cleaned else None
    return value


@cli.command()
@click.option(
    "--reprocess-all",
    is_flag=True,
    help="Reprocess all products with missing or null calorie information",
)
def process_nutritional_information(reprocess_all):
    logger.info("Processing nutritional information for products")
    api_key = os.environ.get("GEMINI_API_KEY")
    assert api_key, "Please set the GEMINI_API_KEY environment variable"
    nutrition_extractor = NutritionFactsExtractor(api_key)

    engine = get_engine()
    with Session(engine) as session:
        query = select(Product).options(
            joinedload(Product.category), joinedload(Product.images)
        )
        if not reprocess_all:
            query = query.where(Product.nutritional_information == None)  # noqa: E711
        else:
            query = query.outerjoin(NutritionalInformation).where(
                (NutritionalInformation.id == None)  # noqa: E711
                | (NutritionalInformation.calories == None)  # noqa: E711
            )

        products = session.exec(query).unique()

        for product in products:
            if product.category and is_food_category(product.category):
                logger.info(f"Processing product '{product.name}' ({product.id})")
                nutritional_info = None

                if product.images:
                    for image in reversed(product.images):
                        try:
                            nutritional_info = (
                                nutrition_extractor.extract_nutrition_facts(
                                    image.zoom_url
                                )
                            )
                            if (
                                nutritional_info is not None
                                and nutritional_info["calories_kcal"] is not None
                            ):
                                break
                        except Exception as e:
                            logger.error(
                                f"Error processing image for product {product.id}: {str(e)}"
                            )

                if (
                    nutritional_info is None
                    or nutritional_info["calories_kcal"] is None
                ):
                    logger.warning(
                        f"No nutritional information found in images for product {product.id}. Estimating using LLM."
                    )
                    nutritional_info = estimate_nutritional_info(product)

                if nutritional_info:
                    nutritional_info["calories"] = nutritional_info.pop(
                        "calories_kcal", None
                    )
                    del nutritional_info["calories_kJ"]
                    cleaned_info = {
                        key: clean_numeric(value)
                        for key, value in nutritional_info.items()
                    }

                    existing_info = product.nutritional_information
                    if existing_info:
                        for key, value in cleaned_info.items():
                            setattr(existing_info, key, value)
                    else:
                        db_nutritional_info = NutritionalInformation(
                            product_id=product.id, **cleaned_info
                        )
                        session.add(db_nutritional_info)

                    session.commit()
                    logger.info(
                        f"Added/Updated nutritional information for product {product.id}"
                    )
            else:
                logger.warning(
                    f"Skipping product '{product.name}' ({product.id}), not a food product."
                )

    logger.info("Nutritional information processing completed")


if __name__ == "__main__":
    cli()
