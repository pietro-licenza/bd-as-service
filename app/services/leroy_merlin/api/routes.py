import logging
import re
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
USD_TO_BRL = 5.10             # Câmbio base para conversão
PRICE_INPUT_1M_USD = 0.10     # Preço por 1M de tokens de entrada
PRICE_OUTPUT_1M_USD = 0.40    # Preço por 1M de tokens de saída

# Cálculo do preço unitário por token em Reais
TOKEN_IN_PRICE = (PRICE_INPUT_1M_USD / 1_000_000) * USD_TO_BRL
TOKEN_OUT_PRICE = (PRICE_OUTPUT_1M_USD / 1_000_000) * USD_TO_BRL

router = APIRouter(prefix="/api/leroy-merlin", tags=["Leroy Merlin"])
logger = logging.getLogger(__name__)

def apply_packaging_margin(value_str: str, margin: float) -> str:
    """
    Tenta converter a string de dimensão para número (detectando a unidade),
    adiciona a margem e retorna como string formatada.

    Conversões suportadas:
    - Metros (m)  → converte para cm antes de somar (ex: "2,55 m" + 7 → "262.00")
    - Centímetros (cm) → soma diretamente
    - Quilogramas (kg) → soma diretamente
    - Valores sem unidade → soma diretamente
    """
    if not value_str:
        return ""
    try:
        s = value_str.strip().lower()
        # Detecta unidade
        is_meters = bool(re.search(r'\bm\b', s) and not re.search(r'\bcm\b', s))
        # Extrai apenas dígitos, vírgula e ponto
        numeric_part = re.sub(r'[^\d,.]', '', value_str).replace(',', '.')
        value_float = float(numeric_part)
        if is_meters:
            value_float = value_float * 100  # converte m → cm
        final_value = value_float + margin
        return f"{final_value:.2f}"
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível aplicar margem ao valor '{value_str}': {e}")
        return value_str

@router.post("/generate-excel/")
async def generate_excel(request: Request):
    """
    Gera Excel com marca alterada para URLs selecionadas.
    Altera o campo Marca e limpa menções na Descrição.
    """
    body = await request.json()
    produtos = body.get('produtos', [])
    alterar_marca_urls = body.get('alterar_marca_urls', [])

    for p in produtos:
        if p.get('url_original') in alterar_marca_urls:
            # 1. Salva a marca original antes de alterar
            marca_original = p.get('marca', '').strip()
            
            # 2. Altera o campo Marca principal
            p['marca'] = 'Brazil Home Living'
            
            # 3. Varredura na Descrição
            if marca_original and marca_original.lower() != 'brazil home living':
                descricao = p.get('descricao', '')
                if descricao:
                    pattern = re.compile(rf'\b{re.escape(marca_original)}\b', re.IGNORECASE)
                    p['descricao'] = pattern.sub('Brazil Home Living', descricao)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_filename = f"leroy_produtos_{timestamp}.xlsx"
    
    # Chama o gerador padrão com os dados já limpos
    generate_standard_excel(produtos, excel_filename, settings.EXPORTS_DIR, "Leroy Merlin", "00A859")
    
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
    Processa URLs da Leroy Merlin com captura de tokens reais e cálculo de 
    dimensões do produto embalado (+7cm nas medidas e +2kg no peso).
    """
    logger.info(f"🚀 Lote Leroy Merlin: {len(request.urls)} URLs para {user.username}")
    
    gemini_client = get_gemini_client()
    all_products = []
    excel_data = [] 
    total_batch_cost_brl = 0.0
    total_batch_tokens = 0

    for url in request.urls:
        try:
            # Passo 1: Extração de dados brutos da URL (inclui dimensões via regex)
            p_info = extract_product_data(url)
            titulo = p_info.get("titulo", "Produto sem título")

            # --- CHAMADA GEMINI: DESCRIÇÃO PROFISSIONAL ---
            gemini_desc_res = gemini_client.extract_description_from_url(url, titulo)
            usage_desc = gemini_desc_res.get("usage", {"input": 0, "output": 0})

            # --- DIMENSÕES VIA REGEX (sem custo de IA) ---
            # "comprimento" tem prioridade; fallback para "profundidade" quando ausente
            comprimento_raw = p_info.get("comprimento") or p_info.get("profundidade", "")

            logger.info(
                f"📐 [DIMENSÕES] {titulo} — "
                f"L:{p_info.get('largura')} C:{comprimento_raw} "
                f"A:{p_info.get('altura')} P:{p_info.get('peso')}"
            )

            # --- LÓGICA DE PRODUTO EMBALADO (SOMAS NO BACKEND) ---
            # Adiciona 7cm em cada medida e 2kg no peso bruto
            largura_final = apply_packaging_margin(p_info.get("largura", ""), 7.0)
            comprimento_final = apply_packaging_margin(comprimento_raw, 7.0)
            altura_final = apply_packaging_margin(p_info.get("altura", ""), 7.0)
            peso_final = apply_packaging_margin(p_info.get("peso", ""), 2.0)
            
            # Reconstrói LxCxA com as novas medidas
            dimensoes_lca_final = ""
            if largura_final and comprimento_final and altura_final:
                dimensoes_lca_final = f"{largura_final}x{comprimento_final}x{altura_final}"

            # --- CONSOLIDAÇÃO DE TOKENS E CÁLCULO FINANCEIRO ---
            total_in = usage_desc["input"]
            total_out = usage_desc["output"]
            
            c_in = total_in * TOKEN_IN_PRICE
            c_out = total_out * TOKEN_OUT_PRICE
            item_cost = c_in + c_out

            total_batch_cost_brl += item_cost
            total_batch_tokens += (total_in + total_out)

            p_obj = ProductData(
                titulo=titulo,
                preco=p_info.get("preco", ""),
                marca=p_info.get("marca", ""),
                modelo=p_info.get("modelo", ""),
                ean=p_info.get("ean", ""),
                descricao=gemini_desc_res.get("descricao", ""),
                # --- NOVOS CAMPOS COM MARGEM DE EMBALAGEM ---
                largura_cm=largura_final,
                comprimento_cm=comprimento_final,
                altura_cm=altura_final,
                dimensoes_lca=dimensoes_lca_final,
                peso_kg=peso_final,
                # ---------------------------------------------
                image_urls=p_info.get("image_urls", []),
                url_original=url,
                input_tokens=total_in,
                output_tokens=total_out,
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

    # Geração do Excel inicial
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