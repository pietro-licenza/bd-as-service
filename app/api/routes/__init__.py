"""
Health check and monitoring endpoints
"""
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@router.get("/")
async def api_root():
    """API root endpoint"""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/health"
    }
