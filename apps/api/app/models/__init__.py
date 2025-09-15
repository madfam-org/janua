"""
Models package for Plinto API

This package contains all database models for the application.
The main models are defined in the parent models.py file.
Sub-models are organized by domain in separate files.
"""

# Import only the main models from parent models.py to avoid circular dependencies
from ..models import *

# Domain-specific models can be imported directly from their files when needed
# e.g., from app.models.sso import SSOConfiguration