import os
from celery import Celery

# Tell Celery which Django settings module to use
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_blog_app.settings')

app = Celery('ai_blog_app')

# Pull all CELERY_* settings from Django settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed Django apps (looks for tasks.py)
app.autodiscover_tasks()
