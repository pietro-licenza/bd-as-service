# app/services/magalu/utils.py
import requests
import logging
from datetime import datetime, timedelta, timezone
from app.models.entities import MagaluCredential
from app.core.config import settings

logger = logging.getLogger(__name__)

MAGALU_BASE_URL = "https://api.magalu.com"

def get_valid_magalu_access_token(db, tenant_id: str):
    """Retorna um token válido, renovando se necessário."""
    creds = db.query(MagaluCredential).filter(MagaluCredential.seller_id == tenant_id).first()
    if not creds:
        raise Exception(f"Credenciais Magalu não encontradas para o tenant {tenant_id}")

    now = datetime.now(timezone.utc)
    # Renova se faltar menos de 5 minutos para expirar
    if not creds.access_token or not creds.expires_at or now >= creds.expires_at.replace(tzinfo=timezone.utc) - timedelta(minutes=5):
        logger.info(f"🔄 Renovando token Magalu para o seller {tenant_id}...")
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": creds.refresh_token,
            "client_id": settings.MAGALU_CLIENT_ID,
            "client_secret": settings.MAGALU_CLIENT_SECRET
        }
        
        response = requests.post(f"{MAGALU_BASE_URL}/oauth/token", data=payload)
        
        if response.status_code == 200:
            new_data = response.json()
            creds.access_token = new_data['access_token']
            # IMPORTANTE: Magalu pode enviar um novo refresh_token. Precisamos salvar!
            if 'refresh_token' in new_data:
                creds.refresh_token = new_data['refresh_token']
            
            creds.expires_at = now + timedelta(seconds=new_data['expires_in'])
            db.commit()
            logger.info(f"✅ Token Magalu renovado com sucesso para {tenant_id}")
        else:
            logger.error(f"❌ Erro ao renovar token Magalu: {response.text}")
            raise Exception(f"Falha ao renovar token: {response.status_code}")

    return creds.access_token

def get_magalu_order_details(order_id: str, token: str, tenant_id: str):
    """Busca detalhes de um pedido específico."""
    # Garante que order_id seja apenas o número (caso venha o path completo)
    clean_id = order_id.split('/')[-1]
    
    url = f"{MAGALU_BASE_URL}/seller/v1/orders/{clean_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": tenant_id
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    
    logger.error(f"❌ Erro ao buscar detalhes do pedido {clean_id}: {response.text}")
    return None