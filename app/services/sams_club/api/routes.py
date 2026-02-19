import os
import json
import logging
import tempfile
import shutil
import re
from typing import List
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Request, Depends
from sqlalchemy.orm import Session

# Importações de Schemas e Clients
from app.services.sams_club.schemas import BatchResponse, BatchProductResponse
from app.services.sams_club.image_parser.gemini_client import GeminiClient 
from app.shared.excel_generator import generate_standard_excel

# Importações do Core (Segurança e Banco)
from app.core.config import settings
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.entities import ScrapingLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sams-club", tags=["Sam's Club"])

# --- CONFIGURAÇÃO DE CUSTO REAL POR TOKEN (GEMINI 1.5 FLASH / LITE) ---
#
USD_TO_BRL = 5.10             # Câmbio comercial para conversão
PRICE_INPUT_1M_USD = 0.075     # Preço por 1M de tokens de entrada
PRICE_OUTPUT_1M_USD = 0.30     # Preço por 1M de tokens de saída

# Cálculo do preço unitário por token em Reais
TOKEN_IN_PRICE = (PRICE_INPUT_1M_USD / 1_000_000) * USD_TO_BRL
TOKEN_OUT_PRICE = (PRICE_OUTPUT_1M_USD / 1_000_000) * USD_TO_BRL

@router.post("/process-batch/", response_model=BatchResponse)
async def process_batch(
    request: Request, 
    files: List[UploadFile] = File(...),
    user = Depends(get_current_user), 
    db: Session = Depends(get_db)
) -> BatchResponse:
    """
    Processa lote Sam's Club com captura de Usage Metadata real da Google.
    Cálculo 100% baseado em tokens reportados pela API.
    """
    logger.info(f"🚀 Lote Sam's Club recebido de {user.username}")
    
    product_groups = {}
    for file in files:
        match = re.match(r'(product[_\s]?\d+)', file.filename.lower())
        if match:
            pid = match.group(1).replace(' ', '_')
            if pid not in product_groups: product_groups[pid] = []
            product_groups[pid].append(file)
    
    form = await request.form()
    gemini_client = GeminiClient()
    all_products = []
    
    total_batch_tokens = 0
    total_batch_cost_brl = 0.0

    for i, (product_id, product_files) in enumerate(product_groups.items(), 1):
        temp_dir = tempfile.mkdtemp()
        temp_paths = []
        try:
            for file in product_files:
                content = await file.read()
                t_path = Path(temp_dir) / file.filename
                with open(t_path, "wb") as f: f.write(content)
                from app.shared.gemini_client import convert_mpo_to_jpeg
                conv_p, _ = convert_mpo_to_jpeg(str(t_path))
                temp_paths.append(conv_p)

            remove_bg = form.get(f'remove_background_{i}') == 'true'
            generate_contextual = form.get(f'generate_contextual_{i}') == 'true'

            # 1. Extração de Dados (Captura tokens reais de entrada/saída)
            result = gemini_client.step1_extract_product_data(temp_paths)
            u1 = result.get("usage", {"input": 0, "output": 0})
            infos = result.get("infos_extraidas", {})
            p_name = infos.get("nome", "produto")

            gen_urls = []
            u2, u3 = {"input": 0, "output": 0}, {"input": 0, "output": 0}
            local_clean_path = None

            # 2. Remoção de Fundo (Captura tokens reais)
            if remove_bg and not result.get("error"):
                idx = int(infos.get("foto_ideal_index", 1)) - 1
                if 0 <= idx < len(temp_paths):
                    gen_res = gemini_client.step2_generate_background_removed_image(temp_paths[idx])
                    if gen_res.get("public_urls"):
                        gen_urls.extend(gen_res["public_urls"])
                        local_clean_path = gen_res.get("local_path")
                    u2 = gen_res.get("usage", {"input": 0, "output": 0})

            # 3. Geração Ambientada (Captura tokens reais)
            if generate_contextual and not result.get("error"):
                source_img = local_clean_path if local_clean_path else temp_paths[0]
                ctx_res = gemini_client.step3_generate_contextual_image(source_img, p_name)
                if ctx_res.get("public_urls"):
                    gen_urls.extend(ctx_res["public_urls"])
                u3 = ctx_res.get("usage", {"input": 0, "output": 0})

            # --- CÁLCULO FINANCEIRO BASEADO EXCLUSIVAMENTE NA API ---
            # Somamos todos os tokens de entrada e saída das 3 etapas
            t_in = u1["input"] + u2["input"] + u3["input"]
            t_out = u1["output"] + u2["output"] + u3["output"]
            
            # Custo matemático puro
            c_in = t_in * TOKEN_IN_PRICE
            c_out = t_out * TOKEN_OUT_PRICE
            item_cost = c_in + c_out

            total_batch_tokens += (t_in + t_out)
            total_batch_cost_brl += item_cost

            if local_clean_path and os.path.exists(local_clean_path):
                os.remove(local_clean_path)

            product_response = BatchProductResponse(
                product_id=product_id, num_images=len(product_files),
                filenames=[f.filename for f in product_files], prompt="Análise e Geração",
                gemini_response=result.get("gemini_response", "{}"),
                generated_images_urls=gen_urls, error=result.get("error"),
                input_tokens=int(t_in), input_cost_brl=round(c_in, 6),
                output_tokens=int(t_out), output_cost_brl=round(c_out, 6),
                total_cost_brl=round(item_cost, 6)
            )
            all_products.append(product_response.model_dump())
            
        finally: 
            shutil.rmtree(temp_dir, ignore_errors=True)

    if all_products:
        try:
            log_entry = ScrapingLog(
                user_id=user.id, loja="sams_club",
                url_count=len(all_products), total_tokens=total_batch_tokens,
                total_cost_brl=total_batch_cost_brl
            )
            db.add(log_entry)
            db.commit()
        except Exception as db_err:
            db.rollback()
            logger.error(f"❌ Erro log Sam's: {db_err}")

    return BatchResponse(products=all_products, total_products=len(all_products))