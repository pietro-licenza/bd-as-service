# app/services/magalu/utils.py
import requests
import logging
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models.entities import MagaluCredential

logger = logging.getLogger(__name__)

# Configurações Magalu vindas de variáveis de ambiente para segurança
MAGALU_CLIENT_ID = os.getenv("MAGALU_CLIENT_ID")
MAGALU_CLIENT_SECRET = os.getenv("MAGALU_CLIENT_SECRET")
MAGALU_TOKEN_URL = "https://id.magalu.com/oauth/token"
MAGALU_BASE_URL = "https://api.magalu.com" # Base URL padrão para API Integra

def exchange_code_for_magalu_tokens(db: Session, seller_id: str, code: str):
    """
    Troca o authorization code pelo primeiro par de tokens Access/Refresh.
    Crucial para novas conexões ou quando o Refresh Token expira.
    """
    # O Redirect URI deve ser EXATAMENTE igual ao configurado no painel IDM da Magalu
    redirect_uri = "https://bd-as-service-88534390451.us-central1.run.app/api/webhooks/magalu/callback"
    
    logger.info(f"🔑 Trocando código de autorização para o seller: {seller_id}")
    
    payload = {
        'grant_type': 'authorization_code',
        'client_id': MAGALU_CLIENT_ID,
        'client_secret': MAGALU_CLIENT_SECRET,
        'code': code,
        'redirect_uri': redirect_uri
    }
    
    try:
        response = requests.post(MAGALU_TOKEN_URL, data=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Busca credencial existente ou cria uma nova
            creds = db.query(MagaluCredential).filter(MagaluCredential.seller_id == seller_id).first()
            if not creds:
                creds = MagaluCredential(seller_id=seller_id)
                db.add(creds)
            
            # Atualiza os dados
            creds.access_token = data['access_token']
            creds.refresh_token = data.get('refresh_token', creds.refresh_token)
            
            # Calcula expiração
            expires_in = data.get('expires_in', 3600)
            creds.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            db.commit()
            logger.info(f"✅ Conexão Magalu estabelecida com sucesso para {seller_id}")
            return True
        
        logger.error(f"❌ Erro na troca de código Magalu ({response.status_code}): {response.text}")
        return False
        
    except Exception as e:
        logger.error(f"💥 Erro crítico ao trocar código Magalu: {e}")
        return False

def get_valid_magalu_access_token(db: Session, seller_id: str):
    """Recupera ou renova o token OAuth da Magalu."""
    creds = db.query(MagaluCredential).filter(MagaluCredential.seller_id == seller_id).first()
    
    if not creds:
        raise Exception(f"Credenciais Magalu não encontradas para o seller {seller_id}")

    current_time = datetime.now(timezone.utc)

    # Verifica se o token expirou (ou vai expirar em 5 minutos)
    if creds.expires_at and current_time < (creds.expires_at - timedelta(minutes=5)):
        return creds.access_token

    # Renovação do token (Refresh)
    logger.info(f"🔄 Renovando token Magalu para o seller {seller_id}...")
    
    payload = {
        'grant_type': 'refresh_token',
        'client_id': MAGALU_CLIENT_ID,
        'client_secret': MAGALU_CLIENT_SECRET,
        'refresh_token': creds.refresh_token
    }
    
    response = requests.post(MAGALU_TOKEN_URL, data=payload)
    
    if response.status_code == 200:
        data = response.json()
        creds.access_token = data['access_token']
        # Magalu às vezes rotaciona o refresh_token, se vier um novo, salvamos
        creds.refresh_token = data.get('refresh_token', creds.refresh_token)
        creds.expires_at = datetime.now(timezone.utc) + timedelta(seconds=data['expires_in'])
        
        db.commit()
        return creds.access_token
    else:
        logger.error(f"❌ Erro ao renovar token Magalu: {response.text}")
        raise Exception("Falha na renovação do token Magalu")

def get_magalu_order_details(resource_uri: str, access_token: str, tenant_id: str):
    """
    Busca os detalhes completos do pedido na API da Magalu.
    Header X-Tenant-ID é obrigatório.
    """
    url = resource_uri if resource_uri.startswith("http") else f"{MAGALU_BASE_URL}{resource_uri}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Tenant-ID": tenant_id,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"🔗 Consultando detalhes do pedido Magalu: {url} | Tenant: {tenant_id}")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        
        logger.error(f"❌ Falha ao buscar detalhes Magalu ({response.status_code}): {response.text}")
        return None
    except Exception as e:
        logger.error(f"💥 Erro de conexão com API Magalu: {e}")
        return None