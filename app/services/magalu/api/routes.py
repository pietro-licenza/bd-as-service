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
    """Recebe notificações e salva no banco dinamicamente"""
    data = await request.json()
    logger.info(f"🔔 WEBHOOK MAGALU RECEBIDO: {data}")
    
    if "challenge" in data:
        return {"challenge": data["challenge"]}

    tenant_id = data.get("tenant_id") or settings.MAGALU_TENANT_ID

    resource_path = data.get("resource") or data.get("data", {}).get("resource")

    if resource_path and "orders" in resource_path:
        try:
            # CORREÇÃO: Extrair apenas o ID numérico do final da string
            # Isso evita o erro de URL duplicada no get_magalu_order_details
            order_id = resource_path.split('?')[0].split('/')[-1]
            
            logger.info(f"🔍 Processando Pedido Magalu: {order_id}")
            # 1. Obter ou renovar token automaticamente
            token = get_valid_magalu_access_token(db, tenant_id)
            
            # 2. Buscar detalhes usando apenas o ID
            full_data = get_magalu_order_details(order_id, token, tenant_id)
            
            if full_data:
                # Normalização de ID e Status
                ext_id = str(full_data.get("code") or order_id)
                raw_status = full_data.get("status")
                status_final = "paid" if raw_status == "approved" else raw_status

                # Cálculo do valor
                total_raw = full_data.get('amounts', {}).get('total', 0)
                norm = full_data.get('amounts', {}).get('normalizer', 100)
                total_final = float(total_raw) / norm

                # Buscar slug da loja
                creds = db.query(MagaluCredential).filter(MagaluCredential.seller_id == tenant_id).first()
                store_slug = creds.store_slug if creds else "brazil_direct"

                # UPSERT
                existing_order = db.query(Order).filter(Order.external_id == ext_id).first()
                if existing_order:
                    existing_order.status = status_final
                    existing_order.total_amount = total_final
                    existing_order.raw_data = full_data
                else:
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
        except Exception as e:
            logger.error(f"💥 Erro no webhook Magalu: {str(e)}")
            db.rollback()
    
    return {"status": "success"}

@router.get("/sync-orders")
async def sync_magalu_orders(
    manual_id: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sincronização manual"""
    tenant_id = settings.MAGALU_TENANT_ID
    token = get_valid_magalu_access_token(db, tenant_id)
    
    ids_to_process = [manual_id] if manual_id else []
    
    if not manual_id:
        date_from = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        url = "https://api.magalu.com/seller/v1/orders"
        headers = {'Authorization': f'Bearer {token}', 'X-Tenant-Id': tenant_id}
        resp = requests.get(url, headers=headers, params={"created_at_from": date_from})
        if resp.status_code == 200:
            ids_to_process = [o['id'] for o in resp.json().get('orders', [])]

    count = 0
    for pid in ids_to_process:
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
async def list_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Order).filter(Order.marketplace == "magalu")
    if current_user.loja_permissao != "todas":
        query = query.filter(Order.store_slug == current_user.loja_permissao)

    return query.order_by(Order.created_at.desc()).all()

# Callback para autenticação (se necessário)
@router.get("/callback")
async def magalu_callback(code: str):
    """Rota temporária para capturar o código de autorização"""
    return {
        "status": "sucesso", 
        "message": "Código capturado! Copie o valor abaixo e mande para o chat.",
        "code": code
    }