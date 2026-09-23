@echo off
celery -A ai_blog_app worker --loglevel=info --pool=solo
