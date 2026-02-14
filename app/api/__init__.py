"""
API module - Routes and endpoints for the platform.
"""


from .auth import router as auth_router
from .routes import router as main_router

__all__ = ["auth_router", "main_router"]

