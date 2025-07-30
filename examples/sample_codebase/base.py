class BaseModel:
    """Base model for all entities."""

    def __init__(self, id_):
        self.id_ = id_

    def save(self):
        """Save the model."""
        print(f"Saving {self.__class__.__name__} with id_ {self.id_}")

    def delete(self):
        """Delete the model."""
        print(f"Deleting {self.__class__.__name__} with id_ {self.id_}")


class BaseManager:
    """Base manager for model operations."""

    def __init__(self, model_class):
        self.model_class = model_class

    def create(self, **kwargs):
        """Create a new instance."""
        return self.model_class(**kwargs)

    def find(self, id_):
        """Find instance by id_."""
        return self.model_class(id_)
