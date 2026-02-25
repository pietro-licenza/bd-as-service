
import logging
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.services.leroy_merlin.schemas import ProductUrlRequest, ProductData, BatchResponse
from app.services.leroy_merlin.scraper.url_extractor import extract_product_data
from app.services.leroy_merlin.scraper.gemini_client import get_gemini_client
from app.core.config import settings
from app.shared.excel_generator import generate_standard_excel
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import ScrapingLog

# --- CONFIGURAÇÃO DE CUSTO REAL POR TOKEN (GEMINI 2.0 FLASH) ---
#
USD_TO_BRL = 5.10             # Câmbio base para conversão
PRICE_INPUT_1M_USD = 0.10     # Preço por 1M de tokens de entrada
PRICE_OUTPUT_1M_USD = 0.40    # Preço por 1M de tokens de saída

# Cálculo do preço unitário por token em Reais
TOKEN_IN_PRICE = (PRICE_INPUT_1M_USD / 1_000_000) * USD_TO_BRL
TOKEN_OUT_PRICE = (PRICE_OUTPUT_1M_USD / 1_000_000) * USD_TO_BRL

router = APIRouter(prefix="/api/leroy-merlin", tags=["Leroy Merlin"])

@router.post("/generate-excel/")
async def generate_excel(request: Request):
    """
    Gera Excel com marca alterada para URLs selecionadas.
    Recebe JSON com 'produtos' e 'alterar_marca_urls'.
    """
    body = await request.json()
    produtos = body.get('produtos', [])
    alterar_marca_urls = body.get('alterar_marca_urls', [])
    for p in produtos:
        if p.get('url_original') in alterar_marca_urls:
            p['marca'] = 'Brazil Home Living'
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_filename = f"leroy_produtos_{timestamp}.xlsx"
    generate_standard_excel(produtos, excel_filename, settings.EXPORTS_DIR, "Leroy Merlin", "00A859")
    excel_path = f"{settings.EXPORTS_DIR}/{excel_filename}"
    return FileResponse(excel_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=excel_filename)

logger = logging.getLogger(__name__)

@router.post("/process-urls/", response_model=BatchResponse)
async def process_product_urls(
    request: ProductUrlRequest,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> BatchResponse:
    """
    Processa URLs da Leroy Merlin com captura de tokens reais e cálculo financeiro 
    baseado estritamente nos dados fornecidos pela API do Google.
    """
    logger.info(f"🚀 Lote Leroy Merlin: {len(request.urls)} URLs para {user.username}")
    
    gemini_client = get_gemini_client()
    all_products = []
    excel_data = [] 
    total_batch_cost_brl = 0.0
    total_batch_tokens = 0

    for url in request.urls:
        try:
            # Passo 1: Extração de dados brutos da URL (Custo zero de IA aqui)
            p_info = extract_product_data(url)
            titulo = p_info.get("titulo", "Produto sem título")

            # Passo 2: Chamada ao Gemini (Captura tokens reais da resposta)
            gemini_res = gemini_client.extract_description_from_url(url, titulo)
            usage = gemini_res.get("usage", {"input": 0, "output": 0})

            # --- CÁLCULO FINANCEIRO BASEADO EM TOKENS REAIS ---
            # 1. Custo dos Tokens reportados pela API
            c_in = usage["input"] * TOKEN_IN_PRICE
            c_out = usage["output"] * TOKEN_OUT_PRICE
            item_cost = c_in + c_out

            total_batch_cost_brl += item_cost
            total_batch_tokens += (usage["input"] + usage["output"])

            p_obj = ProductData(
                titulo=titulo,
                preco=p_info.get("preco", ""),
                marca=p_info.get("marca", ""),
                ean=p_info.get("ean", ""),
                descricao=gemini_res.get("descricao", ""),
                image_urls=p_info.get("image_urls", []),
                url_original=url,
                input_tokens=usage["input"],
                output_tokens=usage["output"],
                input_cost_brl=round(c_in, 6),
                output_cost_brl=round(c_out, 6),
                total_cost_brl=round(item_cost, 6)
            )

            all_products.append(p_obj)
            excel_data.append(p_obj.dict())

        except Exception as e:
            logger.error(f"Erro na URL {url}: {e}")
            all_products.append(ProductData(url_original=url, error=str(e)))

    # --- SALVAR LOG NO SUPABASE ---
    if all_products:
        try:
            log_entry = ScrapingLog(
                user_id=user.id,
                loja="leroy_merlin",
                url_count=len(request.urls),
                total_tokens=total_batch_tokens,
                total_cost_brl=total_batch_cost_brl
            )
            db.add(log_entry)
            db.commit()
        except Exception as db_err:
            db.rollback()
            logger.error(f"❌ Erro log Leroy: {db_err}")

    # Geração do Excel
    excel_url = None
    if excel_data:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"leroy_produtos_{timestamp}.xlsx"
            generate_standard_excel(excel_data, excel_filename, settings.EXPORTS_DIR, "Leroy Merlin", "00A859")
            excel_url = f"/exports/{excel_filename}"
        except Exception as e:
            logger.error(f"❌ Falha Excel: {e}")

    return BatchResponse(
        products=all_products,
        total_products=len(all_products),
        excel_download_url=excel_url,
        total_cost_batch_brl=total_batch_cost_brl
    )