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
    Recebe notificações de vendas do Magalu e salva na tabela unificada 'orders'.
    """
    try:
        order_details = await request.json()
        
        # O Magalu identifica a ordem pelo 'id' ou 'order_id'
        external_id = str(order_details.get("id") or order_details.get("order_id"))
        # No Magalu, o seller_id geralmente vem no campo 'seller' ou passamos via parâmetro
        # Por enquanto, vamos tentar capturar do payload
        seller_id = str(order_details.get("seller_id", "desconhecido"))

        logger.info(f"📦 Nova Venda Magalu: Pedido #{external_id}")

        # 1. Tenta encontrar a organização vinculada a este seller no nosso banco
        creds = db.query(MagaluCredential).filter(MagaluCredential.seller_id == seller_id).first()
        store_slug = creds.store_slug if creds else "magalu_vendas"

        # 2. Mapeamento de Status (Magalu para nosso padrão)
        # Magalu usa: NEW, APPROVED, SHIPPED, DELIVERED, CANCELLED
        magalu_status = order_details.get("status", "NEW").lower()
        
        # 3. Lógica de Upsert (Salva ou Atualiza)
        existing_order = db.query(Order).filter(Order.external_id == external_id, Order.marketplace == "magalu").first()
        
        # Valor total no Magalu costuma vir em 'total_amount' ou 'total_price'
        total_amount = float(order_details.get("total_amount") or order_details.get("total_price") or 0)

        if existing_order:
            existing_order.status = "paid" if magalu_status == "approved" else magalu_status
            existing_order.total_amount = total_amount
            existing_order.raw_data = order_details
            logger.info(f"🔄 Venda {external_id} atualizada para status: {existing_order.status}")
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
            logger.info(f"✅ Venda {external_id} criada com sucesso para a loja: {store_slug}")

        db.commit()
        return {"status": "success", "order_id": external_id}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro ao processar Webhook Magalu: {str(e)}")
        # Respondemos 200 para o Magalu não ficar tentando reenviar em caso de erro de lógica nosso
        return {"status": "error", "message": str(e)}

@router.get("/test-auth/{seller_id}")
async def test_magalu_auth(seller_id: str, db: Session = Depends(get_db)):
    """Mantemos aqui para você validar as chaves quando precisar"""
    try:
        token = get_valid_magalu_access_token(db, seller_id)
        return {"status": "success", "token_valido": True}
    except Exception as e:
        return {"status": "error", "message": str(e)}