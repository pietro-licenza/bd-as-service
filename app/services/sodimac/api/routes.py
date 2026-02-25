"""
API routes for Sodimac product processing service with cost tracking.
Versão Final: Integração total com Supabase, Segurança e Relatório Excel.
"""

from fastapi import Request
from fastapi.responses import FileResponse
import logging
import re  # Importado para o tratamento das URLs de imagem
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

# Importações de Schemas e Scrapers
from app.services.sodimac.schemas import ProductUrlRequest, ProductData, BatchResponse
from app.services.sodimac.scraper.url_extractor import extract_product_data
from app.services.sodimac.scraper.gemini_client import get_gemini_client

# Importações do Core do Sistema
from app.core.config import settings
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.entities import ScrapingLog
from app.shared.excel_generator import generate_standard_excel

logger = logging.getLogger(__name__)

# --- PREÇO REAL POR TOKEN (GOOGLE GEMINI 2.0 FLASH) ---
#
USD_TO_BRL = 5.10 
PRICE_IN = (0.10 / 1_000_000) * USD_TO_BRL  # Entrada: $0.10 por 1M
PRICE_OUT = (0.40 / 1_000_000) * USD_TO_BRL # Saída: $0.40 por 1M

router = APIRouter(prefix="/api/sodimac", tags=["Sodimac"])

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
    excel_filename = f"sodimac_produtos_{timestamp}.xlsx"
    generate_standard_excel(produtos, excel_filename, settings.EXPORTS_DIR, "Sodimac", "FF6B35")
    excel_path = f"{settings.EXPORTS_DIR}/{excel_filename}"
    return FileResponse(excel_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=excel_filename)


@router.post("/process-urls/", response_model=BatchResponse)
async def process_product_urls(
    request: ProductUrlRequest,
    current_user = Depends(get_current_user), # Exige Login
    db: Session = Depends(get_db)             # Conexão com Supabase
) -> BatchResponse:
    """
    Processa URLs da Sodimac, gera descrições via IA, calcula investimento real
    com captura de tokens reais e salva o log de uso no Supabase.
    """
    logger.info(f"🚀 Iniciando lote Sodimac: {len(request.urls)} URLs para {current_user.username}")
    
    if not request.urls:
        raise HTTPException(status_code=400, detail="Nenhuma URL fornecida")

    gemini_client = get_gemini_client()
    all_products = []
    excel_data = []
    total_cost_batch_brl = 0.0
    total_tokens_batch = 0

    for idx, url in enumerate(request.urls, 1):
        try:
            logger.info(f"📊 Processando {idx}/{len(request.urls)}: {url}")

            # Passo 1: Extração HTML/Regex (Custo 0 de IA)
            product_info = extract_product_data(url)
            
            # Passo 2: Gemini para Descrição e Captura de Tokens (REAIS)
            titulo = product_info.get("titulo", "Produto Sodimac")
            gemini_res = gemini_client.extract_description_from_url(url, titulo)
            
            descricao = gemini_res.get("descricao", "")
            usage = gemini_res.get("usage", {"input": 0, "output": 0})
            
            # Passo 3: Cálculo Financeiro 100% baseado nos campos fornecidos pela API
            c_in = usage["input"] * PRICE_IN
            c_out = usage["output"] * PRICE_OUT
            item_cost = c_in + c_out
            
            # Acumuladores para o Log
            total_cost_batch_brl += item_cost
            total_tokens_batch += (usage["input"] + usage["output"])

            # --- TRATAMENTO DE IMAGENS HD ---
            raw_images = product_info.get("image_urls", [])
            hd_images = []
            for img_url in raw_images:
                clean_url = img_url.split(',')[0].strip()
                clean_url = re.sub(r'w=(76|120)', 'w=1036', clean_url)
                hd_images.append(clean_url)

            # Passo 4: Montagem do Objeto de Resposta
            product_response = ProductData(
                titulo=titulo,
                preco=product_info.get("preco", ""),
                marca=product_info.get("marca", ""),
                ean=product_info.get("ean", ""),
                descricao=descricao,
                image_urls=hd_images,
                url_original=url,
                input_tokens=usage["input"],
                output_tokens=usage["output"],
                input_cost_brl=round(c_in, 6),
                output_cost_brl=round(c_out, 6),
                total_cost_brl=round(item_cost, 6),
                error=product_info.get("error") if product_info.get("error") else None
            )
            
            all_products.append(product_response)
            excel_data.append(product_response.dict())
            
        except Exception as e:
            logger.error(f"❌ Erro na URL {url}: {str(e)}")
            all_products.append(ProductData(
                titulo="Erro", 
                preco="", 
                url_original=url, 
                error=str(e)
            ))

    # --- SALVAR LOG NO SUPABASE ---
    if all_products:
        try:
            log_entry = ScrapingLog(
                user_id=current_user.id,
                loja="sodimac",
                url_count=len(request.urls),
                total_tokens=total_tokens_batch,
                total_cost_brl=total_cost_batch_brl
            )
            db.add(log_entry)
            db.commit()
        except Exception as db_err:
            db.rollback()
            logger.error(f"❌ Falha ao salvar log no banco: {db_err}")

    # Passo 5: Geração do Relatório Excel
    excel_url = None
    if excel_data:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"sodimac_produtos_{timestamp}.xlsx"
            generate_standard_excel(excel_data, excel_filename, settings.EXPORTS_DIR, "Sodimac", "FF6B35")
            excel_url = f"/exports/{excel_filename}"
        except Exception as e:
            logger.error(f"❌ Erro Excel Sodimac: {str(e)}")

    return BatchResponse(
        products=all_products,
        total_products=len(all_products),
        excel_download_url=excel_url,
        total_cost_batch_brl=total_cost_batch_brl
    )