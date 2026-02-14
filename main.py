"""
BD | AS Platform - Main Application Entry Point
Professional microservices architecture for integration platform

Run with: uvicorn main:app --reload
"""
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

from app.api import auth_router, main_router
from app.api.routes.web import router as web_router
from app.services.sams_club.api.routes import router as sams_club_router
from app.services.leroy_merlin.api.routes import router as leroy_merlin_router
from app.services.sodimac.api.routes import router as sodimac_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Plataforma de Integração e Automação - BD | AS",
    version="2.0.0"
)

logger.info(f"🚀 Iniciando {settings.APP_NAME} v2.0.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# Include routers
app.include_router(auth_router, prefix="/api", tags=["Auth"])
app.include_router(main_router, tags=["API"])
app.include_router(sams_club_router, tags=["Sam's Club"])
app.include_router(leroy_merlin_router, tags=["Leroy Merlin"])
app.include_router(sodimac_router, tags=["Sodimac"])
app.include_router(web_router, tags=["Web"])

# Mount static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

# Mount exports directory (Excel downloads)
app.mount("/exports", StaticFiles(directory=settings.EXPORTS_DIR), name="exports")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
