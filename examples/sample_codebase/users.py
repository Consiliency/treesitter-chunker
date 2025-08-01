from .base import BaseManager, BaseModel


class User(BaseModel):
    """User model."""

    def __init__(self, id_, name, email):
        super().__init__(id_)
        self.name = name
        self.email = email

    def send_email(self, message):
        """Send email to user."""
        print(f"Sending email to {self.email}: {message}")


class UserManager(BaseManager):
    """Manager for User operations."""

    @staticmethod
    def __init__():
        super().__init__(User)

    @classmethod
    def find_by_email(cls, email):
        """Find user by email."""
        return User(1, "Test User", email)

    def authenticate(self, email, password):
        """Authenticate user."""
        user = self.find_by_email(email)
        return user if password == "password" else None
