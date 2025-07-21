
"""Configuration module."""

import os
from pathlib import Path


class Config:
    """Application configuration."""
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    LOG_DIR = BASE_DIR / "logs"
    
    # Database settings
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    DB_NAME = os.getenv("DB_NAME", "myapp")
    
    # API settings
    API_KEY = os.getenv("API_KEY", "")
    API_TIMEOUT = 30
    
    @classmethod
    def get_db_url(cls):
        """Get database connection URL."""
        return f"postgresql://{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
