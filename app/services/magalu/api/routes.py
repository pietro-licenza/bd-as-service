# app/services/magalu/api/routes.py
import logging
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entities import Order, MagaluCredential
from app.services.magalu.utils import get_valid_magalu_access_token, get_magalu_order_details

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks/magalu", tags=["Magalu Webhook"])

@router.post("/notifications")
async def magalu_webhook_receiver(request: Request, db: Session = Depends(get_db)):
    """
    Recebe notificações do Magalu e sincroniza com a tabela 'orders'.
    """
    try:
        payload = await request.json()
        
        # 1. VALIDAÇÃO DE CHALLENGE
        if "challenge" in payload:
            challenge_val = payload.get("challenge")
            logger.info(f"🛡️ Challenge Magalu validado: {challenge_val}")
            return {"challenge": challenge_val}

        # 2. IDENTIFICAÇÃO DO EVENTO E RECURSO
        topic = payload.get("topic") or payload.get("event")
        resource_uri = payload.get("resource") # URL/Path do pedido
        seller_id = str(payload.get("tenant_id") or payload.get("seller_id", "desconhecido"))
        
        logger.info(f"🔔 Notificação Magalu: {topic} para Seller: {seller_id}")

        # 3. FILTRO DE EVENTOS DE PEDIDO
        order_topics = ["created_order", "orders_order", "orders_delivery", "order"]
        if topic not in order_topics:
            return {"status": "ignored", "message": "Tópico não processado"}

        # 4. BUSCA CREDENCIAIS E TOKEN
        creds = db.query(MagaluCredential).filter(MagaluCredential.seller_id == seller_id).first()
        if not creds:
            logger.warning(f"⚠️ Seller Magalu {seller_id} não encontrado.")
            return {"status": "error", "message": "Seller não cadastrado"}

        store_slug = creds.store_slug
        token = get_valid_magalu_access_token(db, seller_id)

        # 5. BUSCA DETALHES COMPLETOS (Onde pegamos o valor real)
        order_info = payload # Fallback
        if resource_uri:
            api_details = get_magalu_order_details(resource_uri, token)
            if api_details:
                order_info = api_details

        # 6. EXTRAÇÃO DE DADOS PARA A TABELA UNIFICADA
        external_id = str(order_info.get("id") or order_info.get("order_id"))
        total_amount = float(order_info.get("total_amount") or order_info.get("total_price") or 0)
        
        # Mapeamento de Status
        magalu_status = str(order_info.get("status", "NEW")).lower()
        status_map = {
            "approved": "paid",
            "paid": "paid",
            "shipped": "shipped",
            "delivered": "delivered",
            "canceled": "cancelado"
        }
        final_status = status_map.get(magalu_status, "pendente")

        # 7. LÓGICA DE UPSERT
        existing_order = db.query(Order).filter(
            Order.external_id == external_id, 
            Order.marketplace == "magalu"
        ).first()

        if existing_order:
            existing_order.status = final_status
            existing_order.total_amount = total_amount
            existing_order.raw_data = order_info
            logger.info(f"🔄 Pedido Magalu {external_id} atualizado.")
        else:
            new_order = Order(
                marketplace="magalu",
                external_id=external_id,
                seller_id=seller_id,
                store_slug=store_slug,
                total_amount=total_amount,
                status=final_status,
                raw_data=order_info
            )
            db.add(new_order)
            logger.info(f"✅ Pedido Magalu {external_id} criado.")

        db.commit()
        return {"status": "success", "order_id": external_id}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro Webhook Magalu: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.get("/test-auth/{seller_id}")
async def test_magalu_auth(seller_id: str, db: Session = Depends(get_db)):
    """Valida se a renovação de token está funcionando."""
    try:
        token = get_valid_magalu_access_token(db, seller_id)
        return {"status": "success", "token_valido": True}
    except Exception as e:
        return {"status": "error", "message": str(e)}