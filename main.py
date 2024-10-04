import asyncio
import sys
import time

import click
from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from app.database import create_db_and_tables, get_session
from app.parser import parse_mercadona
from app.models import Product, Category
from loguru import logger

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
    product = session.exec(select(Product).where(Product.id == product_id)).first()
    if not product:
        return {"error": "Product not found"}
    return product


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


@click.command()
@click.option("--max-requests", default=60, help="Maximum requests per minute")
@click.option("--update-existing", is_flag=True, help="Update existing products")
def main(max_requests, update_existing):
    """
    Main function to run the application.
    """
    logger.info("Starting the Mercadona parser")
    asyncio.run(
        parse_mercadona(max_requests, skip_existing_products=not update_existing)
    )
    logger.info("Parsing completed")


if __name__ == "__main__":
    main()
