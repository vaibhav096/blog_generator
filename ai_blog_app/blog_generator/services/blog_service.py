"""
Blog service for handling blog-related operations.

This module provides services for:
- Creating blog posts
- Retrieving blog posts
- Updating blog posts
- Deleting blog posts
- User authorization checks
"""

import logging
from typing import Optional, List
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

from ..models import BlogPost
from ..constants import ERROR_MESSAGES, SUCCESS_MESSAGES

logger = logging.getLogger(__name__)


class BlogService:
    """Service class for blog post operations."""

    @staticmethod
    def create_blog_post(
        user: User,
        youtube_title: str,
        youtube_link: str,
        generated_content: str
    ) -> BlogPost:
        """
        Create a new blog post.

        Args:
            user: The user creating the blog post
            youtube_title: User-provided title for the blog
            youtube_link: YouTube video URL
            generated_content: AI-generated blog content (HTML)

        Returns:
            Created BlogPost instance

        Raises:
            ValueError: If required fields are missing
        """
        if not user:
            raise ValueError("User is required")

        if not youtube_title or not youtube_link or not generated_content:
            raise ValueError("All fields (title, link, content) are required")

        try:
            blog_post = BlogPost.objects.create(
                user=user,
                youtube_title=youtube_title,
                youtube_link=youtube_link,
                generated_content=generated_content
            )

            logger.info(
                f"Created blog post {blog_post.id} for user {user.username}: "
                f"{youtube_title}"
            )
            return blog_post

        except Exception as e:
            logger.error(f"Error creating blog post: {e}")
            raise

    @staticmethod
    def get_user_blogs(user: User) -> List[BlogPost]:
        """
        Retrieve all blog posts for a specific user.

        Args:
            user: The user whose blogs to retrieve

        Returns:
            QuerySet of BlogPost objects ordered by creation date (newest first)
        """
        if not user or not user.is_authenticated:
            logger.warning("Attempted to get blogs for unauthenticated user")
            return BlogPost.objects.none()

        blogs = BlogPost.objects.filter(user=user).order_by('-created_at')
        logger.info(f"Retrieved {blogs.count()} blogs for user {user.username}")
        return blogs

    @staticmethod
    def get_blog_by_id(blog_id: int, user: Optional[User] = None) -> Optional[BlogPost]:
        """
        Retrieve a specific blog post by ID.

        Args:
            blog_id: The ID of the blog post
            user: Optional user to check ownership

        Returns:
            BlogPost instance if found, None otherwise

        Raises:
            PermissionDenied: If user provided but doesn't own the blog
        """
        try:
            blog = BlogPost.objects.get(id=blog_id)

            # Check ownership if user is provided
            if user and blog.user != user:
                logger.warning(
                    f"User {user.username} attempted to access blog {blog_id} "
                    f"owned by {blog.user.username}"
                )
                raise PermissionDenied(ERROR_MESSAGES['UNAUTHORIZED'])

            return blog

        except BlogPost.DoesNotExist:
            logger.warning(f"Blog post {blog_id} not found")
            return None

    @staticmethod
    def delete_blog(blog_id: int, user: User) -> bool:
        """
        Delete a blog post.

        Args:
            blog_id: The ID of the blog post to delete
            user: The user attempting to delete the blog

        Returns:
            True if deleted successfully

        Raises:
            PermissionDenied: If user doesn't own the blog
            ValueError: If blog not found
        """
        if not user or not user.is_authenticated:
            raise PermissionDenied(ERROR_MESSAGES['UNAUTHORIZED'])

        try:
            blog = BlogPost.objects.get(id=blog_id)

            if blog.user != user:
                logger.warning(
                    f"User {user.username} attempted to delete blog {blog_id} "
                    f"owned by {blog.user.username}"
                )
                raise PermissionDenied(ERROR_MESSAGES['UNAUTHORIZED'])

            blog_title = blog.youtube_title
            blog.delete()

            logger.info(
                f"User {user.username} deleted blog {blog_id}: {blog_title}"
            )
            return True

        except BlogPost.DoesNotExist:
            logger.error(f"Attempted to delete non-existent blog {blog_id}")
            raise ValueError(ERROR_MESSAGES['NOT_FOUND'])

    @staticmethod
    def get_blog_count(user: User) -> int:
        """
        Get the total number of blogs for a user.

        Args:
            user: The user to count blogs for

        Returns:
            Number of blog posts
        """
        if not user or not user.is_authenticated:
            return 0

        count = BlogPost.objects.filter(user=user).count()
        return count

    @staticmethod
    def search_blogs(user: User, query: str) -> List[BlogPost]:
        """
        Search user's blogs by title or content.

        Args:
            user: The user whose blogs to search
            query: Search query string

        Returns:
            QuerySet of matching BlogPost objects
        """
        if not user or not user.is_authenticated or not query:
            return BlogPost.objects.none()

        blogs = BlogPost.objects.filter(
            user=user
        ).filter(
            youtube_title__icontains=query
        ) | BlogPost.objects.filter(
            user=user
        ).filter(
            generated_content__icontains=query
        )

        logger.info(
            f"Search '{query}' for user {user.username} "
            f"returned {blogs.count()} results"
        )
        return blogs.distinct().order_by('-created_at')
