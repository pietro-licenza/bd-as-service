from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.entities import ScrapingLog

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    Retorna estatísticas de custos e tokens filtradas por período.
    """
    # Define o range de datas padrão (últimos 7 dias) se não houver filtro
    if start_date:
        s_dt = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        s_dt = datetime.now() - timedelta(days=7)
        
    if end_date:
        # Ajusta para o final do dia (23:59:59)
        e_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    else:
        e_dt = datetime.now()

    # 1. Totais Gerais no período
    totals = db.query(
        func.sum(ScrapingLog.total_cost_brl).label("total_cost"),
        func.sum(ScrapingLog.total_tokens).label("total_tokens"),
        func.count(ScrapingLog.id).label("total_requests")
    ).filter(ScrapingLog.created_at.between(s_dt, e_dt)).first()

    # 2. Gastos por Loja (Gráfico de Pizza)
    costs_by_store = db.query(
        ScrapingLog.loja,
        func.sum(ScrapingLog.total_cost_brl).label("cost")
    ).filter(ScrapingLog.created_at.between(s_dt, e_dt)).group_by(ScrapingLog.loja).all()

    # 3. Histórico Diário (Gráfico de Barras)
    history = db.query(
        func.date(ScrapingLog.created_at).label("date"),
        func.sum(ScrapingLog.total_cost_brl).label("cost")
    ).filter(ScrapingLog.created_at.between(s_dt, e_dt))\
     .group_by(func.date(ScrapingLog.created_at))\
     .order_by(func.date(ScrapingLog.created_at)).all()

    return {
        "summary": {
            "total_cost": float(totals.total_cost or 0),
            "total_tokens": int(totals.total_tokens or 0),
            "total_requests": int(totals.total_requests or 0)
        },
        "by_store": {item.loja: float(item.cost) for item in costs_by_store},
        "history": [{"date": str(item.date), "cost": float(item.cost)} for item in history]
    }