from celery import Celery
import os

celery_app = Celery("mercaapi")
celery_app.conf.update(
    broker_url=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_routes={
        "app.worker.find_closest_products_with_preload": {"queue": "high"},
    },
)
