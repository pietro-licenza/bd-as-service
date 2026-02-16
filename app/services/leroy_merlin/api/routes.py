import logging
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.services.leroy_merlin.schemas import ProductUrlRequest, ProductData, BatchResponse
from app.services.leroy_merlin.scraper.url_extractor import extract_product_data
from app.services.leroy_merlin.scraper.gemini_client import get_gemini_client
from app.core.config import settings
from app.shared.excel_generator import generate_standard_excel
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import ScrapingLog

logger = logging.getLogger(__name__)

# Configurações Financeiras
COST_INPUT_USD = 0.075 / 1_000_000
COST_OUTPUT_USD = 0.30 / 1_000_000
USD_TO_BRL = 5.10 

router = APIRouter(prefix="/api/leroy-merlin", tags=["Leroy Merlin"])

@router.post("/process-urls/", response_model=BatchResponse)
async def process_product_urls(
    request: ProductUrlRequest, 
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> BatchResponse:
    logger.info(f"🚀 Lote Leroy Merlin: {len(request.urls)} URLs para {user.username}")
    
    gemini_client = get_gemini_client()
    all_products = []
    excel_data = [] 
    total_batch_cost_brl = 0.0
    total_batch_tokens = 0

    for url in request.urls:
        try:
            p_info = extract_product_data(url)
            titulo = p_info.get("titulo", "Produto sem título")
            
            gemini_res = gemini_client.extract_description_from_url(url, titulo)
            usage = gemini_res.get("usage", {"input": 0, "output": 0})
            
            # Cálculos
            c_in = usage["input"] * COST_INPUT_USD * USD_TO_BRL
            c_out = usage["output"] * COST_OUTPUT_USD * USD_TO_BRL
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
                input_cost_brl=c_in,
                output_cost_brl=c_out,
                total_cost_brl=item_cost
            )
            
            all_products.append(p_obj)
            excel_data.append(p_obj.dict())

        except Exception as e:
            logger.error(f"Erro na URL {url}: {e}")
            all_products.append(ProductData(url_original=url, error=str(e)))

    # --- SALVAR LOG NO SUPABASE ---
    if all_products:
        log_entry = ScrapingLog(
            user_id=user.id,
            loja="leroy_merlin",
            url_count=len(request.urls),
            total_tokens=total_batch_tokens,
            total_cost_brl=total_batch_cost_brl
        )
        db.add(log_entry)
        db.commit()

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