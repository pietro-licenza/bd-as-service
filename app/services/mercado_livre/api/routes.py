import logging
import requests
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entities import MercadoLivreOrder, MLCredential
from app.services.mercado_livre.utils import get_valid_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks/mercadolivre", tags=["Mercado Livre Webhook"])

ML_API_BASE = "https://api.mercadolibre.com"

@router.post("/notifications")
async def ml_webhook_receiver(request: Request, db: Session = Depends(get_db)):
    """
    Recebe notificações e busca detalhes usando tokens dinâmicos por loja.
    """
    try:
        notification = await request.json()
        resource_path = notification.get("resource")
        topic = notification.get("topic")
        ml_user_id = str(notification.get("user_id"))

        logger.info(f"🔔 Notificação: Loja {ml_user_id} | Tópico {topic}")

        if topic == "orders":
            # Obtém token válido (renova automaticamente se precisar)
            try:
                token = get_valid_access_token(db, ml_user_id)
            except Exception as e:
                logger.error(f"❌ Erro de autenticação para loja {ml_user_id}: {e}")
                return {"status": "error", "message": "Auth failed"}

            # Consulta os dados reais da venda
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{ML_API_BASE}{resource_path}", headers=headers)

            if response.status_code == 200:
                order_details = response.json()
                
                existing_order = db.query(MercadoLivreOrder).filter(MercadoLivreOrder.resource_id == resource_path).first()
                
                if existing_order:
                    existing_order.raw_data = order_details
                    existing_order.status = order_details.get("status", "updated")
                else:
                    new_order = MercadoLivreOrder(
                        seller_id=ml_user_id,
                        resource_id=resource_path,
                        topic=topic,
                        raw_data=order_details,
                        status=order_details.get("status", "paid")
                    )
                    db.add(new_order)
                
                db.commit()
                logger.info(f"✅ Venda {resource_path} da loja {ml_user_id} salva.")
            else:
                logger.error(f"❌ Erro API ML ({response.status_code}): {response.text}")

        return {"status": "success"}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro crítico no webhook: {str(e)}")
        return {"status": "error", "message": str(e)}