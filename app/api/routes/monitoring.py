# app/api/routes/monitoring.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import logging

from app.core.database import get_db
from app.models.entities import MonitoringTerm, MonitoredProduct, StockHistory, User
from app.models.schemas import MonitoringTermCreate, MonitoringTermResponse
from app.api.auth import get_current_user

# Serviços de monitoramento
from app.services.leroy_merlin.scraper.monitoring_service import LeroyMonitoringService
# Nota: Quando criar os serviços de Sodimac/Decathlon, importe-os aqui.

router = APIRouter(tags=["Monitoring"])
logger = logging.getLogger(__name__)

# Mapeamento de Marketplaces -> Serviços
# Facilita a expansão: basta adicionar a nova loja aqui quando o serviço estiver pronto.
MONITORING_SERVICES = {
    "leroy_merlin": LeroyMonitoringService,
    # "sodimac": SodimacMonitoringService, 
    # "decathlon": DecathlonMonitoringService,
}

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
        raise HTTPException(status_code=400, detail="Este termo já está sendo monitorado para esta loja.")

    new_term = MonitoringTerm(**term_in.model_dump())
    db.add(new_term)
    db.commit()
    db.refresh(new_term)
    return new_term

@router.get("/terms", response_model=List[MonitoringTermResponse])
def list_monitoring_terms(
    marketplace: str = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista os termos cadastrados com opção de filtrar por marketplace e status ativo."""
    query = db.query(MonitoringTerm)
    if marketplace:
        query = query.filter(MonitoringTerm.marketplace == marketplace)
    if active_only:
        query = query.filter(MonitoringTerm.is_active == True)
    return query.all()

@router.patch("/terms/{term_id}/toggle")
def toggle_term_status(
    term_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ativa ou desativa um termo de monitoramento."""
    term = db.query(MonitoringTerm).filter(MonitoringTerm.id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Termo não encontrado")
    
    term.is_active = not term.is_active
    db.commit()
    db.refresh(term)
    
    status_text = "ativado" if term.is_active else "desativado"
    return {"status": "success", "message": f"Termo {status_text} com sucesso", "is_active": term.is_active}

@router.delete("/terms/{term_id}")
def delete_term(
    term_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove um termo do monitoramento (use toggle para ativar/desativar)."""
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
    """
    Orquestrador Global: Dispara a varredura para todos os 
    marketplaces que possuem termos ativos cadastrados.
    """
    try:
        # Busca marketplaces que possuem pelo menos um termo ativo
        active_markets = db.query(MonitoringTerm.marketplace).filter(
            MonitoringTerm.is_active == True
        ).distinct().all()

        total_processed = 0
        executed_markets = []

        for (market_name,) in active_markets:
            service = MONITORING_SERVICES.get(market_name)
            if service:
                logger.info(f"🔄 Iniciando sincronização manual para: {market_name}")
                count = service.run_sync(db)
                total_processed += count
                executed_markets.append(market_name)
            else:
                logger.warning(f"⚠️ Serviço não implementado para o marketplace: {market_name}")

        return {
            "status": "success",
            "message": f"Sincronização concluída para {executed_markets}. {total_processed} registros salvos."
        }
    except Exception as e:
        logger.error(f"❌ Erro na sincronização global: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro na sincronização: {str(e)}")

@router.get("/dashboard-data/{term_id}")
def get_dashboard_data(
    term_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna dados processados (vendas e estoque) para o dashboard."""
    term_obj = db.query(MonitoringTerm).filter(MonitoringTerm.id == term_id).first()
    if not term_obj:
        raise HTTPException(status_code=404, detail="Termo não encontrado")

    # Busca todos os produtos do marketplace que têm histórico de estoque
    # (produtos descobertos por este ou outros termos do mesmo marketplace)
    products = db.query(MonitoredProduct).filter(
        MonitoredProduct.marketplace == term_obj.marketplace
    ).all()

    grid_data = []
    total_estimated_sales = 0
    out_of_stock_count = 0
    top_mover = {"name": "Nenhum", "delta": 0}

    for p in products:
        history = db.query(StockHistory).filter(
            StockHistory.product_internal_id == p.id
        ).order_by(StockHistory.recorded_at.desc()).limit(2).all()

        if not history:
            continue

        latest = history[0]
        previous = history[1] if len(history) > 1 else latest
        
        delta = previous.stock_count - latest.stock_count
        delta = delta if delta > 0 else 0
        
        total_estimated_sales += delta
        if latest.stock_count == 0:
            out_of_stock_count += 1
        
        if delta > top_mover["delta"]:
            top_mover = {"name": p.name, "delta": delta}

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

    grid_data = sorted(grid_data, key=lambda x: x['delta'], reverse=True)

    return {
        "summary": {
            "term": term_obj.term,
            "marketplace": term_obj.marketplace,
            "total_products": len(grid_data),  # Conta apenas produtos com histórico
            "estimated_sales_24h": total_estimated_sales,
            "out_of_stock_count": out_of_stock_count,
            "top_selling_product": top_mover["name"]
        },
        "products": grid_data
    }