import logging
import requests
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entities import Order, MLCredential, User
from app.api.auth import get_current_user
# Importe sua função de obter usuário atual (ajuste o caminho se necessário)
# from app.api.auth import get_current_user 

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks/mercadolivre", tags=["Mercado Livre Webhook"])

ML_API_BASE = "https://api.mercadolibre.com"

@router.post("/notifications")
async def ml_webhook_receiver(request: Request, db: Session = Depends(get_db)):
    """
    Recebe notificações do ML e salva na tabela unificada 'orders' com vínculo de organização.
    """
    try:
        notification = await request.json()
        resource_path = notification.get("resource")
        topic = notification.get("topic")
        ml_user_id = str(notification.get("user_id"))

        logger.info(f"🔔 Notificação: Loja {ml_user_id} | Tópico {topic}")

        if topic in ["orders", "orders_v2"]:
            # 1. Obtém slug da organização dona desta conta ML
            creds = db.query(MLCredential).filter(MLCredential.seller_id == ml_user_id).first()
            store_slug = creds.store_slug if creds else "desconhecido"

            # 2. Obtém token válido
            try:
                token = get_valid_access_token(db, ml_user_id)
            except Exception as e:
                logger.error(f"❌ Erro de autenticação para loja {ml_user_id}: {e}")
                return {"status": "error", "message": "Auth failed"}

            # 3. Consulta os dados reais da venda
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{ML_API_BASE}{resource_path}", headers=headers)

            if response.status_code == 200:
                order_details = response.json()
                
                existing_order = db.query(Order).filter(Order.external_id == resource_path).first()
                
                if existing_order:
                    existing_order.raw_data = order_details
                    existing_order.status = order_details.get("status", "updated")
                    existing_order.total_amount = order_details.get("total_amount")
                    existing_order.store_slug = store_slug # Atualiza o vínculo
                else:
                    new_order = Order(
                        marketplace="mercadolivre",
                        external_id=resource_path,
                        seller_id=ml_user_id,
                        store_slug=store_slug, # Salva o vínculo da organização
                        total_amount=order_details.get("total_amount"),
                        status=order_details.get("status", "paid"),
                        raw_data=order_details
                    )
                    db.add(new_order)
                
                db.commit()
                logger.info(f"✅ Venda {resource_path} (ML) salva para a organização: {store_slug}")
            else:
                logger.error(f"❌ Erro API ML ({response.status_code}): {response.text}")

        return {"status": "success"}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro crítico no webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.get("/orders")
async def list_orders(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user) # Esta linha ativa o filtro
):
    query = db.query(Order)
    if current_user.loja_permissao != "todas":
        query = query.filter(Order.store_slug == current_user.loja_permissao)
    
    return query.order_by(Order.created_at.desc()).all()