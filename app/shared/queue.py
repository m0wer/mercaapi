from celery import Celery
from loguru import logger
import os

celery_app = Celery("mercaapi")
celery_app.conf.update(
    broker_url=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
)


def enqueue_high_priority(func, *args, **kwargs):
    logger.info(f"Enqueueing high priority task: {func.__name__}")
    task = celery_app.send_task(
        "app.worker.find_closest_products", args=args, kwargs=kwargs, queue="high"
    )
    return task
