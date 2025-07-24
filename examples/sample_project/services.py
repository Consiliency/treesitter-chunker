"""Business logic services."""

from .config import Config
from .database import get_db
from .models import Profile, User


class UserService:
    """User-related business logic."""

    def __init__(self):
        self.db = get_db()

    def create_user(self, username, email, bio=None):
        """Create a new user with profile."""
        # Create user
        user = User(username=username, email=email)
        user.save()

        # Create profile
        if bio:
            profile = Profile(user_id=user.id, bio=bio)
            profile.save()

        return user

    def get_user_with_profile(self, user_id):
        """Get user with their profile."""
        user = User.find(user_id)
        if user:
            user.profile = user.get_profile()
        return user

    def update_user_email(self, user_id, new_email):
        """Update user email."""
        user = User.find(user_id)
        if user:
            user.email = new_email
            user.save()
        return user


class NotificationService:
    """Notification service."""

    def __init__(self):
        self.api_key = Config.API_KEY

    def send_email(self, user, subject, message):
        """Send email notification."""
        print(f"Sending email to {user.email}: {subject}")
        # Simulated email sending

    def notify_user_created(self, user):
        """Send notification for new user."""
        self.send_email(
            user,
            "Welcome!",
            f"Welcome to our app, {user.username}!",
        )
