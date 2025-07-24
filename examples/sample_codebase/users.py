from .base import BaseManager, BaseModel


class User(BaseModel):
    """User model."""

    def __init__(self, id, name, email):
        super().__init__(id)
        self.name = name
        self.email = email

    def send_email(self, message):
        """Send email to user."""
        print(f"Sending email to {self.email}: {message}")


class UserManager(BaseManager):
    """Manager for User operations."""

    def __init__(self):
        super().__init__(User)

    def find_by_email(self, email):
        """Find user by email."""
        # Simplified implementation
        return User(1, "Test User", email)

    def authenticate(self, email, password):
        """Authenticate user."""
        user = self.find_by_email(email)
        # Simplified auth
        return user if password == "password" else None
