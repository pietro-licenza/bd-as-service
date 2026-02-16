# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from urllib.parse import quote_plus # Importante para lidar com os símbolos & e $
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

password = os.getenv('DB_PASSWORD')

# "Traduz" os caracteres especiais da senha para formato de URL
# Exemplo: o '&' vira '%26' para não quebrar a conexão
safe_password = quote_plus(password) if password else ""

# A URL CORRETA:
SQLALCHEMY_DATABASE_URL = f"postgresql://postgres.eynpcqcwyteafzbdajgl:{safe_password}@aws-1-us-east-2.pooler.supabase.com:6543/postgres"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()