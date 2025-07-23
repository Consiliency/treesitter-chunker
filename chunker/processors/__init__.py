"""Specialized processors for different file types."""

from .base import SpecializedProcessor
from .config import ConfigProcessor

__all__ = ['SpecializedProcessor', 'ConfigProcessor']