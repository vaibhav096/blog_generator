# This makes Celery start automatically when Django starts.
# Without this, scheduled/async tasks won't be registered properly.
from .celery import app as celery_app

__all__ = ('celery_app',)
