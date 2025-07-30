"""Data models module."""

from .database import get_db


class Model:
    """Base model class."""

    table_name = None

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def save(self):
        """Save model to database."""
        db = get_db()
        query = f"INSERT INTO {self.table_name} ..."
        db.execute(query)

    @classmethod
    def find(cls, id_):
        """Find model by ID."""
        db = get_db()
        query = f"SELECT * FROM {cls.table_name} WHERE id_ = {id_}"
        result = db.execute(query)
        return cls(**result[0]) if result else None


class User(Model):
    """User model."""

    table_name = "users"

    def __init__(self, id_=None, username=None, email=None):
        super().__init__(id_=id_, username=username, email=email)

    def get_profile(self):
        """Get user profile."""
        return Profile.find_by_user(self.id_)


class Profile(Model):
    """User profile model."""

    table_name = "profiles"

    def __init__(self, id_=None, user_id=None, bio=None):
        super().__init__(id_=id_, user_id=user_id, bio=bio)

    @classmethod
    def find_by_user(cls, user_id):
        """Find profile by user ID."""
        db = get_db()
        query = f"SELECT * FROM {cls.table_name} WHERE user_id = {user_id}"
        result = db.execute(query)
        return cls(**result[0]) if result else None
