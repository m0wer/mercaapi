import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

import click
from loguru import logger
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload

from app.database import get_engine
from app.parser import parse_mercadona
from app.warehouses import discover_warehouses, parse_availability
from app.models import Product, NutritionalInformation, is_food_category
from app.ai.nutrition import NutritionAI, is_plausible_nutrition, MACRO_FIELDS


@click.group()
def cli():
    pass


@cli.command()
@click.option("--max-requests", default=5, help="Maximum requests per second")
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


@cli.command("discover-warehouses")
@click.option("--max-requests", default=2, help="Maximum requests per second")
def discover_warehouses_cmd(max_requests):
    """Discover Mercadona warehouses by probing one postal code per province."""
    logger.info("Discovering warehouses")
    engine = get_engine()
    count = asyncio.run(discover_warehouses(engine, max_requests))
    logger.info(f"Discovery completed: {count} warehouses known")


@cli.command("parse-availability")
@click.option("--max-requests", default=5, help="Maximum requests per second")
@click.option(
    "--warehouses",
    default="",
    help="Comma-separated warehouse ids (default: all active warehouses)",
)
def parse_availability_cmd(max_requests, warehouses):
    """Track per-warehouse product availability and prices."""
    logger.info("Starting availability tracking")
    engine = get_engine()
    warehouse_ids = [wh.strip() for wh in warehouses.split(",") if wh.strip()] or None
    asyncio.run(parse_availability(engine, max_requests, warehouse_ids))
    logger.info("Availability tracking completed")


def _load_products_missing_nutrition(session: Session) -> list[Product]:
    """Food products without nutritional information or without calories."""
    products = (
        session.exec(
            select(Product).options(
                joinedload(Product.category),  # type: ignore[arg-type]
                joinedload(Product.images),  # type: ignore[arg-type]
                joinedload(Product.nutritional_information),  # type: ignore[arg-type]
            )
        )
        .unique()
        .all()
    )
    return [
        product
        for product in products
        if product.category
        and is_food_category(product.category)
        and (
            product.nutritional_information is None
            or product.nutritional_information.calories is None
        )
    ]


def _save_nutrition(
    session: Session, product: Product, values: dict[str, float | None]
) -> None:
    existing = session.exec(
        select(NutritionalInformation).where(
            NutritionalInformation.product_id == product.id
        )
    ).first()
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
    else:
        session.add(NutritionalInformation(product_id=product.id, **values))
    session.commit()


def _process_products_nutrition(
    engine, products: list[Product], workers: int
) -> tuple[int, int]:
    """Fetch nutrition for products concurrently, write results sequentially."""
    if not products:
        logger.info("No products to process")
        return 0, 0

    nutrition_ai = NutritionAI()
    processed = 0
    failed = 0

    with (
        ThreadPoolExecutor(max_workers=workers) as executor,
        Session(engine) as session,
    ):
        futures = {
            executor.submit(nutrition_ai.get_nutrition_for_product, product): product
            for product in products
        }
        for future in as_completed(futures):
            product = futures[future]
            try:
                values = future.result()
            except Exception as e:
                logger.error(f"Error processing product {product.id}: {e}")
                failed += 1
                continue
            if values is None:
                logger.warning(f"No nutrition obtained for product {product.id}")
                failed += 1
                continue
            _save_nutrition(session, product, values)
            processed += 1
            logger.info(
                f"Saved nutrition for product '{product.name}' ({product.id}) "
                f"[{processed + failed}/{len(products)}]"
            )

    logger.info(f"Nutrition processing done: {processed} saved, {failed} failed")
    return processed, failed


@cli.command()
@click.option("--workers", default=4, help="Concurrent AI requests")
@click.option("--limit", default=0, help="Maximum products to process (0 = all)")
def process_nutritional_information(workers, limit):
    """Add nutritional information to food products that are missing it."""
    logger.info("Processing nutritional information for products")
    engine = get_engine()
    with Session(engine) as session:
        products = _load_products_missing_nutrition(session)
    logger.info(f"{len(products)} food products missing nutritional information")
    if limit:
        products = products[:limit]
    _process_products_nutrition(engine, products, workers)


@cli.command()
@click.option("--workers", default=4, help="Concurrent AI requests")
@click.option(
    "--dry-run", is_flag=True, help="Only report invalid rows, do not reprocess"
)
def clean_nutrition(workers, dry_run):
    """Find implausible nutritional values and reprocess them with AI."""
    engine = get_engine()
    with Session(engine) as session:
        rows = (
            session.exec(
                select(Product)
                .join(NutritionalInformation)
                .options(
                    joinedload(Product.category),  # type: ignore[arg-type]
                    joinedload(Product.images),  # type: ignore[arg-type]
                    joinedload(Product.nutritional_information),  # type: ignore[arg-type]
                )
            )
            .unique()
            .all()
        )
        invalid_products = []
        for product in rows:
            info = product.nutritional_information
            if info is None:
                continue
            values = {"calories": info.calories}
            values.update({field: getattr(info, field) for field in MACRO_FIELDS})
            if not is_plausible_nutrition(values):
                logger.warning(
                    f"Implausible nutrition for product '{product.name}' "
                    f"({product.id}): {values}"
                )
                invalid_products.append(product)

    logger.info(f"Found {len(invalid_products)} products with implausible nutrition")
    if not dry_run and invalid_products:
        _process_products_nutrition(engine, invalid_products, workers)


@cli.command()
@click.option("--max-requests", default=5, help="Maximum requests per second")
@click.option("--workers", default=4, help="Concurrent AI requests")
@click.pass_context
def update(ctx, max_requests, workers):
    """Full database update: parse products and prices, then fix nutrition.

    Designed to be run periodically (e.g. from cron).
    """
    logger.info("Starting full database update")
    ctx.invoke(parse, max_requests=max_requests, update_existing=True)
    ctx.invoke(discover_warehouses_cmd, max_requests=2)
    ctx.invoke(parse_availability_cmd, max_requests=max_requests, warehouses="")
    ctx.invoke(process_nutritional_information, workers=workers, limit=0)
    ctx.invoke(clean_nutrition, workers=workers, dry_run=False)
    logger.info("Full database update completed")


if __name__ == "__main__":
    cli()
