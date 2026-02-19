# app/services/magalu/api/routes.py
import logging
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entities import Order, MagaluCredential
from app.services.magalu.utils import get_valid_magalu_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks/magalu", tags=["Magalu Webhook"])

@router.post("/notifications")
async def magalu_webhook_receiver(request: Request, db: Session = Depends(get_db)):
    """
    Recebe notificações do Magalu, filtra apenas eventos de pedidos
    e salva na tabela unificada 'orders'.
    """
    try:
        payload = await request.json()
        
        # 1. BLOCO DE VALIDAÇÃO (CHALLENGE)
        if "challenge" in payload:
            challenge_val = payload.get("challenge")
            logger.info(f"🛡️ Validando Challenge Magalu: {challenge_val}")
            return {"challenge": challenge_val}

        # 2. IDENTIFICAÇÃO DO TÓPICO
        # O Magalu envia o nome do evento no campo 'topic' ou 'event'
        topic = payload.get("topic") or payload.get("event")
        logger.info(f"🔔 Notificação Magalu recebida. Tópico: {topic}")

        # 3. FILTRO DE EVENTOS DE PEDIDO
        # Lista de tópicos que queremos processar (conforme o retorno do seu Postman)
        order_topics = ["created_order", "orders_order", "orders_delivery"]
        
        if topic not in order_topics:
            logger.info(f"⏩ Ignorando tópico não relacionado a pedidos: {topic}")
            return {"status": "ignored", "message": "Evento não processado"}

        # 4. PROCESSAMENTO DO PEDIDO
        # Se chegou aqui, é um pedido real.
        order_details = payload
        
        external_id = str(order_details.get("id") or order_details.get("order_id"))
        seller_id = str(order_details.get("seller_id", "desconhecido"))

        logger.info(f"📦 Processando Pedido Magalu: #{external_id}")

        # Tenta encontrar a organização vinculada
        creds = db.query(MagaluCredential).filter(MagaluCredential.seller_id == seller_id).first()
        store_slug = creds.store_slug if creds else "magalu_vendas"

        # Mapeamento de Status
        magalu_status = str(order_details.get("status", "NEW")).lower()
        
        # Lógica de Upsert (Atualiza se existir, cria se não)
        existing_order = db.query(Order).filter(
            Order.external_id == external_id, 
            Order.marketplace == "magalu"
        ).first()
        
        total_amount = float(order_details.get("total_amount") or order_details.get("total_price") or 0)

        if existing_order:
            existing_order.status = "paid" if magalu_status == "approved" else magalu_status
            existing_order.total_amount = total_amount
            existing_order.raw_data = order_details
            logger.info(f"🔄 Venda {external_id} atualizada para: {existing_order.status}")
        else:
            new_order = Order(
                marketplace="magalu",
                external_id=external_id,
                seller_id=seller_id,
                store_slug=store_slug,
                total_amount=total_amount,
                status="paid" if magalu_status == "approved" else magalu_status,
                raw_data=order_details
            )
            db.add(new_order)
            logger.info(f"✅ Venda {external_id} criada para a loja: {store_slug}")

        db.commit()
        return {"status": "success", "order_id": external_id}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro ao processar Webhook Magalu: {str(e)}")
        # Retornamos 200 mesmo no erro para evitar que o Magalu tente reenviar 
        # infinitamente notificações problemáticas
        return {"status": "error", "message": str(e)}
@router.get("/test-auth/{seller_id}")
async def test_magalu_auth(seller_id: str, db: Session = Depends(get_db)):
    """Valida se as chaves e a renovação de token estão funcionando"""
    try:
        token = get_valid_magalu_access_token(db, seller_id)
        return {"status": "success", "token_valido": True}
    except Exception as e:
        return {"status": "error", "message": str(e)}