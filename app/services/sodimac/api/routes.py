"""
API routes for Sodimac product processing service with cost tracking.
Versão Final: Integração total com Supabase, Segurança e Relatório Excel.
"""
import logging
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

# Configurações de Custo (Gemini 1.5 Flash / Flash-Lite)
COST_INPUT_USD = 0.075 / 1_000_000
COST_OUTPUT_USD = 0.30 / 1_000_000
USD_TO_BRL = 5.10 

router = APIRouter(prefix="/api/sodimac", tags=["Sodimac"])

@router.post("/process-urls/", response_model=BatchResponse)
async def process_product_urls(
    request: ProductUrlRequest,
    current_user = Depends(get_current_user), # Exige Login
    db: Session = Depends(get_db)             # Conexão com Supabase
) -> BatchResponse:
    """
    Processa URLs da Sodimac, gera descrições via IA, calcula investimento real
    e salva o log de uso no Supabase.
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

            # Passo 1: Extração HTML/Regex
            product_info = extract_product_data(url)
            
            # Passo 2: Gemini para Descrição e Captura de Tokens
            titulo = product_info.get("titulo", "Produto Sodimac")
            gemini_res = gemini_client.extract_description_from_url(url, titulo)
            
            descricao = gemini_res.get("descricao", "")
            usage = gemini_res.get("usage", {"input": 0, "output": 0})
            
            # Passo 3: Cálculo Financeiro Detalhado
            c_in = usage["input"] * COST_INPUT_USD * USD_TO_BRL
            c_out = usage["output"] * COST_OUTPUT_USD * USD_TO_BRL
            item_cost = c_in + c_out
            
            # Acumuladores para o Log
            total_cost_batch_brl += item_cost
            total_tokens_batch += (usage["input"] + usage["output"])

            # Passo 4: Montagem do Objeto de Resposta
            product_response = ProductData(
                titulo=titulo,
                preco=product_info.get("preco", ""),
                marca=product_info.get("marca", ""),
                ean=product_info.get("ean", ""),
                descricao=descricao,
                image_urls=product_info.get("image_urls", []),
                url_original=url,
                input_tokens=usage["input"],
                output_tokens=usage["output"],
                input_cost_brl=c_in,
                output_cost_brl=c_out,
                total_cost_brl=item_cost,
                error=None if product_info.get("success") else product_info.get("error")
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

    # --- NOVO: SALVAR LOG NO SUPABASE ---
    if all_products:
        try:
            log_entry = ScrapingLog(
                user_id=current_user.id, # ID do Victor ou Admin
                loja="sodimac",
                url_count=len(request.urls),
                total_tokens=total_tokens_batch,
                total_cost_brl=total_cost_batch_brl
            )
            db.add(log_entry)
            db.commit()
            logger.info(f"📊 Log Sodimac salvo no Supabase para {current_user.username}")
        except Exception as db_err:
            db.rollback()
            logger.error(f"❌ Falha ao salvar log no banco: {db_err}")

    # Passo 5: Geração do Relatório Excel
    excel_url = None
    if excel_data:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"sodimac_produtos_{timestamp}.xlsx"
            
            generate_standard_excel(
                products_data=excel_data,
                filename=excel_filename,
                exports_dir=settings.EXPORTS_DIR,
                service_name="Sodimac",
                header_color="FF6B35"  # Laranja Sodimac
            )
            excel_url = f"/exports/{excel_filename}"
            logger.info(f"✅ Excel gerado com sucesso: {excel_url}")
        except Exception as e:
            logger.error(f"❌ Erro ao gerar Excel Sodimac: {str(e)}")

    logger.info(f"✅ Lote Sodimac finalizado. Investimento Total: R$ {total_cost_batch_brl:.4f}")
    
    return BatchResponse(
        products=all_products,
        total_products=len(all_products),
        excel_download_url=excel_url,
        total_cost_batch_brl=total_cost_batch_brl
    )