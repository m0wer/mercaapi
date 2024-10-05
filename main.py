import asyncio
import os
import sys
import time

import click
from fastapi import FastAPI, Depends, Request, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from app.database import create_db_and_tables, get_session, engine
from app.parser import parse_mercadona
from app.models import Product, Category, NutritionalInformation
from app.vision.nutrition_facts import NutritionFactsExtractor
from app.models import ProductImage
from loguru import logger
from app.vision.ticket import TicketImageInformationExtractor

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


@api_router.on_event("startup")
def on_startup():
    create_db_and_tables()


@api_router.get("/products")
def get_products(
    skip: int = 0, limit: int = 100, session: Session = Depends(get_session)
):
    products = session.exec(select(Product).offset(skip).limit(limit)).all()
    return products


@api_router.get("/products/{product_id}")
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
        **product.dict(),
        "nutritional_information": product.nutritional_information.dict(exclude={"id"})
        if product.nutritional_information is not None
        else None,
        "images": [
            image.dict(exclude={"id", "product_id"}) for image in product.images
        ],
    }


@api_router.get("/categories")
def get_categories(
    skip: int = 0, limit: int = 100, session: Session = Depends(get_session)
):
    categories = session.exec(select(Category).offset(skip).limit(limit)).all()
    return categories


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
    asyncio.run(
        parse_mercadona(max_requests, skip_existing_products=not update_existing)
    )
    logger.info("Parsing completed")


def is_food_category(category_id: str) -> bool:
    # TODO
    return True


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

    with Session(engine) as session:
        products = session.exec(
            select(Product).where(Product.nutritional_information == None)  # noqa: E711
        ).all()
        for product in products:
            if is_food_category(product.category_id) and product.images:
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


@api_router.post("/ticket")
async def process_ticket(file: UploadFile = File(...)):
    """
    Handle POST requests to /ticket endpoint.
    Accepts an image or PDF file, extracts ticket information, and returns it.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured")

    extractor = TicketImageInformationExtractor(api_key=api_key)
    file_data = await file.read()
    mime_type = file.content_type

    try:
        extract_info = extractor.extract_ticket_info(file_data, mime_type)
    except Exception as e:
        logger.error(f"Error extracting ticket information: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to extract ticket information"
        )
    return extract_info


if __name__ == "__main__":
    cli()
