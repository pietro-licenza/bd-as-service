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
    Busca os detalhes completos do pedido na API das Casas Bahia para obter 
    o valor total e dados do cliente.
    """
    # A base URL depende se você está em HLG ou PROD
    # Homologação: https://api-mktplace-hlg.viavarejo.com.br/api/v2
    # Produção: https://api.grupocasasbahia.com.br/api/v2
    base_url = "https://api.grupocasasbahia.com.br/api/v2"
    url = f"{base_url}{resource_uri}"
    
    headers = {
        "client_id": client_id,
        "access_token": access_token,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"❌ Erro ao consultar detalhes do pedido na API CB: {e}")
        return None

@router.post("/notifications")
async def cb_webhook_receiver(request: Request, db: Session = Depends(get_db)):
    """
    Recebe notificações das Casas Bahia, identifica a loja, busca detalhes 
    completos via API e centraliza na tabela 'orders'.
    """
    try:
        payload = await request.json()
        logger.info(f"🔔 Notificação Casas Bahia recebida.")

        # 1. TRATAMENTO DE CHALLENGE (Padrão de segurança de Webhooks)
        if "challenge" in payload:
            challenge_val = payload.get("challenge")
            logger.info(f"🛡️ Validando Challenge Casas Bahia: {challenge_val}")
            return {"challenge": challenge_val}

        # 2. EXTRAÇÃO DE DADOS (Padrão Oficial: camelCase)
        seller_id = str(payload.get("sellerId"))
        external_id = str(payload.get("resourceId"))
        cb_event = str(payload.get("eventType", "New")).lower()
        resource_uri = payload.get("uriResource")

        logger.info(f"📦 Processando Pedido Casas Bahia: #{external_id} | Loja: {seller_id}")

        # 3. BUSCA DINÂMICA DA LOJA NO BANCO
        creds = db.query(CasasBahiaCredential).filter(
            CasasBahiaCredential.seller_id == seller_id
        ).first()
        
        if not creds:
            logger.warning(f"⚠️ Credenciais não encontradas para o sellerId: {seller_id}")
            store_slug = "casas_bahia_desconhecida"
        else:
            store_slug = creds.store_slug

        # 4. BUSCA DE DETALHES COMPLETOS (Para pegar total_amount)
        # Se temos as credenciais, buscamos o valor real na API
        order_details = payload # Fallback: guarda o webhook se a API falhar
        total_amount = 0.0
        
        if creds and resource_uri:
            api_data = get_cb_order_details(resource_uri, creds.client_id, creds.access_token)
            if api_data:
                order_details = api_data # Substitui pelo JSON completo da API
                total_amount = float(api_data.get("total_amount") or api_data.get("total_price") or 0)

        # 5. MAPEAMENTO DE STATUS (Standardização Interna)
        status_map = {
            "new": "pendente",
            "approved": "paid",
            "canceled": "cancelado",
            "returned": "devolvido",
            "sent": "enviado",
            "delivered": "entregue"
        }
        final_status = status_map.get(cb_event, cb_event)

        # 6. LÓGICA DE UPSERT (IGUAL À MAGALU E ML)
        existing_order = db.query(Order).filter(
            Order.external_id == external_id, 
            Order.marketplace == "casas_bahia"
        ).first()

        if existing_order:
            existing_order.status = final_status
            if total_amount > 0:
                existing_order.total_amount = total_amount
            existing_order.raw_data = order_details
            logger.info(f"🔄 Venda CB {external_id} atualizada para: {final_status}")
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
            logger.info(f"✅ Venda CB {external_id} criada para a organização: {store_slug}")

        db.commit()
        return {"status": "success", "order_id": external_id}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro ao processar Webhook Casas Bahia: {str(e)}")
        # Retornamos status error mas sem HTTP status code de erro para evitar loops de reenvio
        return {"status": "error", "message": str(e)}