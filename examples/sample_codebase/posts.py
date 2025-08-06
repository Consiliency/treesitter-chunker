from .base import BaseManager, BaseModel
from .users import UserManager


class Post(BaseModel):
    """Blog post model."""

    def __init__(self, id_, title, content, author_id):
        super().__init__(id_)
        self.title = title
        self.content = content
        self.author_id = author_id

    def get_author(self):
        """Get the post author."""
        user_manager = UserManager()
        return user_manager.find(self.author_id)

    def publish(self):
        """Publish the post."""
        self.save()
        author = self.get_author()
        author.send_email(f"Your post '{self.title}' has been published!")


class PostManager(BaseManager):
    """Manager for Post operations."""

    @staticmethod
    def __init__():
        super().__init__(Post)

    @classmethod
    def find_by_author(cls, author_id):
        """Find posts by author."""
        return [
            Post(1, "First Post", "Content 1", author_id),
            Post(2, "Second Post", "Content 2", author_id),
        ]

    @classmethod
    def get_recent_posts(cls, limit=10):
        """Get recent posts."""
        return [Post(i, f"Post {i}", f"Content {i}", 1) for i in range(limit)]
