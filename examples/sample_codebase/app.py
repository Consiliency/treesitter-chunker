
from .users import UserManager
from .posts import PostManager


class BlogApp:
    """Main blog application."""
    def __init__(self):
        self.user_manager = UserManager()
        self.post_manager = PostManager()
        
    def create_post(self, user_email, password, title, content):
        """Create a new blog post."""
        # Authenticate user
        user = self.user_manager.authenticate(user_email, password)
        if not user:
            raise ValueError("Authentication failed")
            
        # Create post
        post = self.post_manager.create(
            id=None,
            title=title,
            content=content,
            author_id=user.id
        )
        
        # Publish it
        post.publish()
        return post
        
    def get_user_posts(self, user_id):
        """Get all posts by a user."""
        return self.post_manager.find_by_author(user_id)
        

def main():
    """Run the blog application."""
    app = BlogApp()
    
    # Create a post
    post = app.create_post(
        "user@example.com",
        "password",
        "Hello World",
        "This is my first blog post!"
    )
    
    # Get user's posts
    posts = app.get_user_posts(1)
    for p in posts:
        print(f"- {p.title}")


if __name__ == "__main__":
    main()
