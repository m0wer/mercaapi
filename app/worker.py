# app/worker.py
from app.celery_config import celery_app
from app.database import get_session
from app.shared.cache import get_all_products
from app.shared.product_matcher import find_closest_products_task
from loguru import logger

products = []


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        3600.0, reload_products.s(), name="reload products every hour"
    )


@celery_app.task
def reload_products():
    global products
    products = get_all_products(next(get_session()))
    logger.info(f"Reloaded {len(products)} products for matching")


# Preload products when worker starts
products = get_all_products(next(get_session()))
logger.info(f"Preloaded {len(products)} products for matching")


@celery_app.task
def find_closest_products_with_preload(*args, **kwargs):
    return [
        result.model_dump()
        for result in find_closest_products_task(products, *args, **kwargs)
    ]
