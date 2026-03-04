# app/services/magalu/api/routes.py
import logging
import requests
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.models.entities import Order, MagaluCredential, User
from app.api.auth import get_current_user
from app.services.magalu.utils import get_valid_magalu_access_token, get_magalu_order_details
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks/magalu", tags=["Magalu Webhook"])

@router.post("/notifications")
async def magalu_webhook_receiver(request: Request, db: Session = Depends(get_db)):
    """
    Recebe notificações em tempo real.
    Ajustado para logar o payload completo e ser flexível com os tópicos da Magalu.
    """
    try:
        payload = await request.json()
        
        # 1. LOG CRÍTICO: Visualização do JSON bruto no Google Cloud Logs
        logger.info(f"🔔 WEBHOOK MAGALU RECEBIDO: {payload}")
        
        # Resposta ao desafio de URL (Challenge) que a Magalu faz ocasionalmente
        if "challenge" in payload:
            return {"challenge": payload["challenge"]}

        topic = payload.get("topic", "")
        resource_id = payload.get("resource")
        tenant_id = payload.get("tenant_id") or settings.MAGALU_TENANT_ID

        # 2. FILTRO FLEXÍVEL: Aceita 'orders', 'order_status_changed', etc.
        if "order" not in topic.lower() and topic != "":
            logger.warning(f"⚠️ Tópico ignorado pelo filtro: {topic}")
            return {"status": "ignored", "topic": topic}

        if resource_id:
            logger.info(f"📦 Iniciando processamento do recurso: {resource_id}")
            
            # 3. Buscar a credencial para identificar a loja (store_slug)
            creds = db.query(MagaluCredential).filter(MagaluCredential.seller_id == tenant_id).first()
            store_slug = creds.store_slug if creds else "brazil_direct"
            
            # 4. Obter token e detalhes completos do pedido
            token = get_valid_magalu_access_token(db, tenant_id)
            full_data = get_magalu_order_details(resource_id, token, tenant_id)
            
            if full_data:
                # Normalização do ID (Code é o ID amigável 1514...)
                ext_id = str(full_data.get("code") or full_data.get("id"))

                # Normalização do Status (Mapeia 'approved' para 'paid' para padrão do Dashboard)
                raw_status = full_data.get("status", "unknown")
                status_final = "paid" if raw_status in ["approved", "paid"] else raw_status

                # Cálculo financeiro (Normalizer 100 converte centavos para Reais)
                amounts = full_data.get('amounts', {})
                total_raw = amounts.get('total', 0)
                norm = amounts.get('normalizer', 100)
                total_final = float(total_raw) / norm

                # UPSERT: Atualiza se já existir, cria se for novo
                existing_order = db.query(Order).filter(Order.external_id == ext_id).first()

                if existing_order:
                    logger.info(f"🔄 Atualizando pedido existente: {ext_id}")
                    existing_order.status = status_final
                    existing_order.total_amount = total_final
                    existing_order.raw_data = full_data
                else:
                    logger.info(f"✨ Criando novo pedido Magalu: {ext_id}")
                    new_order = Order(
                        marketplace="magalu",
                        external_id=ext_id,
                        seller_id=tenant_id,
                        store_slug=store_slug,
                        total_amount=total_final,
                        status=status_final,
                        raw_data=full_data
                    )
                    db.add(new_order)
                
                db.commit()
                logger.info(f"✅ Pedido {ext_id} processado com sucesso.")
            else:
                logger.error(f"❌ Não foi possível obter detalhes para o recurso: {resource_id}")

    except Exception as e:
        logger.error(f"💥 Erro catastrófico no webhook Magalu: {str(e)}")
        db.rollback()
    
    # Retornamos sempre 200 para a Magalu não ficar tentando re-enviar em loop
    return {"status": "success"}

@router.get("/sync-orders")
async def sync_magalu_orders(
    manual_id: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sincronização manual via API ou Dashboard para resgatar vendas antigas"""
    tenant_id = settings.MAGALU_TENANT_ID
    token = get_valid_magalu_access_token(db, tenant_id)
    
    ids_to_process = [manual_id] if manual_id else []
    
    if not manual_id:
        # Busca pedidos dos últimos 30 dias para garantir
        date_from = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        url = "https://api.magalu.com/seller/v1/orders"
        headers = {'Authorization': f'Bearer {token}', 'X-Tenant-Id': tenant_id}
        resp = requests.get(url, headers=headers, params={"created_at_from": date_from})
        if resp.status_code == 200:
            ids_to_process = [o['id'] for o in resp.json().get('orders', [])]

    count = 0
    for pid in ids_to_process:
        # A API de listagem retorna IDs longos, o get_details aceita o resource ou o ID
        full_data = get_magalu_order_details(pid, token, tenant_id)
        if full_data:
            ext_id = str(full_data.get("code") or full_data.get("id"))
            total_final = float(full_data.get('amounts', {}).get('total', 0)) / 100
            
            existing = db.query(Order).filter(Order.external_id == ext_id).first()
            if not existing:
                new_o = Order(
                    marketplace="magalu", external_id=ext_id, seller_id=tenant_id,
                    store_slug="brazil_direct", total_amount=total_final,
                    status="paid" if full_data.get("status") == "approved" else full_data.get("status"),
                    raw_data=full_data
                )
                db.add(new_o)
                count += 1
    
    db.commit()
    return {"status": "success", "processed": len(ids_to_process), "new": count}

@router.get("/orders")
async def list_orders(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Lista as ordens salvas filtrando por permissão de loja"""
    query = db.query(Order).filter(Order.marketplace == "magalu")
    if current_user.loja_permissao != "todas":
        query = query.filter(Order.store_slug == current_user.loja_permissao)
    return query.order_by(Order.created_at.desc()).all()
