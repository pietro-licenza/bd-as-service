"""
Core configuration for BD | AS Platform
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "BD | AS Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STATIC_DIR: Path = BASE_DIR / "static"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    EXPORTS_DIR: Path = BASE_DIR / "exports"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:8000", "http://127.0.0.1:8000", "*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]
    
    # Google Cloud
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "")
    
    # Gemini API
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "AIzaSyCtBzhyDgY-l8pTqTm2FURrZVsdjQyd5BA")
    GEMINI_MODEL_TEXT: str = "models/gemini-2.5-flash-lite"
    GEMINI_MODEL_MULTIMODAL: str = "models/gemini-2.5-flash-image"
    GEMINI_ENDPOINT: str = "https://api.gemini.com/v1/process"
    
    # GCP Config
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "gen-lang-client-0481115304")
    GCP_LOCATION: str = os.getenv("GCP_LOCATION", "us-central1")
    GCP_STORAGE_BUCKET: str = os.getenv("GCP_STORAGE_BUCKET", "bd-image-parser-products")
    GCP_SERVICE_ACCOUNT_KEY_PATH: str = os.getenv("GCP_SERVICE_ACCOUNT_KEY_PATH", "bd_image_parser_service_account.json")
    GCP_SERVICE_ACCOUNT_JSON: str = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "")
    GCP_SERVICE_ACCOUNT_SECRET_NAME: str = os.getenv("GCP_SERVICE_ACCOUNT_SECRET_NAME", "bd-image-parser-sa-key")
    GCP_USE_SECRET_MANAGER: bool = os.getenv("GCP_USE_SECRET_MANAGER", "false").lower() == "true"
    
    # Mercado Livre
    ML_CLIENT_ID: str = os.getenv("ML_CLIENT_ID")
    ML_CLIENT_SECRET: str = os.getenv("ML_CLIENT_SECRET")
    
    # --- SEGURANÇA E BANCO DE DADOS ---
    DB_PASSWORD: str = ""
    # CHAVE SECRETA PARA O JWT (ADICIONADA AQUI)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "uma_chave_muito_secreta_e_longa_para_seguranca")

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore" # Ignora variáveis extras no .env

settings = Settings()