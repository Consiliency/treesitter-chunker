
"""Main application module."""

from .services import UserService, NotificationService
from .config import Config


class Application:
    """Main application class."""
    
    def __init__(self):
        self.user_service = UserService()
        self.notification_service = NotificationService()
        self.config = Config()
        
    def register_user(self, username, email, bio=None):
        """Register a new user."""
        # Create user
        user = self.user_service.create_user(username, email, bio)
        
        # Send welcome notification
        self.notification_service.notify_user_created(user)
        
        return user
        
    def get_user_info(self, user_id):
        """Get complete user information."""
        return self.user_service.get_user_with_profile(user_id)
        

def main():
    """Run the application."""
    app = Application()
    
    # Register a user
    user = app.register_user(
        "john_doe",
        "john@example.com",
        "Software developer"
    )
    
    # Get user info
    user_info = app.get_user_info(user.id)
    print(f"User: {user_info.username} ({user_info.email})")


if __name__ == "__main__":
    main()
