import os
import json
import logging
import tempfile
import shutil
import re
from typing import List
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Request

from app.services.sams_club.schemas import BatchResponse, BatchProductResponse
from app.services.sams_club.image_parser.gemini_client import GeminiClient 
from app.core.config import settings
from app.shared.excel_generator import generate_standard_excel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sams-club", tags=["Sam's Club"])

# Constantes Oficiais para o Faturamento
COST_INPUT_USD = 0.075
COST_OUTPUT_USD = 0.30
USD_TO_BRL = 5.10 

@router.post("/process-batch/", response_model=BatchResponse)
async def process_batch(request: Request, files: List[UploadFile] = File(...)) -> BatchResponse:
    logger.info(f"🚀 Lote Sam's Club recebido.")
    
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

            # Step 1: Extração com nova descrição profissional
            result = gemini_client.step1_extract_product_data(temp_paths)
            u1 = result.get("usage", {"input": 0, "output": 0})
            
            gen_urls, u2 = [], {"input": 0, "output": 0}
            err_msg = result.get("error")

            # Step 2: Geração de Imagem
            if remove_bg and not err_msg:
                infos = result.get("infos_extraidas", {})
                idx_ia = int(infos.get("foto_ideal_index", 1))
                idx = (idx_ia - 1) if idx_ia > 0 else 0
                
                if 0 <= idx < len(temp_paths):
                    gen_res = gemini_client.step2_generate_background_removed_image(temp_paths[idx])
                    gen_urls = gen_res.get("public_urls", [])
                    u2 = gen_res.get("usage", {"input": 0, "output": 0})
                    if gen_res.get("error"): err_msg = gen_res.get("error")

            # Cálculo de Custo Blindado
            t_in = (u1.get("input") or 0) + (u2.get("input") or 0)
            t_out = (u1.get("output") or 0) + (u2.get("output") or 0)
            
            c_in = (t_in / 1_000_000) * COST_INPUT_USD * USD_TO_BRL
            c_out = (t_out / 1_000_000) * COST_OUTPUT_USD * USD_TO_BRL

            product_response = BatchProductResponse(
                product_id=product_id, num_images=len(product_files),
                filenames=[f.filename for f in product_files], prompt="Análise Profissional",
                gemini_response=result.get("gemini_response", "{}"),
                generated_images_urls=gen_urls, error=err_msg,
                input_tokens=int(t_in), input_cost_brl=round(c_in, 6),
                output_tokens=int(t_out), output_cost_brl=round(c_out, 6),
                total_cost_brl=round(c_in + c_out, 6)
            )
            all_products.append(product_response.model_dump())
            
        finally: 
            shutil.rmtree(temp_dir, ignore_errors=True)

    return BatchResponse(products=all_products, total_products=len(all_products))