# app/services/magalu/api/routes.py
import logging
import requests
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entities import Order, MagaluCredential, User
from app.api.auth import get_current_user
from app.services.magalu.utils import get_valid_magalu_access_token, get_magalu_order_details

logger = logging.getLogger(__name__)

# Seguindo o padrão de prefixo do Mercado Livre
router = APIRouter(prefix="/api/webhooks/magalu", tags=["Magalu Webhook"])

@router.post("/notifications")
async def magalu_webhook_receiver(request: Request, db: Session = Depends(get_db)):
    """
    Recebe notificações da Magalu e salva na tabela unificada 'orders'.
    Segue o padrão de verificação de duplicidade e vínculo de store_slug.
    """
    try:
        data = await request.json()
        
        # 1. Tratamento do Challenge (Específico da Magalu)
        if "challenge" in data:
            challenge_value = data["challenge"]
            logger.info(f"🛡️ Validando Challenge Magalu: {challenge_value}")
            return {"challenge": challenge_value}

        # 2. Extração de Metadados
        topic = data.get("topic")
        tenant_id = data.get("tenant_id") # O tenant_id é o nosso seller_id/user_id no ML
        resource_path = data.get("resource")

        logger.info(f"🔔 Notificação Magalu: Loja {tenant_id} | Tópico {topic}")

        if topic == "created_order" and resource_path:
            # 3. Obtém credenciais e store_slug
            creds = db.query(MagaluCredential).filter(
                (MagaluCredential.seller_id == tenant_id) | 
                (MagaluCredential.seller_id == '3f9afe2b-c52e-4bbe-b50b-d315ccab4970')
            ).first()
            
            store_slug = creds.store_slug if creds else "desconhecido"

            # 4. Obtém token válido
            try:
                token = get_valid_magalu_access_token(db, creds.seller_id)
            except Exception as e:
                logger.error(f"❌ Erro de autenticação Magalu para {tenant_id}: {e}")
                return {"status": "error", "message": "Auth failed"}

            # 5. Consulta os detalhes reais da venda (Passando o tenant_id como exigido no utils)
            order_details = get_magalu_order_details(resource_path, token, tenant_id)

            if order_details:
                # 6. Verifica duplicidade (Mesma lógica do ML)
                existing_order = db.query(Order).filter(Order.external_id == resource_path).first()
                
                if existing_order:
                    existing_order.raw_data = order_details
                    existing_order.status = order_details.get("status", "updated")
                    existing_order.total_amount = order_details.get("total_amount")
                    existing_order.store_slug = store_slug
                else:
                    new_order = Order(
                        marketplace="magalu",
                        external_id=resource_path,
                        seller_id=creds.seller_id,
                        store_slug=store_slug,
                        total_amount=order_details.get("total_amount"),
                        status=order_details.get("status", "paid"),
                        raw_data=order_details
                    )
                    db.add(new_order)
                
                db.commit()
                logger.info(f"✅ Venda {resource_path} (Magalu) salva para a organização: {store_slug}")
            else:
                logger.error(f"❌ Não foi possível obter detalhes da ordem {resource_path}")

        return {"status": "success"}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro crítico no webhook Magalu: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.get("/orders")
async def list_magalu_orders(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Lista ordens da Magalu com filtro de permissão.
    """
    query = db.query(Order).filter(Order.marketplace == "magalu")
    if current_user.loja_permissao != "todas":
        query = query.filter(Order.store_slug == current_user.loja_permissao)
    
    return query.order_by(Order.created_at.desc()).all()

@router.get("/test-auth/{seller_id}")
def test_magalu_auth(seller_id: str, db: Session = Depends(get_db)):
    """Rota de diagnóstico seguindo o novo prefixo."""
    try:
        get_valid_magalu_access_token(db, seller_id)
        return {"status": "success", "token_valido": True}
    except Exception as e:
        return {"status": "error", "message": str(e)}