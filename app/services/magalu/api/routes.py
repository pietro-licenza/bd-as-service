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

@router.get("/sync-orders")
async def sync_magalu_orders(
    manual_id: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sincronização manual via API ou Dashboard"""
    tenant_id = settings.MAGALU_TENANT_ID
    token = get_valid_magalu_access_token(db, tenant_id)
    
    ids_to_process = [manual_id] if manual_id else []
    
    # Se não passou ID manual, busca os recentes (Listagem)
    if not manual_id:
        date_from = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
        url = "https://api.magalu.com/seller/v1/orders"
        headers = {'Authorization': f'Bearer {token}', 'X-Tenant-Id': tenant_id}
        resp = requests.get(url, headers=headers, params={"created_at_from": date_from})
        if resp.status_code == 200:
            ids_to_process = [o['id'] for o in resp.json().get('orders', [])]

    count = 0
    for pid in ids_to_process:
        full_data = get_magalu_order_details(pid, token, tenant_id)
        if full_data:
            ext_id = str(full_data.get("id"))
            total_final = float(full_data.get('amounts', {}).get('total', 0)) / 100
            
            existing = db.query(Order).filter(Order.external_id == ext_id).first()
            if not existing:
                new_o = Order(
                    marketplace="magalu", external_id=ext_id, seller_id=tenant_id,
                    store_slug="brazil_direct", total_amount=total_final,
                    status=full_data.get("status"), raw_data=full_data
                )
                db.add(new_o)
                count += 1
    
    db.commit()
    return {"status": "success", "processed": len(ids_to_process), "new": count}

@router.post("/notifications")
async def magalu_webhook_receiver(request: Request, db: Session = Depends(get_db)):
    """Recebe notificações em tempo real e salva no banco"""
    data = await request.json()
    
    # Responder ao challenge de validação da Magalu
    if "challenge" in data:
        return {"challenge": data["challenge"]}

    # Se não vier tenant_id na notificação, usamos o padrão da Brazil Direct
    tenant_id = data.get("tenant_id") or settings.MAGALU_TENANT_ID
    resource_id = data.get("resource") # ID ou Número do pedido

    if resource_id:
        try:
            logger.info(f"📥 Webhook Magalu recebido: Recurso {resource_id}")
            
            # 1. Obter token válido
            token = get_valid_magalu_access_token(db, tenant_id)
            
            # 2. Buscar detalhes completos do pedido
            full_data = get_magalu_order_details(resource_id, token, tenant_id)
            
            if full_data:
                # 3. Extrair ID Técnico e tratar valores
                # Usamos o ID UUID como chave única no banco para evitar duplicados
                ext_id = str(full_data.get("id"))
                
                total_raw = full_data.get('amounts', {}).get('total', 0)
                norm = full_data.get('amounts', {}).get('normalizer', 100)
                total_final = float(total_raw) / norm

                # 4. Verificar se o pedido já existe (UPSERT)
                existing_order = db.query(Order).filter(Order.external_id == ext_id).first()

                if existing_order:
                    # Atualiza o status e os dados brutos
                    existing_order.status = full_data.get("status", "approved")
                    existing_order.total_amount = total_final
                    existing_order.raw_data = full_data
                    logger.info(f"🔄 Pedido {ext_id} atualizado no banco.")
                else:
                    # Cria um novo registro
                    new_order = Order(
                        marketplace="magalu",
                        external_id=ext_id,
                        seller_id=tenant_id,
                        store_slug="brazil_direct",
                        total_amount=total_final,
                        status=full_data.get("status", "approved"),
                        raw_data=full_data
                    )
                    db.add(new_order)
                    logger.info(f"✅ Novo pedido {ext_id} inserido no banco.")
                
                db.commit()
            else:
                logger.warning(f"⚠️ Não foi possível obter detalhes do pedido {resource_id}")
                
        except Exception as e:
            logger.error(f"💥 Erro ao processar webhook Magalu: {str(e)}")
            db.rollback() # Reverte em caso de erro no banco
    
    return {"status": "success"}

@router.get("/orders")
async def list_orders(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Lista as ordens salvas para o Dashboard"""
    query = db.query(Order).filter(Order.marketplace == "magalu")
    if current_user.loja_permissao != "todas":
        query = query.filter(Order.store_slug == current_user.loja_permissao)
    return query.order_by(Order.created_at.desc()).all()