"""Warehouse discovery and per-warehouse product availability tracking.

Mercadona serves a different catalog (and occasionally different prices)
depending on the warehouse that ships to the customer's postal code. The
``wh`` query parameter selects the warehouse on the public API, and the
postal code endpoint reveals the warehouse code for a postal code through
the ``x-customer-wh`` response header.

Availability is tracked with a current snapshot per (product, warehouse)
in ``productwarehousestatus`` and an append-only ``availabilityhistory``
log that only records changes.
"""

import asyncio
from datetime import datetime

import aiohttp
from loguru import logger
from sqlmodel import Session, select

from app.models import (
    AvailabilityHistory,
    Category,
    PriceHistory,
    Product,
    ProductWarehouseStatus,
    Warehouse,
)
from app.parser import BASE_URL, RateLimiter, build_product, fetch

POSTAL_CODE_URL = f"{BASE_URL}/postal-codes/actions/change-pc/"

# One representative postal code per Spanish province (01001 to 52001).
PROVINCE_POSTAL_CODES = [f"{i:02d}001" for i in range(1, 53)]


async def discover_warehouses(
    engine,
    max_requests_per_second: float = 2,
    postal_codes: list[str] | None = None,
) -> int:
    """Discover warehouse codes by probing one postal code per province.

    New warehouses are stored as active; existing ones keep their state.
    Returns the number of distinct warehouses discovered.
    """
    postal_codes = postal_codes or PROVINCE_POSTAL_CODES
    rate_limiter = RateLimiter(max_requests_per_second)
    semaphore = asyncio.Semaphore(20)
    discovered: dict[str, str] = {}

    async def probe(session: aiohttp.ClientSession, postal_code: str):
        async with semaphore:
            await rate_limiter.acquire()
            try:
                async with session.post(
                    POSTAL_CODE_URL, json={"new_postal_code": postal_code}
                ) as response:
                    return postal_code, response.headers.get("x-customer-wh")
            except aiohttp.ClientError as e:
                logger.warning(f"Postal code probe failed for {postal_code}: {e}")
                return postal_code, None

    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *(probe(session, postal_code) for postal_code in postal_codes)
        )
        for postal_code, warehouse_id in results:
            if warehouse_id:
                discovered.setdefault(warehouse_id, postal_code)

    with Session(engine) as db_session:
        for warehouse_id, postal_code in discovered.items():
            existing = db_session.get(Warehouse, warehouse_id)
            if existing is None:
                logger.info(
                    f"Discovered new warehouse {warehouse_id} "
                    f"(postal code {postal_code})"
                )
                db_session.add(Warehouse(id=warehouse_id, postal_code=postal_code))
        db_session.commit()

    logger.info(f"Warehouse discovery finished: {len(discovered)} warehouses")
    return len(discovered)


async def fetch_warehouse_catalog(
    session, rate_limiter, warehouse_id: str
) -> dict[str, dict]:
    """Fetch the full catalog of a warehouse from the category listings.

    Returns a mapping of product id to ``{"price": float, "category_id": int,
    "category_name": str}`` built from ~160 listing requests (instead of one
    request per product).
    """
    categories = await fetch(
        session, f"{BASE_URL}/categories/?wh={warehouse_id}", rate_limiter
    )
    if not categories:
        logger.error(f"Could not fetch categories for warehouse {warehouse_id}")
        return {}

    subcategory_ids = [
        subcategory["id"]
        for category in categories["results"]
        for subcategory in category.get("categories", [])
    ]

    async def fetch_subcategory(subcategory_id: int) -> dict | None:
        return await fetch(
            session,
            f"{BASE_URL}/categories/{subcategory_id}/?wh={warehouse_id}",
            rate_limiter,
        )

    catalog: dict[str, dict] = {}
    results = await asyncio.gather(
        *(fetch_subcategory(subcategory_id) for subcategory_id in subcategory_ids)
    )
    for subcategory_id, data in zip(subcategory_ids, results):
        if not data:
            continue
        for subcategory in data.get("categories", []):
            for product in subcategory.get("products", []):
                catalog[str(product["id"])] = {
                    "price": float(product["price_instructions"]["unit_price"]),
                    "category_id": subcategory_id,
                    "category_name": data.get("name", ""),
                }
    logger.info(f"Warehouse {warehouse_id}: {len(catalog)} products in catalog")
    return catalog


