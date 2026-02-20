import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entities import Order, CasasBahiaCredential

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks/casas-bahia", tags=["Casas Bahia Webhook"])

@router.post("/notifications")
async def cb_webhook_receiver(request: Request, db: Session = Depends(get_db)):
    """
    Recebe notificações das Casas Bahia, identifica a loja via seller_id 
    e centraliza na tabela unificada 'orders'.
    """
    try:
        payload = await request.json()
        logger.info(f"🔔 Notificação Casas Bahia recebida.")

        # 1. TRATAMENTO DE CHALLENGE (Se houver validação de URL)
        if "challenge" in payload:
            challenge_val = payload.get("challenge")
            logger.info(f"🛡️ Validando Challenge Casas Bahia: {challenge_val}")
            return {"challenge": challenge_val}

        # 2. EXTRAÇÃO DE DADOS BÁSICOS
        # Nota: Ajustar chaves ('order_id', 'id_pedido') conforme documentação oficial Via
        order_details = payload
        external_id = str(order_details.get("order_id") or order_details.get("id"))
        seller_id = str(order_details.get("seller_id", "desconhecido"))
        
        logger.info(f"📦 Processando Pedido Casas Bahia: #{external_id} | Loja: {seller_id}")

        # 3. BUSCA DINÂMICA DA LOJA NO BANCO
        # Aqui o sistema descobre se o pedido é da 'loja_1' ou 'loja_2'
        creds = db.query(CasasBahiaCredential).filter(
            CasasBahiaCredential.seller_id == seller_id
        ).first()
        
        # Se não achar a credencial, usamos um fallback para não perder o dado
        store_slug = creds.store_slug if creds else "casas_bahia_vendas"

        # 4. MAPEAMENTO DE STATUS E VALORES
        total_amount = float(order_details.get("total_amount") or order_details.get("total_price") or 0)
        cb_status = str(order_details.get("status", "NEW")).lower()

        # 5. LÓGICA DE UPSERT (IGUAL À MAGALU)
        existing_order = db.query(Order).filter(
            Order.external_id == external_id, 
            Order.marketplace == "casas_bahia"
        ).first()

        if existing_order:
            # Atualiza pedido existente
            existing_order.status = "paid" if cb_status in ["approved", "pago"] else cb_status
            existing_order.total_amount = total_amount
            existing_order.raw_data = order_details
            logger.info(f"🔄 Venda CB {external_id} atualizada para: {existing_order.status}")
        else:
            # Cria novo registro
            new_order = Order(
                marketplace="casas_bahia",
                external_id=external_id,
                seller_id=seller_id,
                store_slug=store_slug,
                total_amount=total_amount,
                status="paid" if cb_status in ["approved", "pago"] else cb_status,
                raw_data=order_details
            )
            db.add(new_order)
            logger.info(f"✅ Venda CB {external_id} criada para a organização: {store_slug}")

        db.commit()
        return {"status": "success", "order_id": external_id}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro ao processar Webhook Casas Bahia: {str(e)}")
        # Retornamos 200/Success para evitar que o marketplace fique tentando reenviar erros de processamento interno
        return {"status": "error", "message": str(e)}