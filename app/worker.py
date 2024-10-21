from loguru import logger

from app.celery_config import celery_app
from app.database import get_session
from app.models import WrongMatchReport, WrongNutritionReport
from app.shared.cache import get_all_products
from app.shared.product_matcher import find_closest_products_task

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


@celery_app.task(
    default_retry_delay=30,
    max_retries=5,
)
def process_wrong_match_report(
    original_name: str, original_price: float, wrong_match_id: str
):
    try:
        with next(get_session()) as session:
            report = WrongMatchReport(
                original_name=original_name,
                original_price=original_price,
                wrong_match_id=wrong_match_id,
            )
            session.add(report)
            session.commit()
            logger.info(f"Saved wrong match report for product {wrong_match_id}")
    except Exception as e:
        logger.error(f"Error saving wrong match report: {str(e)}")
        raise


@celery_app.task(
    default_retry_delay=30,
    max_retries=5,
)
def process_wrong_nutrition_report(product_id: str, nutrition_id: int):
    try:
        with next(get_session()) as session:
            report = WrongNutritionReport(
                product_id=product_id, nutrition_id=nutrition_id
            )
            session.add(report)
            session.commit()
            logger.info(f"Saved wrong nutrition report for product {product_id}")
    except Exception as e:
        logger.error(f"Error saving wrong nutrition report: {str(e)}")
        raise
