import logging
import re  # Importado para a lógica de substituição de texto
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.services.decathlon.schemas import ProductUrlRequest, ProductData, BatchResponse
from app.services.decathlon.scraper.url_extractor import extract_product_data
from app.services.decathlon.scraper.gemini_client import get_gemini_client
from app.core.config import settings
from app.shared.excel_generator import generate_standard_excel
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import ScrapingLog

logger = logging.getLogger(__name__)

# --- CONFIGURAÇÃO DE CUSTO (GEMINI 2.0 FLASH) ---
USD_TO_BRL = 5.10
TOKEN_IN_PRICE = (0.10 / 1_000_000) * USD_TO_BRL
TOKEN_OUT_PRICE = (0.40 / 1_000_000) * USD_TO_BRL

router = APIRouter(prefix="/api/decathlon", tags=["Decathlon"])

@router.post("/generate-excel/")
async def generate_excel(request: Request):
    """
    Gera Excel com marca alterada para URLs selecionadas.
    Altera o campo Marca e limpa menções apenas na Descrição.
    O Título permanece original conforme solicitado.
    """
    body = await request.json()
    produtos = body.get('produtos', [])
    alterar_marca_urls = body.get('alterar_marca_urls', [])
    
    for p in produtos:
        if p.get('url_original') in alterar_marca_urls:
            # 1. Salva a marca original antes de alterar
            marca_original = p.get('marca', '').strip()
            
            # 2. Altera o campo Marca principal (coluna do Excel)
            p['marca'] = 'Brazil Home Living'
            
            # 3. Varredura na Descrição (Apenas se houver marca original e for diferente da nova)
            if marca_original and marca_original.lower() != 'brazil home living':
                descricao = p.get('descricao', '')
                if descricao:
                    # Busca a marca original ignorando maiúsculas/minúsculas e usando word boundaries (\b)
                    pattern = re.compile(rf'\b{re.escape(marca_original)}\b', re.IGNORECASE)
                    p['descricao'] = pattern.sub('Brazil Home Living', descricao)
                    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_filename = f"decathlon_produtos_{timestamp}.xlsx"
    
    # Gera o Excel preservando o Título original, mas limpando Marca e Descrição
    generate_standard_excel(produtos, excel_filename, settings.EXPORTS_DIR, "Decathlon", "0082C3")
    
    excel_path = f"{settings.EXPORTS_DIR}/{excel_filename}"
    return FileResponse(
        excel_path, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        filename=excel_filename
    )


@router.post("/process-urls/", response_model=BatchResponse)
async def process_product_urls(
    request: ProductUrlRequest, 
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> BatchResponse:
    """
    Processa URLs da Decathlon com captura de tokens e geração de descrição profissional.
    """
    logger.info(f"🚀 Lote Decathlon: {len(request.urls)} URLs para {user.username}")
    
    gemini_client = get_gemini_client()
    all_products = []
    excel_data = [] 
    total_batch_cost_brl = 0.0
    total_batch_tokens = 0

    for url in request.urls:
        try:
            # 1. Extração de dados brutos
            p_info = extract_product_data(url)
            if not p_info.get("success"):
                raise Exception(p_info.get("error", "Falha na extração"))

            titulo = p_info.get("titulo", "Produto sem título")
            marca = p_info.get("marca", "")
            modelo = p_info.get("modelo", "Modelo não encontrado")
            ean = p_info.get("ean", "")
            
            # 2. Chamada ao Gemini para Descrição Profissional
            gemini_res = gemini_client.extract_description_from_url(url, titulo)
            
            usage = gemini_res.get("usage", {"input": 0, "output": 0})
            
            # Cálculo de custo
            c_in = usage["input"] * TOKEN_IN_PRICE
            c_out = usage["output"] * TOKEN_OUT_PRICE
            item_cost = c_in + c_out
            
            total_batch_cost_brl += item_cost
            total_batch_tokens += (usage["input"] + usage["output"])

            p_obj = ProductData(
                titulo=titulo,
                preco=p_info.get("preco", ""),
                marca=marca,
                modelo=modelo,
                ean=ean,
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

    # 3. Salvar Log no Banco
    if all_products:
        try:
            log_entry = ScrapingLog(
                user_id=user.id,
                loja="decathlon",
                url_count=len(request.urls),
                total_tokens=total_batch_tokens,
                total_cost_brl=total_batch_cost_brl
            )
            db.add(log_entry)
            db.commit()
        except Exception as db_err:
            db.rollback()
            logger.error(f"❌ Erro log Decathlon: {db_err}")

    # 4. Geração do Excel
    excel_url = None
    if excel_data:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"decathlon_produtos_{timestamp}.xlsx"
            generate_standard_excel(excel_data, excel_filename, settings.EXPORTS_DIR, "Decathlon", "0082C3")
            excel_url = f"/exports/{excel_filename}"
        except Exception as e:
            logger.error(f"❌ Falha Excel: {e}")

    return BatchResponse(
        products=all_products,
        total_products=len(all_products),
        excel_download_url=excel_url,
        total_cost_batch_brl=total_batch_cost_brl
    )