# app/services/magalu/utils.py
import requests
import logging
from datetime import datetime, timezone, timedelta # Importado timezone
from sqlalchemy.orm import Session
from app.models.entities import MagaluCredential
# Note: Certifique-se de que MagaluCredential foi adicionado ao seu entities.py

logger = logging.getLogger(__name__)

# Configurações Magalu
MAGALU_CLIENT_ID = "dst0ze8NSCMBEDXVy5ybb7iNiaF-Qfu4I8FgOFWw9vs"
MAGALU_CLIENT_SECRET = "Yq9N043UGTv-ph22QVHbPrPqIxzWrzsUIzDAYpBtBJQ"
MAGALU_TOKEN_URL = "https://id.magalu.com/oauth/token"

def get_valid_magalu_access_token(db: Session, seller_id: str):
    creds = db.query(MagaluCredential).filter(MagaluCredential.seller_id == seller_id).first()
    
    if not creds:
        raise Exception(f"Credenciais Magalu não encontradas para o seller {seller_id}")

    # AJUSTE: Pegando a hora atual com fuso horário UTC (Aware)
    current_time = datetime.now(timezone.utc)

    # Verifica se o token expirou (ou vai expirar em 5 minutos)
    # Agora os dois lados da comparação possuem fuso horário
    if creds.expires_at and current_time < (creds.expires_at - timedelta(minutes=5)):
        return creds.access_token

    # Se expirou, faz o Refresh
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
        creds.refresh_token = data.get('refresh_token', creds.refresh_token)
        # Salvando a expiração também com fuso horário
        creds.expires_at = datetime.now(timezone.utc) + timedelta(seconds=data['expires_in'])
        
        db.commit()
        return creds.access_token
    else:
        logger.error(f"❌ Erro ao renovar token Magalu: {response.text}")
        raise Exception("Falha na renovação do token Magalu")