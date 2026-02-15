"""
API routes for Sam's Club image processing service
"""
import os
import json
import logging
import tempfile
import shutil
from typing import List
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, UploadFile, File
import re

from app.services.sams_club.schemas import BatchResponse, BatchProductResponse
from app.services.sams_club.image_parser.gemini_client import send_to_gemini, generate_product_images_with_gemini
from app.core.config import settings
from app.shared.excel_generator import generate_standard_excel

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/sams-club",
    tags=["Sam's Club"]
)

# Ensure exports directory exists
settings.EXPORTS_DIR.mkdir(exist_ok=True)


from fastapi import Request

@router.post("/process-batch/", response_model=BatchResponse)
async def process_batch(request: Request, files: List[UploadFile] = File(...)) -> BatchResponse:
    """
    Process multiple products in batch.
    
    Files should be named with product identifier (e.g., product1_img1.jpg, product1_img2.jpg, product2_img1.jpg)
    OR they will be grouped sequentially based on upload order.
    
    For better control, name your files: product1_001.jpg, product1_002.jpg, product2_001.jpg, etc.
    
    Args:
        files: List of all uploaded images
        
    Returns:
        Batch response with results for all products
    """
    logger.info(f"🚀 Iniciando processamento em lote de {len(files)} imagens")
    
    # Group files by product based on filename pattern
    product_groups = {}
    unmatched_files = []
    
    for file in files:
        # Try to extract product ID from filename (e.g., "product1_img1.jpg" -> "product1")
        filename = file.filename
        product_id = None
        
        # Pattern: productX_... or product_X_...
        match = re.match(r'(product[_\s]?\d+)', filename.lower())
        if match:
            product_id = match.group(1).replace(' ', '_')
            if product_id not in product_groups:
                product_groups[product_id] = []
            product_groups[product_id].append(file)
        else:
            # Files without pattern will be distributed later
            unmatched_files.append(file)
    
    # If there are unmatched files, group every 3 images as one product
    if unmatched_files:
        images_per_product = 3
        for i in range(0, len(unmatched_files), images_per_product):
            product_key = f"product_{len(product_groups) + 1}"
            product_groups[product_key] = unmatched_files[i:i + images_per_product]
    
    # Process each product
    all_products = []
    excel_data = []

    # Recebe flags e prompts do frontend (FormData)
    form = await request.form()
    prompts = {}
    extract_infos_flags = {}
    remove_background_flags = {}
    for k, v in form.items():
        if k.startswith('prompt_product_'):
            idx = k.split('_')[-1]
            prompts[f'product{idx}'] = v
        if k.startswith('extract_infos_'):
            idx = k.split('_')[-1]
            extract_infos_flags[f'product{idx}'] = v == 'true'
        if k.startswith('remove_background_'):
            idx = k.split('_')[-1]
            remove_background_flags[f'product{idx}'] = v == 'true'

    logger.info(f"📋 Flags recebidas - Extract Infos: {extract_infos_flags}, Remove Background: {remove_background_flags}")

    for i, (product_id, product_files) in enumerate(product_groups.items(), 1):
        temp_dir = tempfile.mkdtemp()
        temp_paths = []
        for file in product_files:
            content = await file.read()
            temp_path = Path(temp_dir) / file.filename
            with open(temp_path, "wb") as f:
                f.write(content)
            # Converte MPO para JPEG se necessário
            from app.shared.gemini_client import convert_mpo_to_jpeg
            converted_path, _ = convert_mpo_to_jpeg(str(temp_path))
            temp_paths.append(converted_path)

        # Prompt e flag para o produto
        prompt = prompts.get(f'product{i}', "Descreva o produto.")
        extract_infos = extract_infos_flags.get(f'product{i}', True)

        # Chama GeminiClient com a flag correta
        from app.services.sams_club.image_parser.gemini_client import GeminiClient
        gemini_client = GeminiClient()
        result = gemini_client.step1_extract_product_data(temp_paths, extract_infos=extract_infos)
        gemini_response_text = result.get("gemini_response", "")
        generated_images_urls = result.get("generated_images_urls", [])

        # Processa remoção de fundo se solicitado
        remove_background = remove_background_flags.get(f'product{i}', False)
        if remove_background and extract_infos:
            logger.info(f"🎨 Iniciando Step 2: Remoção de fundo para produto {product_id}")
            infos = result.get("infos_extraidas", {})
            ideal_index = infos.get("foto_ideal_index", 1) - 1  # 0-based
            logger.info(f"🎯 Produto {product_id}: foto_ideal_index={infos.get('foto_ideal_index', 'N/A')}, ideal_index ajustado={ideal_index}, total imagens={len(temp_paths)}")
            if 0 <= ideal_index < len(temp_paths):
                ideal_path = temp_paths[ideal_index]
                logger.info(f"🖼️ Imagem selecionada para Step 2: {ideal_path}")
                gen_result = gemini_client.step2_generate_background_removed_image(ideal_path)
                generated_images_urls = gen_result.get("public_urls", [])
                logger.info(f"✅ Step 2 concluído para produto {product_id}: {len(generated_images_urls)} imagens geradas")
            else:
                logger.warning(f"⚠️ Índice ideal inválido para produto {product_id}: {ideal_index}")
        else:
            logger.info(f"⏭️ Step 2 pulado para produto {product_id} (remove_background: {remove_background}, extract_infos: {extract_infos})")

        product_response = BatchProductResponse(
            product_id=product_id,
            num_images=len(product_files),
            filenames=[file.filename for file in product_files],
            prompt=prompt,
            gemini_response=gemini_response_text,
            generated_images_urls=generated_images_urls,
            error=None
        )
        all_products.append(product_response)

        # Limpeza dos arquivos temporários
        if temp_dir and os.path.exists(temp_dir):
            try:
                import time
                time.sleep(0.1)
                shutil.rmtree(temp_dir)
                logger.debug(f"🧹 Arquivos temporários removidos: {temp_dir}")
            except PermissionError as e:
                logger.warning(f"⚠️  Arquivos temporários serão removidos posteriormente: {temp_dir}")
    
    # Generate Excel report
    excel_url = None
    if excel_data:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"produtos_processados_{timestamp}.xlsx"
            excel_path = generate_standard_excel(
                products_data=excel_data,
                filename=excel_filename,
                exports_dir=settings.EXPORTS_DIR,
                service_name="Sam's Club",
                header_color="667eea"
            )
            excel_url = f"/exports/{excel_filename}"
            logger.info(f"📊 Relatório Excel disponível: {excel_url}")
        except Exception as e:
            logger.error(f"❌ Erro ao gerar Excel: {str(e)}")
    
    return BatchResponse(
        products=all_products,
        total_products=len(all_products),
        excel_download_url=excel_url
    )
