
class BaseModel:
    """Base model for all entities."""
    def __init__(self, id):
        self.id = id
        
    def save(self):
        """Save the model."""
        print(f"Saving {self.__class__.__name__} with id {self.id}")
        
    def delete(self):
        """Delete the model."""
        print(f"Deleting {self.__class__.__name__} with id {self.id}")


class BaseManager:
    """Base manager for model operations."""
    def __init__(self, model_class):
        self.model_class = model_class
        
    def create(self, **kwargs):
        """Create a new instance."""
        return self.model_class(**kwargs)
        
    def find(self, id):
        """Find instance by id."""
        return self.model_class(id)
