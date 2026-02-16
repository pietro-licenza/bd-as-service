"""
BD | AS Platform - Main Application Entry Point
Professional microservices architecture for integration platform

Run with: uvicorn main:app --reload
"""
import logging
import os
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

# --- AJUSTE PARA PRODUÇÃO: CRIAÇÃO DE DIRETÓRIOS ---
# Garante que as pastas existam antes do app tentar montá-las
for directory in [settings.STATIC_DIR, settings.EXPORTS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.info(f"📁 Pasta criada: {directory}")

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
# Usamos str() para garantir compatibilidade do Path com o Starlette
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# Mount exports directory (Excel downloads)
app.mount("/exports", StaticFiles(directory=str(settings.EXPORTS_DIR)), name="exports")

if __name__ == "__main__":
    import uvicorn
    # Em produção, o Cloud Run usa a variável de ambiente PORT
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False, # Desativar reload em produção por performance
        log_level="info"
    )