# app/services/magalu/utils.py
import requests
import logging
from datetime import datetime, timedelta, timezone
from app.models.entities import MagaluCredential
from app.core.config import settings

logger = logging.getLogger(__name__)

# --- ENDPOINTS OFICIAIS MAGALU ---
MAGALU_AUTH_URL = "https://id.magalu.com/oauth/token"  # Para renovar o token
MAGALU_API_URL = "https://api.magalu.com"             # Para buscar os pedidos
# ---------------------------------

def get_valid_magalu_access_token(db, tenant_id: str):
    """Busca credenciais no banco e renova o token se necessário."""
    creds = db.query(MagaluCredential).filter(MagaluCredential.seller_id == tenant_id).first()
    
    if not creds:
        logger.error(f"❌ Seller {tenant_id} não encontrado no banco de dados.")
        raise Exception(f"Credenciais Magalu não encontradas para {tenant_id}")

    now = datetime.now(timezone.utc)
    
    # Verifica expiração (com margem de segurança de 5 min)
    is_expired = (
        not creds.access_token or 
        not creds.expires_at or 
        now >= creds.expires_at.replace(tzinfo=timezone.utc) - timedelta(minutes=5)
    )

    if is_expired:
        logger.info(f"🔄 Renovando token Magalu no servidor de identidade (id.magalu.com)...")
        
        # Conforme documentação: x-www-form-urlencoded
        payload = {
            "grant_type": "refresh_token",
            "client_id": settings.MAGALU_CLIENT_ID,
            "client_secret": settings.MAGALU_CLIENT_SECRET,
            "refresh_token": creds.refresh_token
        }
        
        try:
            # requests.post com 'data' envia automaticamente como form-urlencoded
            response = requests.post(MAGALU_AUTH_URL, data=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                creds.access_token = data['access_token']
                # Se a Magalu devolver um novo refresh_token, precisamos salvar!
                if 'refresh_token' in data:
                    creds.refresh_token = data['refresh_token']
                
                # Atualiza tempo de vida (geralmente vem em segundos)
                expires_in = data.get('expires_in', 3600)
                creds.expires_at = now + timedelta(seconds=expires_in)
                
                db.commit()
                logger.info(f"✅ Token renovado com sucesso para o seller {tenant_id}")
            else:
                logger.error(f"❌ Falha na renovação: {response.status_code} - {response.text}")
                raise Exception(f"Erro Magalu Auth: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Erro de conexão ao renovar token: {str(e)}")
            raise e

    return creds.access_token

def get_magalu_order_details(order_id: str, token: str, tenant_id: str):
    """Busca os dados do pedido no servidor de recursos (api.magalu.com)."""
    
    # Limpa o ID de qualquer parâmetro de URL (?...)
    clean_id = order_id.split('?')[0].split('/')[-1]
    
    url = f"{MAGALU_API_URL}/seller/v1/orders/{clean_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": tenant_id
    }
    
    try:
        logger.info(f"📡 Solicitando detalhes do pedido {clean_id} à API Magalu...")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        
        logger.error(f"❌ Erro ao buscar pedido {clean_id}: {response.status_code} - {response.text}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Exceção ao buscar detalhes do pedido: {str(e)}")
        return None