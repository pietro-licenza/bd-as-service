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

class MLCredential(Base):
    """Tabela para gerenciar o OAuth 2.0 da sua loja"""
    __tablename__ = "ml_credentials"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(String, unique=True, index=True)
    store_name = Column(String)
    access_token = Column(String)
    refresh_token = Column(String)
    store_slug = Column(String, index=True)
    expires_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    marketplace = Column(String, index=True) # Identifica a origem: 'mercadolivre', 'shopee', etc.
    external_id = Column(String, index=True, unique=True) # ID da ordem no Marketplace
    seller_id = Column(String, index=True)
    total_amount = Column(Float)
    status = Column(String)
    raw_data = Column(JSON) # JSON completo enviado pela API original
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    store_slug = Column(String, index=True)

class MagaluCredential(Base):
    """Tabela para gerenciar o OAuth 2.0 da sua loja Magalu"""
    __tablename__ = "magalu_credentials"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(String, unique=True, index=True) # ID do Seller no Magalu
    access_token = Column(String)
    refresh_token = Column(String)
    store_slug = Column(String, index=True) # Vínculo com a organização (ex: brazil_direct)
    expires_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CasasBahiaCredential(Base):
    """Tabela para gerenciar as chaves de acesso das lojas Casas Bahia"""
    __tablename__ = "casas_bahia_credentials"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(String, unique=True, index=True) # ID da loja no portal
    client_id = Column(String)
    access_token = Column(String)
    store_slug = Column(String, index=True) # Vínculo com a organização (ex: loja_1, loja_2)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())