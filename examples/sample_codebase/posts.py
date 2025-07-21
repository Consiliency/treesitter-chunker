
from .base import BaseModel, BaseManager
from .users import User, UserManager


class Post(BaseModel):
    """Blog post model."""
    def __init__(self, id, title, content, author_id):
        super().__init__(id)
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
    def __init__(self):
        super().__init__(Post)
        
    def find_by_author(self, author_id):
        """Find posts by author."""
        # Simplified implementation
        return [
            Post(1, "First Post", "Content 1", author_id),
            Post(2, "Second Post", "Content 2", author_id)
        ]
        
    def get_recent_posts(self, limit=10):
        """Get recent posts."""
        # Simplified implementation
        return [Post(i, f"Post {i}", f"Content {i}", 1) for i in range(limit)]
