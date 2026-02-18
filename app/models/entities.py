# app/models/entities.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    name = Column(String)
    hashed_password = Column(String)
    loja_permissao = Column(String, default="todas")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ScrapingLog(Base):
    __tablename__ = "scraping_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    loja = Column(String)
    url_count = Column(Integer)
    total_tokens = Column(Integer)
    total_cost_brl = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MercadoLivreOrder(Base):
    """Nova tabela para armazenar notificações de vendas do Mercado Livre"""
    __tablename__ = "mercadolivre_orders"
    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(String, unique=True, index=True) # ID da Ordem no ML
    topic = Column(String) # orders, items, etc.
    raw_data = Column(JSON) # Payload completo do webhook
    status = Column(String, default="received")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MLCredential(Base):
    """Tabela para gerenciar o OAuth 2.0 da sua loja"""
    __tablename__ = "ml_credentials"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(String, unique=True)
    store_name = Column(String)
    access_token = Column(String)
    refresh_token = Column(String)
    expires_at = Column(DateTime(timezone=True)) # Data de expiração do access_token
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())