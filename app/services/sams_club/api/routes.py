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

# Importações de Schemas e Clients atualizados
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
# Valores baseados na tabela oficial do Google Cloud Vertex AI / AI Studio
USD_TO_BRL = 5.10             # Câmbio comercial para conversão
PRICE_INPUT_1M_USD = 0.075     # Preço por 1M de tokens de entrada ($)
PRICE_OUTPUT_1M_USD = 0.30     # Preço por 1M de tokens de saída ($)

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
    Cálculo 100% baseado em tokens reportados pela API em todas as etapas.
    """
    logger.info(f"🚀 Lote Sam's Club recebido de {user.username}")
    
    # Agrupamento de arquivos por padrão de nome (product1_, product2_, etc)
    product_groups = {}
    for file in files:
        match = re.match(r'(product[_\s]?\d+)', file.filename.lower())
        if match:
            pid = match.group(1).replace(' ', '_')
            if pid not in product_groups: product_groups[pid] = []
            product_groups[pid].append(file)
    
    form = await request.form()
    gemini_client = GeminiClient()
    all_products_results = []
    
    total_batch_tokens = 0
    total_batch_cost_brl = 0.0

    # Processamento individual de cada produto identificado no lote
    for i, (product_id, product_files) in enumerate(product_groups.items(), 1):
        temp_dir = tempfile.mkdtemp()
        temp_paths = []
        try:
            # Salva arquivos temporários para processamento
            for file in product_files:
                content = await file.read()
                t_path = Path(temp_dir) / file.filename
                with open(t_path, "wb") as f: f.write(content)
                
                # Conversão opcional de formatos específicos (ex: MPO)
                from app.shared.gemini_client import convert_mpo_to_jpeg
                conv_p, _ = convert_mpo_to_jpeg(str(t_path))
                temp_paths.append(conv_p)

            # Identifica flags de processamento extra vindas do frontend
            remove_bg = form.get(f'remove_background_{i}') == 'true'
            generate_contextual = form.get(f'generate_contextual_{i}') == 'true'

            # --- ETAPA 1: EXTRAÇÃO DE DADOS ---
            step1_res = gemini_client.step1_extract_product_data(temp_paths)
            u1 = step1_res.get("usage", {"input": 0, "output": 0})
            infos = step1_res.get("infos_extraidas", {})
            product_name = infos.get("nome", "produto")

            gen_urls = []
            u2, u3 = {"input": 0, "output": 0}, {"input": 0, "output": 0}
            local_clean_path = None

            # --- ETAPA 2: REMOÇÃO DE FUNDO (AJUSTE DE ÍNDICE) ---
            if remove_bg and not step1_res.get("error"):
                # Ajuste robusto: Se a IA mandar 0 ou 1, tratamos como a primeira foto.
                raw_idx = int(infos.get("foto_ideal_index", 1))
                idx = raw_idx - 1 if raw_idx > 0 else 0
                
                if 0 <= idx < len(temp_paths):
                    gen_res = gemini_client.step2_generate_background_removed_image(temp_paths[idx])
                    if gen_res.get("public_urls"):
                        gen_urls.extend(gen_res["public_urls"])
                        local_clean_path = gen_res.get("local_path")
                    u2 = gen_res.get("usage", {"input": 0, "output": 0})

            # --- ETAPA 3: GERAÇÃO AMBIENTADA ---
            if generate_contextual and not step1_res.get("error"):
                source_img = local_clean_path if local_clean_path else temp_paths[0]
                ctx_res = gemini_client.step3_generate_contextual_image(source_img, product_name)
                if ctx_res.get("public_urls"):
                    gen_urls.extend(ctx_res["public_urls"])
                u3 = ctx_res.get("usage", {"input": 0, "output": 0})

            # --- CÁLCULO FINANCEIRO CONSOLIDADO ---
            t_in = u1["input"] + u2["input"] + u3["input"]
            t_out = u1["output"] + u2["output"] + u3["output"]
            
            c_in = t_in * TOKEN_IN_PRICE
            c_out = t_out * TOKEN_OUT_PRICE
            product_total_cost = c_in + c_out

            total_batch_tokens += (t_in + t_out)
            total_batch_cost_brl += product_total_cost

            if local_clean_path and os.path.exists(local_clean_path):
                os.remove(local_clean_path)

            product_response = BatchProductResponse(
                product_id=product_id,
                num_images=len(product_files),
                filenames=[f.filename for f in product_files],
                prompt="Processamento Sam's Club",
                gemini_response=step1_res.get("gemini_response", "{}"),
                generated_images_urls=gen_urls,
                error=step1_res.get("error"),
                input_tokens=int(t_in),
                input_cost_brl=round(c_in, 6),
                output_tokens=int(t_out),
                output_cost_brl=round(c_out, 6),
                total_cost_brl=round(product_total_cost, 6)
            )
            all_products_results.append(product_response.model_dump())
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar produto {product_id}: {str(e)}")
            all_products_results.append({
                "product_id": product_id,
                "num_images": len(product_files),
                "filenames": [f.filename for f in product_files],
                "prompt": "Erro",
                "gemini_response": "{}",
                "error": str(e)
            })
        finally: 
            shutil.rmtree(temp_dir, ignore_errors=True)

    # --- PERSISTÊNCIA DE LOGS NO SUPABASE ---
    if all_products_results:
        try:
            log_entry = ScrapingLog(
                user_id=user.id,
                loja="sams_club",
                url_count=len(all_products_results),
                total_tokens=int(total_batch_tokens),
                total_cost_brl=round(total_batch_cost_brl, 4)
            )
            db.add(log_entry)
            db.commit()
            logger.info(f"📊 Log de custos salvo: R$ {total_batch_cost_brl:.4f}")
        except Exception as db_err:
            db.rollback()
            logger.error(f"❌ Erro ao salvar log: {db_err}")

    return BatchResponse(
        products=all_products_results, 
        total_products=len(all_products_results),
        total_cost_batch_brl=round(total_batch_cost_brl, 4)
    )