"""Business logic services."""

from .config import Config
from .database import get_db
from .models import Profile, User


class UserService:
    """User-related business logic."""

    def __init__(self):
        self.db = get_db()

    @classmethod
    def create_user(cls, username, email, bio=None):
        """Create a new user with profile."""
        user = User(username=username, email=email)
        user.save()
        if bio:
            profile = Profile(user_id=user.id, bio=bio)
            profile.save()
        return user

    @staticmethod
    def get_user_with_profile(user_id):
        """Get user with their profile."""
        user = User.find(user_id)
        if user:
            user.profile = user.get_profile()
        return user

    @staticmethod
    def update_user_email(user_id, new_email):
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

    @staticmethod
    def send_email(user, subject, _message):
        """Send email notification."""
        print(f"Sending email to {user.email}: {subject}")

    def notify_user_created(self, user):
        """Send notification for new user."""
        self.send_email(user, "Welcome!", f"Welcome to our app, {user.username}!")
