# app/models/entities.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
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