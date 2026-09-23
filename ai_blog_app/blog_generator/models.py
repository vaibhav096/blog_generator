from django.db import models

from django.contrib.auth.models import User

# Create your models here.

class BlogPost(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blogs')
    youtube_title = models.CharField(max_length=300)
    youtube_link = models.URLField()
    generated_content = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user_id']),  # For filtering posts by user
            models.Index(fields=['-created_at']),  # For sorting by newest first
            models.Index(fields=['user_id', '-created_at']),  # For user's recent posts
        ]
        ordering = ['-created_at']  # Default ordering by newest first

    def __str__(self):
        return self.youtube_title