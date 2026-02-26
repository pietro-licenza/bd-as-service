# app/services/magalu/utils.py
import requests
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models.entities import MagaluCredential
from app.core.config import settings

logger = logging.getLogger(__name__)

MAGALU_CLIENT_ID = settings.MAGALU_CLIENT_ID
MAGALU_CLIENT_SECRET = settings.MAGALU_CLIENT_SECRET
MAGALU_TOKEN_URL = "https://id.magalu.com/oauth/token"
MAGALU_BASE_URL = "https://api.magalu.com"

def get_valid_magalu_access_token(db: Session, seller_id: str):
    """
    Recupera ou renova o token OAuth da Magalu.
    Lida com o fluxo de Organization (PJ).
    """
    creds = db.query(MagaluCredential).filter(MagaluCredential.seller_id == seller_id).first()
    
    if not creds:
        raise Exception(f"Credenciais Magalu não encontradas para o seller {seller_id}")

    current_time = datetime.now(timezone.utc)

    # Se o token ainda é válido por mais de 5 minutos, retorna ele
    if creds.expires_at and current_time < (creds.expires_at.replace(tzinfo=timezone.utc) - timedelta(minutes=5)):
        return creds.access_token

    # Caso contrário, faz o REFRESH automático (A peça chave para o Cloud Run)
    logger.info(f"🔄 Renovando token Magalu para o seller {seller_id}...")
    
    payload = {
        'grant_type': 'refresh_token',
        'client_id': MAGALU_CLIENT_ID,
        'client_secret': MAGALU_CLIENT_SECRET,
        'refresh_token': creds.refresh_token
    }
    
    try:
        response = requests.post(MAGALU_TOKEN_URL, data=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            creds.access_token = data['access_token']
            # Salva o novo refresh_token se a Magalu rotacionar
            creds.refresh_token = data.get('refresh_token', creds.refresh_token)
            creds.expires_at = datetime.now(timezone.utc) + timedelta(seconds=data['expires_in'])
            
            db.commit()
            logger.info(f"✅ Token Magalu renovado com sucesso para {seller_id}")
            return creds.access_token
        else:
            logger.error(f"❌ Erro ao renovar token Magalu: {response.text}")
            raise Exception("Falha na renovação do token Magalu")
    except Exception as e:
        logger.error(f"💥 Falha técnica no refresh Magalu: {e}")
        raise e

def get_magalu_order_details(resource_uri: str, access_token: str, tenant_id: str):
    """
    Busca os detalhes completos do pedido.
    Implementa o header X-Tenant-Id validado no notebook para evitar erro 422.
    """
    # Se resource_uri vier apenas como ID, montamos a URL
    if not resource_uri.startswith("http") and not resource_uri.startswith("/"):
        url = f"{MAGALU_BASE_URL}/seller/v1/orders/{resource_uri}"
    else:
        url = resource_uri if resource_uri.startswith("http") else f"{MAGALU_BASE_URL}{resource_uri}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Tenant-Id": tenant_id, # Header crucial para Organization
        "Accept": "application/json"
    }
    
    try:
        logger.info(f"📡 Consultando Magalu: {url} | Tenant: {tenant_id}")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        
        logger.error(f"❌ Falha ao buscar detalhes Magalu ({response.status_code}): {response.text}")
        return None
    except Exception as e:
        logger.error(f"💥 Erro de conexão com API Magalu: {e}")
        return None