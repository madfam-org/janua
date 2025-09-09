"""
Plinto Core API - Entry Point

This module imports and exposes the FastAPI app from the app module.
"""

from app.main import app

__all__ = ["app"]