async def _add_missing_products(
    engine, session, warehouse_id: str, catalog: dict[str, dict], rate_limiter
) -> int:
    """Insert products that only exist in this warehouse's catalog."""
    with Session(engine) as db_session:
        known_ids = set(db_session.exec(select(Product.id)).all())
        known_categories = set(db_session.exec(select(Category.id)).all())

    missing_ids = [pid for pid in catalog if pid not in known_ids]
    added = 0
    for product_id in missing_ids:
        category_id = catalog[product_id]["category_id"]
        if category_id not in known_categories:
            logger.warning(
                f"Skipping product {product_id}: unknown category {category_id}"
            )
            continue
        details = await fetch(
            session,
            f"{BASE_URL}/products/{product_id}/?wh={warehouse_id}",
            rate_limiter,
        )
        if not details:
            continue
        product = build_product(details, category_id)
        with Session(engine) as db_session:
            logger.info(
                f"Adding product from warehouse {warehouse_id}: "
                f"({product.id}) {product.name}"
            )
            db_session.add(product)
            db_session.add(
                PriceHistory(
                    product_id=product.id,
                    price=product.price,
                    timestamp=datetime.now(),
                    warehouse_id=warehouse_id,
                )
            )
            db_session.commit()
            added += 1
    return added


def sync_warehouse_availability(
    engine, warehouse_id: str, catalog: dict[str, dict]
) -> dict[str, int]:
    """Update availability statuses and history for one warehouse.

    ``availabilityhistory`` only records changes; ``pricehistory`` records
    warehouse prices when they diverge from the main product price or change
    over time.
    """
    now = datetime.now()
    stats = {"appeared": 0, "disappeared": 0, "price_changes": 0}

    with Session(engine) as db_session:
        products = {
            product_id: price
            for product_id, price in db_session.exec(
                select(Product.id, Product.price)
            ).all()
        }
        statuses = {
            status.product_id: status
            for status in db_session.exec(
                select(ProductWarehouseStatus).where(
                    ProductWarehouseStatus.warehouse_id == warehouse_id
                )
            ).all()
        }

        for product_id, entry in catalog.items():
            if product_id not in products:
                continue  # product could not be inserted
            price = entry["price"]
            status = statuses.get(product_id)
            if status is None:
                db_session.add(
                    ProductWarehouseStatus(
                        product_id=product_id,
                        warehouse_id=warehouse_id,
                        available=True,
                        price=price,
                        first_seen=now,
                        last_seen=now,
                    )
                )
                db_session.add(
                    AvailabilityHistory(
                        product_id=product_id,
                        warehouse_id=warehouse_id,
                        available=True,
                        timestamp=now,
                    )
                )
                stats["appeared"] += 1
                if price != products[product_id]:
                    db_session.add(
                        PriceHistory(
                            product_id=product_id,
                            price=price,
                            timestamp=now,
                            warehouse_id=warehouse_id,
                        )
                    )
                    stats["price_changes"] += 1
            else:
                if not status.available:
                    status.available = True
                    db_session.add(
                        AvailabilityHistory(
                            product_id=product_id,
                            warehouse_id=warehouse_id,
                            available=True,
                            timestamp=now,
                        )
                    )
                    stats["appeared"] += 1
                if status.price != price:
                    db_session.add(
                        PriceHistory(
                            product_id=product_id,
                            price=price,
                            timestamp=now,
                            warehouse_id=warehouse_id,
                        )
                    )
                    stats["price_changes"] += 1
                    status.price = price
                status.last_seen = now
                db_session.add(status)

        for product_id, status in statuses.items():
            if product_id not in catalog and status.available:
                status.available = False
                db_session.add(status)
                db_session.add(
                    AvailabilityHistory(
                        product_id=product_id,
                        warehouse_id=warehouse_id,
                        available=False,
                        timestamp=now,
                    )
                )
                stats["disappeared"] += 1

        db_session.commit()

    logger.info(
        f"Warehouse {warehouse_id}: {stats['appeared']} appeared, "
        f"{stats['disappeared']} disappeared, {stats['price_changes']} price changes"
    )
    return stats


async def parse_availability(
    engine,
    max_requests_per_second: float,
    warehouse_ids: list[str] | None = None,
) -> None:
    """Track product availability for all active warehouses."""
    with Session(engine) as db_session:
        if warehouse_ids:
            warehouses = warehouse_ids
        else:
            warehouses = list(
                db_session.exec(
                    select(Warehouse.id).where(Warehouse.active == True)  # noqa: E712
                ).all()
            )
    if not warehouses:
        logger.warning(
            "No warehouses to track. Run 'discover-warehouses' first or pass "
            "warehouse ids explicitly."
        )
        return

    logger.info(f"Tracking availability for {len(warehouses)} warehouses")
    rate_limiter = RateLimiter(max_requests_per_second)
    async with aiohttp.ClientSession() as session:
        for warehouse_id in warehouses:
            catalog = await fetch_warehouse_catalog(session, rate_limiter, warehouse_id)
            if not catalog:
                logger.warning(
                    f"Empty catalog for warehouse {warehouse_id}, skipping sync "
                    "to avoid marking everything unavailable"
                )
                continue
            await _add_missing_products(
                engine, session, warehouse_id, catalog, rate_limiter
            )
            sync_warehouse_availability(engine, warehouse_id, catalog)

    logger.info("Availability tracking completed")
