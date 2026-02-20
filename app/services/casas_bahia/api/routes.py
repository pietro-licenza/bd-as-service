import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entities import Order

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks/casas-bahia", tags=["Casas Bahia Webhook"])

@router.post("/notifications")
async def cb_webhook_receiver(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
        logger.info(f"🔔 Notificação Casas Bahia recebida: {payload}")

        # Extração de dados (ajustar conforme o payload real da Via Varejo)
        external_id = str(payload.get("order_id") or payload.get("id"))
        status = str(payload.get("status", "NEW")).lower()
        total_amount = float(payload.get("total_amount", 0))

        # Lógica de Upsert (Igual à Magalu)
        existing_order = db.query(Order).filter(
            Order.external_id == external_id, 
            Order.marketplace == "casas_bahia"
        ).first()

        if existing_order:
            existing_order.status = status
            existing_order.total_amount = total_amount
            existing_order.raw_data = payload
            logger.info(f"🔄 Venda CB {external_id} atualizada.")
        else:
            new_order = Order(
                marketplace="casas_bahia",
                external_id=external_id,
                total_amount=total_amount,
                status=status,
                raw_data=payload
            )
            db.add(new_order)
            logger.info(f"✅ Venda CB {external_id} criada com sucesso.")

        db.commit()
        return {"status": "success"}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro Webhook Casas Bahia: {str(e)}")
        return {"status": "error", "message": str(e)}