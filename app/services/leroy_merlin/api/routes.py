import logging
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.services.leroy_merlin.schemas import ProductUrlRequest, ProductData, BatchResponse
from app.services.leroy_merlin.scraper.url_extractor import extract_product_data
from app.services.leroy_merlin.scraper.gemini_client import get_gemini_client
from app.core.config import settings
from app.shared.excel_generator import generate_standard_excel

logger = logging.getLogger(__name__)

# Configurações Financeiras
COST_INPUT_USD = 0.075 / 1_000_000
COST_OUTPUT_USD = 0.30 / 1_000_000
USD_TO_BRL = 5.10 

router = APIRouter(prefix="/api/leroy-merlin", tags=["Leroy Merlin"])

@router.post("/process-urls/", response_model=BatchResponse)
async def process_product_urls(request: ProductUrlRequest) -> BatchResponse:
    logger.info(f"🚀 Lote Leroy Merlin: {len(request.urls)} URLs")
    
    gemini_client = get_gemini_client()
    all_products = []
    excel_data = [] # Lista para o gerador de Excel
    total_batch_cost_brl = 0.0

    for url in request.urls:
        try:
            # 1. Extração de Dados
            p_info = extract_product_data(url)
            titulo = p_info.get("titulo", "Produto sem título")
            
            # 2. IA para Descrição e Custo
            gemini_res = gemini_client.extract_description_from_url(url, titulo)
            usage = gemini_res.get("usage", {"input": 0, "output": 0})
            
            # 3. Cálculos
            c_in = usage["input"] * COST_INPUT_USD * USD_TO_BRL
            c_out = usage["output"] * COST_OUTPUT_USD * USD_TO_BRL
            item_cost = c_in + c_out
            total_batch_cost_brl += item_cost

            # 4. Montagem do Objeto
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

    # --- LÓGICA DO EXCEL (Copiada da Sodimac) ---
    excel_url = None
    if excel_data:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"leroy_produtos_{timestamp}.xlsx"
            
            generate_standard_excel(
                products_data=excel_data,
                filename=excel_filename,
                exports_dir=settings.EXPORTS_DIR,
                service_name="Leroy Merlin",
                header_color="00A859" # Verde Leroy
            )
            excel_url = f"/exports/{excel_filename}"
            logger.info(f"✅ Excel gerado: {excel_url}")
        except Exception as e:
            logger.error(f"❌ Falha ao gerar Excel: {e}")

    return BatchResponse(
        products=all_products,
        total_products=len(all_products),
        excel_download_url=excel_url,
        total_cost_batch_brl=total_batch_cost_brl
    )