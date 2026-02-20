# app/services/magalu/api/routes.py
from fastapi import APIRouter, Depends, Request, Header
from sqlalchemy.orm import Session
import logging
from app.core.database import get_db
from app.models.entities import Order, MagaluCredential
from app.services.magalu.utils import get_valid_magalu_access_token, get_magalu_order_details

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/notifications")
async def magalu_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint para receber notificações da Magalu (Webhooks).
    """
    try:
        data = await request.json()
        logger.info(f"📩 Nova notificação Magalu recebida: {data}")

        # 1. Tratamento do Challenge (Segurança Magalu)
        if "challenge" in data:
            challenge_value = data["challenge"]
            logger.info(f"🛡️ Validando Challenge Magalu: {challenge_value}")
            return {"challenge": challenge_value}

        # 2. Extração de Metadados
        topic = data.get("topic")
        tenant_id = data.get("tenant_id")  # Importante para o header X-Tenant-ID
        resource_uri = data.get("resource")

        # Filtro: Só processamos novos pedidos (created_order)
        if topic != "created_order" or not resource_uri:
            logger.info(f"⏩ Ignorando tópico: {topic}")
            return {"status": "ignored"}

        # 3. Identificar o Seller pelo Tenant ID
        # No Magalu, o sub do token é o seller_id que usamos no banco
        # Vamos buscar as credenciais vinculadas a este tenant
        creds = db.query(MagaluCredential).filter(
            (MagaluCredential.seller_id == tenant_id) | 
            (MagaluCredential.seller_id == '3f9afe2b-c52e-4bbe-b50b-d315ccab4970') # Fallback para seu seller fixo se necessário
        ).first()

        if not creds:
            logger.error(f"❌ Seller não encontrado para o tenant_id: {tenant_id}")
            return {"status": "error", "message": "Seller not found"}

        seller_id = creds.seller_id

        # 4. Obter Token Válido (Renova se necessário)
        access_token = get_valid_magalu_access_token(db, seller_id)

        # 5. Buscar Detalhes Completos do Pedido (Agora enviando o tenant_id)
        order_details = get_magalu_order_details(resource_uri, access_token, tenant_id)

        if not order_details:
            return {"status": "error", "message": "Could not fetch order details"}

        # 6. Salvar no Banco de Dados (Supabase)
        # Adaptando os campos do JSON da Magalu para seu modelo de Order
        new_order = Order(
            external_order_id=str(order_details.get("id")),
            seller_id=seller_id,
            source="magalu",
            total_amount=order_details.get("total_amount"),
            status=order_details.get("status"),
            customer_name=order_details.get("customer", {}).get("name"),
            raw_json=order_details # Guarda o JSON completo para segurança
        )

        db.add(new_order)
        db.commit()

        logger.info(f"✅ Pedido {new_order.external_order_id} salvo com sucesso no banco!")
        return {"status": "success", "order_id": new_order.external_order_id}

    except Exception as e:
        logger.error(f"💥 Erro ao processar webhook Magalu: {str(e)}")
        return {"status": "error", "message": str(e)}

# Rota de teste para saúde do token (Heartbeat)
@router.get("/test-auth/{seller_id}")
def test_magalu_auth(seller_id: str, db: Session = Depends(get_db)):
    try:
        token = get_valid_magalu_access_token(db, seller_id)
        return {"status": "success", "token_valido": True}
    except Exception as e:
        return {"status": "error", "message": str(e)}