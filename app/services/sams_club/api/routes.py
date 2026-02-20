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

# --- CONFIGURAÇÃO DE CUSTO (estimativa para casar com Billing do GCP) ---
# Referências oficiais de pricing:
# - Gemini 2.5 Flash-Lite: preço por token (input/output)
# - Gemini 2.5 Flash: preço por token (input/output)
# - Gemini 2.5 Flash Image: output de imagem custa US$ 30 / 1.000.000 tokens e
#   imagens até 1024x1024 consomem ~1290 tokens por imagem.
#
# Observação: aqui fazemos a estimativa local para que o custo exibido na aplicação
# fique o mais próximo possível do Billing do GCP.

USD_TO_BRL = float(os.getenv("USD_TO_BRL", "5.10"))  # Você pode sobrescrever via env

# Preços em USD por 1M tokens (ou por 1M image output tokens)
PRICING_USD_PER_1M = {
    # Texto (Step 1)
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},

    # Tokens de entrada (texto+imagem) para steps de imagem seguem o preço do 2.5 Flash
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},

    # Geração de imagem (Step 2/3) — output de imagem tem preço próprio
    "gemini-2.5-flash-image": {"image_output": 30.0},
}

def _brl_per_token(usd_per_1m: float) -> float:
    return (usd_per_1m / 1_000_000) * USD_TO_BRL

# Preços unitários em BRL
FLASH_LITE_IN_BRL = _brl_per_token(PRICING_USD_PER_1M["gemini-2.5-flash-lite"]["input"])
FLASH_LITE_OUT_BRL = _brl_per_token(PRICING_USD_PER_1M["gemini-2.5-flash-lite"]["output"])

FLASH_IN_BRL = _brl_per_token(PRICING_USD_PER_1M["gemini-2.5-flash"]["input"])
FLASH_OUT_BRL = _brl_per_token(PRICING_USD_PER_1M["gemini-2.5-flash"]["output"])

FLASH_IMAGE_OUT_BRL = _brl_per_token(PRICING_USD_PER_1M["gemini-2.5-flash-image"]["image_output"])


@router.post("/process-batch/", response_model=BatchResponse)
async def process_batch(
    request: Request, 
    files: List[UploadFile] = File(...),
    user = Depends(get_current_user), 
    db: Session = Depends(get_db)
) -> BatchResponse:
    """
    Processa lote Sam's Club com captura de Usage Metadata real da Google.
    Cálculo baseado em tokens reportados pela API, com regra específica
    para output de imagem (aproximando o Billing do GCP).
    """
    logger.info(f"🚀 Lote Sam's Club recebido de {user.username}")
    
    # Agrupamento de arquivos por padrão de nome (product1_, product2_, etc)
    product_groups = {}
    for file in files:
        match = re.match(r'(product[_\s]?\d+)', file.filename.lower())
        if match:
            pid = match.group(1).replace(' ', '_')
            if pid not in product_groups: 
                product_groups[pid] = []
            product_groups[pid].append(file)

    all_products_results = []
    total_batch_tokens = 0
    total_batch_cost_brl = 0.0

    for product_id, product_files in product_groups.items():
        temp_dir = tempfile.mkdtemp()
        gemini_client = GeminiClient()

        try:
            # Flags vindas do frontend (query params)
            remove_bg = request.query_params.get("remove_bg", "false").lower() == "true"
            generate_contextual = request.query_params.get("generate_contextual", "false").lower() == "true"

            temp_paths = []
            for f in product_files:
                file_path = os.path.join(temp_dir, f.filename)
                with open(file_path, "wb") as buffer:
                    buffer.write(await f.read())
                temp_paths.append(file_path)

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

            # --- CÁLCULO FINANCEIRO CONSOLIDADO (aprox. Billing do GCP) ---
            # Input tokens: usamos prompt_token_count de cada chamada (inclui imagem de entrada quando houver).
            # Output tokens:
            # - Step 1: candidates_token_count (texto)
            # - Step 2/3: image_output_tokens (estimado como 1290 por imagem, se o SDK não trouxer explícito)
            #
            # Custos:
            # - Step 1 (flash-lite): input/output por token
            # - Step 2/3 (flash-image): input por token (flash) + output de imagem por token (image_output)

            # Tokens
            step1_in = int(u1.get("input", 0))
            step1_out_text = int(u1.get("output", 0))

            step2_in = int(u2.get("input", 0))
            step2_out_text = int(u2.get("output", 0))
            step2_out_image = int(u2.get("image_output_tokens", 0))

            step3_in = int(u3.get("input", 0))
            step3_out_text = int(u3.get("output", 0))
            step3_out_image = int(u3.get("image_output_tokens", 0))

            # Para manter compatibilidade, consideramos output total = texto + imagem
            t_in = step1_in + step2_in + step3_in
            t_out = (step1_out_text + step2_out_text + step3_out_text) + (step2_out_image + step3_out_image)

            # Custos por etapa
            c1_in = step1_in * FLASH_LITE_IN_BRL
            c1_out = step1_out_text * FLASH_LITE_OUT_BRL

            # Steps de imagem: input segue Flash; output de imagem segue tabela de image output
            c2_in = step2_in * FLASH_IN_BRL
            c2_out = (step2_out_text * FLASH_OUT_BRL) + (step2_out_image * FLASH_IMAGE_OUT_BRL)

            c3_in = step3_in * FLASH_IN_BRL
            c3_out = (step3_out_text * FLASH_OUT_BRL) + (step3_out_image * FLASH_IMAGE_OUT_BRL)

            c_in = c1_in + c2_in + c3_in
            c_out = c1_out + c2_out + c3_out
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

            all_products_results.append(product_response)

        except Exception as e:
            logger.error(f"❌ Erro ao processar {product_id}: {e}")
            all_products_results.append(BatchProductResponse(
                product_id=product_id,
                num_images=len(product_files),
                filenames=[f.filename for f in product_files],
                prompt="Erro",
                gemini_response="{}",
                generated_images_urls=[],
                error=str(e)
            ))
        finally: 
            shutil.rmtree(temp_dir, ignore_errors=True)

    # --- GERAÇÃO DE EXCEL ---
    excel_url = None
    try:
        excel_url = generate_standard_excel(all_products_results, loja="sams_club")
    except Exception as e:
        logger.error(f"❌ Erro ao gerar Excel: {e}")

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
        excel_download_url=excel_url,
        total_cost_batch_brl=round(total_batch_cost_brl, 4)
    )