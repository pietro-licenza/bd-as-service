# app/api/routes/monitoring.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.entities import MonitoringTerm, MonitoredProduct, StockHistory, User
from app.models.schemas import MonitoringTermCreate, MonitoringTermResponse
from app.api.auth import get_current_user

# Serviço de monitoramento de estoque da Leroy Merlin
from app.services.leroy_merlin.scraper.monitoring_service import LeroyMonitoringService

router = APIRouter(tags=["Monitoring"])

# --- ROTAS DE GESTÃO DE TERMOS ---

@router.post("/terms", response_model=MonitoringTermResponse)
def create_monitoring_term(
    term_in: MonitoringTermCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cadastra um novo termo para monitoramento."""
    existing = db.query(MonitoringTerm).filter(
        MonitoringTerm.term == term_in.term,
        MonitoringTerm.marketplace == term_in.marketplace
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Este termo já está sendo monitorado.")

    new_term = MonitoringTerm(**term_in.model_dump())
    db.add(new_term)
    db.commit()
    db.refresh(new_term)
    return new_term

@router.get("/terms", response_model=List[MonitoringTermResponse])
def list_monitoring_terms(
    marketplace: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista os termos cadastrados."""
    query = db.query(MonitoringTerm)
    if marketplace:
        query = query.filter(MonitoringTerm.marketplace == marketplace)
    return query.all()

@router.delete("/terms/{term_id}")
def delete_term(
    term_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove um termo do monitoramento."""
    term = db.query(MonitoringTerm).filter(MonitoringTerm.id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Termo não encontrado")
    
    db.delete(term)
    db.commit()
    return {"status": "success", "message": "Termo removido com sucesso"}

# --- ROTAS DE EXECUÇÃO E INTELIGÊNCIA ---

@router.post("/sync")
def trigger_monitoring_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Dispara manualmente a varredura de estoque."""
    try:
        processed_count = LeroyMonitoringService.run_sync(db)
        return {
            "status": "success",
            "message": f"Sincronização concluída. {processed_count} registros salvos."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na sincronização: {str(e)}")

@router.get("/dashboard-data/{term_id}")
def get_dashboard_data(
    term_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna dados mastigados para o Front-end:
    - Summary (Cards)
    - Products List (Grid Interativo)
    """
    # 1. Busca o termo alvo
    term_obj = db.query(MonitoringTerm).filter(MonitoringTerm.id == term_id).first()
    if not term_obj:
        raise HTTPException(status_code=404, detail="Termo não encontrado")

    # 2. Busca todos os produtos vinculados a esse marketplace e termo
    # Usamos o nome do produto para filtrar o que pertence a esse termo
    products = db.query(MonitoredProduct).filter(
        MonitoredProduct.marketplace == term_obj.marketplace,
        MonitoredProduct.name.ilike(f"%{term_obj.term}%")
    ).all()

    grid_data = []
    total_estimated_sales = 0
    out_of_stock_count = 0
    top_mover = {"name": "Nenhum", "delta": 0}

    for p in products:
        # Pega as duas últimas leituras de estoque
        history = db.query(StockHistory).filter(
            StockHistory.product_internal_id == p.id
        ).order_by(StockHistory.recorded_at.desc()).limit(2).all()

        if not history:
            continue

        latest = history[0]
        previous = history[1] if len(history) > 1 else latest
        
        # Cálculo de Venda (Delta)
        # Se o estoque anterior era maior que o atual, houve "venda"
        delta = previous.stock_count - latest.stock_count
        delta = delta if delta > 0 else 0
        
        # Acumuladores para os Cards
        total_estimated_sales += delta
        if latest.stock_count == 0:
            out_of_stock_count += 1
        
        if delta > top_mover["delta"]:
            top_mover = {"name": p.name, "delta": delta}

        # Status Simplificado para o Front
        status = "disponivel"
        if latest.stock_count == 0:
            status = "esgotado"
        elif latest.stock_count <= 10:
            status = "critico"

        grid_data.append({
            "id": p.id,
            "product_id": p.product_id,
            "name": p.name,
            "image": p.image_url,
            "url": p.url,
            "price": latest.price or 0.0,
            "stock": latest.stock_count,
            "delta": delta,
            "status": status,
            "last_sync": latest.recorded_at
        })

    # Ordena o Grid por quem mais "vendeu" (maior delta)
    grid_data = sorted(grid_data, key=lambda x: x['delta'], reverse=True)

    return {
        "summary": {
            "term": term_obj.term,
            "total_products": len(products),
            "estimated_sales_24h": total_estimated_sales,
            "out_of_stock_count": out_of_stock_count,
            "top_selling_product": top_mover["name"]
        },
        "products": grid_data
    }