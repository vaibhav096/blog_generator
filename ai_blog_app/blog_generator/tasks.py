import logging
from celery import shared_task
from .models import BlogPost

logger = logging.getLogger('blog_generator')


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def generate_blog_task(self, blog_id: int):
    """
    Celery task that runs in the background.

    Steps:
      1. Mark the BlogPost as 'processing'
      2. Fetch the YouTube transcript
      3. Call Gemini to generate blog content
      4. Save content + mark 'completed'
      If anything fails → mark 'failed' with an error message

    bind=True    → gives access to `self` (the task instance) so we can retry
    max_retries=2 → auto-retry up to 2 times on unexpected errors
    """
    # Import here to avoid circular imports (views imports tasks, tasks imports views helpers)
    from .views import fetch_transcript, generate_blog_from_transcription, format_blog_content

    try:
        blog = BlogPost.objects.get(id=blog_id)
    except BlogPost.DoesNotExist:
        logger.error(f"generate_blog_task: BlogPost {blog_id} not found")
        return

    try:
        # ── Step 1: Mark as processing ────────────────────────────────────
        blog.status = BlogPost.STATUS_PROCESSING
        blog.save(update_fields=['status'])

        # ── Step 2: Fetch transcript ──────────────────────────────────────
        video_id = _extract_video_id(blog.youtube_link)
        transcription = fetch_transcript(video_id)
        if not transcription:
            raise ValueError("Could not fetch transcript for this video.")

        # ── Step 3: Generate blog via Gemini ──────────────────────────────
        raw_content = generate_blog_from_transcription(transcription)
        html_content = format_blog_content(raw_content)

        # ── Step 4: Save and mark completed ──────────────────────────────
        blog.generated_content = html_content
        blog.status = BlogPost.STATUS_COMPLETED
        blog.error_message = ''
        blog.save(update_fields=['generated_content', 'status', 'error_message'])

        logger.info(f"generate_blog_task: blog {blog_id} completed successfully")

    except Exception as exc:
        logger.exception(f"generate_blog_task: blog {blog_id} failed — {exc}")

        # Retry on unexpected errors (network blips, API timeouts, etc.)
        # ValueError (bad transcript) is not worth retrying
        if not isinstance(exc, ValueError) and self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        # Final failure — save error message so frontend can show it
        blog.status = BlogPost.STATUS_FAILED
        blog.error_message = str(exc)
        blog.save(update_fields=['status', 'error_message'])


def _extract_video_id(url: str) -> str:
    """Re-use the same URL parsing logic without importing the full views module."""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    hostname = parsed.hostname.lower() if parsed.hostname else ''
    path = parsed.path

    if 'youtu.be' in hostname:
        return path[1:] if len(path) > 1 else None
    if 'youtube.com' in hostname:
        if path == '/watch':
            return parse_qs(parsed.query).get('v', [None])[0]
        elif path.startswith('/embed/') or path.startswith('/v/'):
            parts = path.split('/')
            return parts[2] if len(parts) > 2 else None
    return None
