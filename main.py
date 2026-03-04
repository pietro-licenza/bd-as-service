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

# IMPORTAÇÕES DO BANCO PARA CRIAÇÃO DE TABELAS
from app.core.database import engine, Base
# Importar entities garante que o SQLAlchemy "enxergue" a classe Order e MLCredential
from app.models import entities 

from app.api import auth_router, main_router
from app.api.routes.web import router as web_router
from app.services.sams_club.api.routes import router as sams_club_router
from app.services.leroy_merlin.api.routes import router as leroy_merlin_router
from app.services.sodimac.api.routes import router as sodimac_router
from app.api.dashboard import router as dashboard_router
from app.services.mercado_livre.api.routes import router as ml_webhook_router
from app.services.magalu.api.routes import router as magalu_router
from app.services.casas_bahia.api.routes import router as cb_router
from app.services.decathlon.api.routes import router as decathlon_router
from app.api.routes import monitoring

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- CRIAÇÃO AUTOMÁTICA DE TABELAS ---
# O SQLAlchemy percorre os modelos carregados e cria as tabelas unificadas
try:
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Tabelas unificadas (incluindo 'orders') verificadas no banco.")
except Exception as e:
    logger.error(f"❌ Erro ao sincronizar tabelas: {e}")

# --- CRIAÇÃO DE DIRETÓRIOS ---
for directory in [settings.STATIC_DIR, settings.EXPORTS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.info(f"📁 Pasta garantida: {directory}")

# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Plataforma de Integração e Automação - BD | AS",
    version="2.0.0"
)

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
app.include_router(dashboard_router, tags=["Dashboard"])
app.include_router(sams_club_router, tags=["Sam's Club"])
app.include_router(leroy_merlin_router, tags=["Leroy Merlin"])
app.include_router(sodimac_router, tags=["Sodimac"])
app.include_router(decathlon_router, tags=["Decathlon"])
app.include_router(ml_webhook_router, tags=["Mercado Livre Webhook"])
app.include_router(magalu_router, tags=["Magalu Webhook"])
app.include_router(cb_router, tags=["Casas Bahia Webhook"])
app.include_router(web_router, tags=["Web"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["Monitoring"])
# Mount static files
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")
app.mount("/exports", StaticFiles(directory=str(settings.EXPORTS_DIR)), name="exports")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False, 
        log_level="info"
    )