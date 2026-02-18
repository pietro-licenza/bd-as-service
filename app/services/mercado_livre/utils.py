import logging
import requests
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.entities import MLCredential
from app.core.config import settings

logger = logging.getLogger(__name__)

ML_AUTH_URL = "https://api.mercadolibre.com/oauth/token"

def get_valid_access_token(db: Session, seller_id: str) -> str:
    """
    Busca o token no banco, verifica validade e renova se necessário.
    Logs adicionados para depuração de fuso horário e fluxo de autenticação.
    """
    logger.info(f"🔍 [ML AUTH] Iniciando verificação de token para o vendedor: {seller_id}")
    
    creds = db.query(MLCredential).filter(MLCredential.seller_id == str(seller_id)).first()
    
    if not creds:
        logger.error(f"❌ [ML AUTH] Credenciais não encontradas no banco para seller_id: {seller_id}")
        raise Exception(f"Credenciais não encontradas para o seller {seller_id}")

    # Captura o tempo atual com fuso horário UTC (Offset-aware)
    now_utc = datetime.now(timezone.utc)
    
    # LOG DE INSPEÇÃO: Verifica se ambos os lados da comparação possuem fuso horário
    logger.info(f"📅 [ML AUTH] Comparação de datas:")
    logger.info(f"   -> Agora (now_utc): {now_utc}")
    logger.info(f"   -> Expira em (creds.expires_at): {creds.expires_at}")
    
    # Verifica se expira nos próximos 5 minutos para margem de segurança
    if creds.expires_at <= now_utc + timedelta(minutes=5):
        logger.info(f"🔁 [ML AUTH] Token da loja {creds.store_name or seller_id} expirado ou próximo da expiração. Renovando...")
        
        payload = {
            "grant_type": "refresh_token",
            "client_id": settings.ML_CLIENT_ID,
            "client_secret": settings.ML_CLIENT_SECRET,
            "refresh_token": creds.refresh_token
        }

        # Log de segurança (sem expor o secret inteiro)
        logger.info(f"📡 [ML AUTH] Chamando API do Mercado Livre para Refresh. Client ID: {settings.ML_CLIENT_ID}")

        response = requests.post(ML_AUTH_URL, data=payload)
        
        if response.status_code == 200:
            data = response.json()
            
            # Atualiza no banco
            creds.access_token = data["access_token"]
            creds.refresh_token = data.get("refresh_token", creds.refresh_token)
            
            # Calcula nova expiração garantindo UTC
            new_expiry = now_utc + timedelta(seconds=data["expires_in"])
            creds.expires_at = new_expiry
            
            db.commit()
            logger.info(f"✅ [ML AUTH] Token renovado com sucesso. Nova expiração: {new_expiry}")
            return creds.access_token
        else:
            logger.error(f"❌ [ML AUTH] Erro ao renovar token ML: {response.text}")
            raise Exception(f"Falha na renovação do token do Mercado Livre: {response.status_code}")

    logger.info(f"✨ [ML AUTH] Token atual ainda é válido para a loja {creds.store_name or seller_id}.")
    return creds.access_token