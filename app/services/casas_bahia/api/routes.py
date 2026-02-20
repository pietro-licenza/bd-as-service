import logging
import requests
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entities import Order, CasasBahiaCredential

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks/casas-bahia", tags=["Casas Bahia Webhook"])

def get_cb_order_details(resource_uri: str, client_id: str, access_token: str):
    """
    Busca os detalhes completos do pedido na API das Casas Bahia.
    Utiliza múltiplos headers de autenticação para garantir compatibilidade 
    com o gateway (evitando erros de 'kid' ou 'auth-token').
    """
    # AMBIENTE: Trocando para HLG conforme os testes atuais
    # Para Produção futuramente: https://api.viavarejo.com.br/api/v2
    base_url = "https://api-mktplace-hlg.viavarejo.com.br/api/v2"
    url = f"{base_url}{resource_uri}"
    
    # Técnica de "Headers Combinados" para vencer o erro 401.004
    headers = {
        "client_id": client_id,
        "access_token": access_token,
        "auth-token": access_token,              # Sugerido pelo erro 401.004
        "apiKey": f"{client_id}:{access_token}", # Padrão do exemplo curl do painel
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) API-Integration"
    }
    
    try:
        logger.info(f"🔗 Consultando API Casas Bahia (HLG): {url}")
        # Timeout de 10s para evitar que o processo trave se o firewall deles dropar o pacote
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Dados do pedido recuperados com sucesso.")
            return response.json()
        else:
            logger.error(f"❌ Falha na API ({response.status_code}): {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("⏳ Timeout ao conectar na API das Casas Bahia (Firewall/Akamai).")
        return None
    except Exception as e:
        logger.error(f"💥 Erro imprevisto na consulta CB: {e}")
        return None

@router.post("/notifications")
async def cb_webhook_receiver(request: Request, db: Session = Depends(get_db)):
    """
    Recebe notificações das Casas Bahia, identifica a loja via seller_id 
    e centraliza na tabela unificada 'orders'.
    """
    try:
        payload = await request.json()
        logger.info(f"🔔 Notificação Casas Bahia recebida.")

        # 1. TRATAMENTO DE CHALLENGE
        if "challenge" in payload:
            challenge_val = payload.get("challenge")
            logger.info(f"🛡️ Validando Challenge: {challenge_val}")
            return {"challenge": challenge_val}

        # 2. EXTRAÇÃO DE DADOS (Padrão camelCase da documentação)
        seller_id = str(payload.get("sellerId"))
        external_id = str(payload.get("resourceId"))
        cb_event = str(payload.get("eventType", "New")).lower()
        resource_uri = payload.get("uriResource")

        logger.info(f"📦 Processando Pedido CB: #{external_id} | Seller: {seller_id}")

        # 3. BUSCA DINÂMICA DAS CREDENCIAIS NO BANCO
        creds = db.query(CasasBahiaCredential).filter(
            CasasBahiaCredential.seller_id == seller_id
        ).first()
        
        if not creds:
            logger.warning(f"⚠️ Loja não cadastrada para o sellerId: {seller_id}")
            store_slug = "casas_bahia_desconhecida"
        else:
            store_slug = creds.store_slug

        # 4. ENRIQUECIMENTO DOS DADOS (Busca Preço/Cliente)
        order_details = payload # Fallback com os dados básicos da notificação
        total_amount = 0.0
        
        if creds and resource_uri:
            api_data = get_cb_order_details(resource_uri, creds.client_id, creds.access_token)
            if api_data:
                order_details = api_data
                # Tenta pegar o valor total de diferentes chaves possíveis da API
                total_amount = float(api_data.get("total_amount") or api_data.get("total_price") or 0)

        # 5. MAPEAMENTO DE STATUS
        status_map = {
            "new": "pendente",
            "approved": "paid",
            "canceled": "cancelado",
            "returned": "devolvido",
            "sent": "enviado",
            "delivered": "entregue"
        }
        final_status = status_map.get(cb_event, cb_event)

        # 6. UPSERT NA TABELA ORDERS
        existing_order = db.query(Order).filter(
            Order.external_id == external_id, 
            Order.marketplace == "casas_bahia"
        ).first()

        if existing_order:
            existing_order.status = final_status
            if total_amount > 0:
                existing_order.total_amount = total_amount
            existing_order.raw_data = order_details
            logger.info(f"🔄 Pedido {external_id} atualizado.")
        else:
            new_order = Order(
                marketplace="casas_bahia",
                external_id=external_id,
                seller_id=seller_id,
                store_slug=store_slug,
                total_amount=total_amount,
                status=final_status,
                raw_data=order_details
            )
            db.add(new_order)
            logger.info(f"✅ Nova venda CB {external_id} salva para: {store_slug}")

        db.commit()
        return {"status": "success", "order_id": external_id}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro no Webhook CB: {str(e)}")
        return {"status": "error", "message": str(e)}