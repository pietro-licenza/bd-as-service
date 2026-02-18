import logging
import requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.entities import MLCredential
from app.core.config import settings

logger = logging.getLogger(__name__)

ML_AUTH_URL = "https://api.mercadolibre.com/oauth/token"

def get_valid_access_token(db: Session, seller_id: str) -> str:
    """
    Busca o token no banco, verifica validade e renova se necessário.
    """
    creds = db.query(MLCredential).filter(MLCredential.seller_id == str(seller_id)).first()
    
    if not creds:
        raise Exception(f"Credenciais não encontradas para o seller {seller_id}")

    # Verifica se expira nos próximos 5 minutos para margem de segurança
    if creds.expires_at <= datetime.utcnow() + timedelta(minutes=5):
        logger.info(f"🔁 Token da loja {seller_id} expirado ou próximo da expiração. Renovando...")
        
        payload = {
            "grant_type": "refresh_token",
            "client_id": settings.ML_CLIENT_ID,
            "client_secret": settings.ML_CLIENT_SECRET,
            "refresh_token": creds.refresh_token
        }

        response = requests.post(ML_AUTH_URL, data=payload)
        
        if response.status_code == 200:
            data = response.json()
            # Atualiza no banco
            creds.access_token = data["access_token"]
            creds.refresh_token = data.get("refresh_token", creds.refresh_token)
            creds.expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])
            db.commit()
            logger.info(f"✅ Token da loja {seller_id} renovado com sucesso.")
            return creds.access_token
        else:
            logger.error(f"❌ Erro ao renovar token ML: {response.text}")
            raise Exception("Falha na renovação do token do Mercado Livre")

    return creds.access_token