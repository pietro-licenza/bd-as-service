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
from app.shared.gemini_client import send_to_gemini, generate_product_images_with_gemini, get_gemini_client
from app.core.config import settings
from app.shared.excel_generator import generate_standard_excel
from app.shared.log_streamer import log_streamer, create_log_streaming_response

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/sams-club",
    tags=["Sam's Club"]
)

# Ensure exports directory exists
settings.EXPORTS_DIR.mkdir(exist_ok=True)


@router.post("/process-batch/", response_model=BatchResponse)
async def process_batch(files: List[UploadFile] = File(...)) -> BatchResponse:
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
    
    # Clear previous logs
    log_streamer.clear_logs()
    log_streamer.log(f"🚀 Iniciando processamento em lote de {len(files)} imagens")
    
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
        log_streamer.log(f"⚠️  {len(unmatched_files)} arquivo(s) sem padrão 'productX_'. Agrupando a cada 3 imagens.", "WARNING")
        images_per_product = 3
        for i in range(0, len(unmatched_files), images_per_product):
            product_key = f"product_{len(product_groups) + 1}"
            product_groups[product_key] = unmatched_files[i:i + images_per_product]
    
    log_streamer.log(f"📦 {len(product_groups)} produto(s) identificado(s)")
    for prod_key, prod_files in product_groups.items():
        log_streamer.log(f"  • {prod_key}: {len(prod_files)} imagem(ns)")
    
    # Process each product
    all_products = []
    excel_data = []
    
    for product_id, product_files in product_groups.items():
        temp_dir = None
        temp_paths = []
        
        try:
            log_streamer.log(f"⚙️  Processando {product_id} com {len(product_files)} imagem(ns)...")
            
            # Create temporary directory
            temp_dir = tempfile.mkdtemp()
            
            # Save uploaded files temporarily
            for file in product_files:
                content = await file.read()
                temp_path = Path(temp_dir) / file.filename
                with open(temp_path, "wb") as f:
                    f.write(content)
                temp_paths.append(str(temp_path))
            
            # Send images to Gemini for data extraction
            log_streamer.log(f"🤖 Enviando imagens para análise do Gemini...")
            result = send_to_gemini(temp_paths)
            log_streamer.log(f"📥 Resposta recebida do Gemini para {product_id}")
            
            # Parse gemini_response (it's a JSON string)
            gemini_response_text = result.get("gemini_response", "")
            product_image_path = result.get("product_image_path")
            
            log_streamer.log(f"🖼️  Imagem do produto identificada: {Path(product_image_path).name}")
            
            gemini_data = {}
            if isinstance(gemini_response_text, str):
                try:
                    # Clean JSON formatting (remove markdown code blocks)
                    clean_json = gemini_response_text.replace("```json", "").replace("```", "").strip()
                    gemini_data = json.loads(clean_json)
                    log_streamer.log(f"✅ Dados extraídos: {gemini_data.get('nome_produto', 'N/A')}")
                except json.JSONDecodeError as e:
                    log_streamer.log(f"❌ Erro ao parsear JSON do Gemini: {str(e)}", "ERROR")
                    log_streamer.log(f"Resposta recebida: {gemini_response_text[:200]}...", "ERROR")
                    gemini_data = {"error": "Resposta inválida da IA"}
            
            # Generate description locally and use it as the canonical description (override any existing)
            if isinstance(gemini_data, dict):
                try:
                    gc = get_gemini_client()
                    product_title = gemini_data.get("nome_produto", "")
                    especificacoes = gemini_data.get("especificacoes", [])
                    log_streamer.log(f"✍️  Gerando descrição padrão para '{product_title}' usando prompt local")
                    generated_desc = gc.generate_description(product_title, especificacoes)
                    generated_desc = generated_desc or ""
                    gemini_data["descricao"] = generated_desc
                    log_streamer.log("✓ Descrição gerada e atribuída aos dados do produto")
                except Exception as desc_err:
                    log_streamer.log(f"⚠️  Falha ao gerar descrição localmente: {desc_err}", "WARNING")

            # Generate product images with AI and upload to cloud
            generated_images_urls = []
            
            if product_image_path and isinstance(gemini_data, dict) and "error" not in gemini_data:
                try:
                    product_name = gemini_data.get("nome_produto", "produto")
                    log_streamer.log(f"🎨 Iniciando geração de imagens no cloud para '{product_name}'...")
                    
                    # Extract numeric ID from product_id (e.g., "product_1" -> 1)
                    numeric_id = None
                    id_match = re.search(r'\\d+', product_id)
                    if id_match:
                        numeric_id = int(id_match.group())
                    
                    log_streamer.log(f"📸 Chamando generate_product_images_with_gemini...")
                    image_gen_result = generate_product_images_with_gemini(
                        product_image_path=product_image_path,
                        product_name=product_name,
                        product_id=numeric_id
                    )
                    generated_images_urls = image_gen_result.get("public_urls", [])
                    log_streamer.log(f"✅ {len(generated_images_urls)} imagens geradas e enviadas ao GCS!")
                    log_streamer.log(f"🔗 URLs: {generated_images_urls}")
                except Exception as img_error:
                    log_streamer.log(f"❌ Erro ao gerar imagens para {product_id}: {str(img_error)}", "ERROR")
            else:
                if not product_image_path:
                    log_streamer.log(f"⚠️  product_image_path não encontrado, pulando geração de imagens", "WARNING")
                if "error" in gemini_data:
                    log_streamer.log(f"⚠️  Erro nos dados do Gemini, pulando geração de imagens", "WARNING")
            
            # Create product response
            product_response = BatchProductResponse(
                product_id=product_id,
                num_images=len(product_files),
                filenames=[file.filename for file in product_files],
                gemini_response=json.dumps(gemini_data, ensure_ascii=False) if isinstance(gemini_data, dict) else str(gemini_data),
                generated_images_urls=generated_images_urls,
                error=gemini_data.get("error") if isinstance(gemini_data, dict) else None
            )
            
            all_products.append(product_response)
            
            # Prepare data for Excel
            if isinstance(gemini_data, dict) and "error" not in gemini_data:
                excel_data.append({
                    "product_id": product_id,
                    "nome_produto": gemini_data.get("nome_produto", ""),
                    "preco": gemini_data.get("preco", ""),
                    "ean": gemini_data.get("ean", ""),
                    "especificacoes": gemini_data.get("especificacoes", []),
                    "descricao": gemini_data.get("descricao", ""),
                    "generated_images_urls": generated_images_urls,
                    "num_generated": len(generated_images_urls)
                })
            
            logger.info(f"✅ {product_id} processado com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar {product_id}: {str(e)}")
            product_response = BatchProductResponse(
                product_id=product_id,
                num_images=len(product_files),
                filenames=[file.filename for file in product_files],
                gemini_response="",
                generated_images_urls=[],
                error=str(e)
            )
            all_products.append(product_response)
        
        finally:
            # Clean up temporary files with proper file handle closure
            if temp_dir and os.path.exists(temp_dir):
                try:
                    # Small delay to ensure file handles are released (Windows issue)
                    import time
                    time.sleep(0.1)
                    shutil.rmtree(temp_dir)
                    logger.debug(f"🧹 Arquivos temporários removidos: {temp_dir}")
                except PermissionError as e:
                    # On Windows, files might still be in use
                    logger.warning(f"⚠️  Arquivos temporários serão removidos posteriormente: {temp_dir}")
                except Exception as e:
                    logger.warning(f"⚠️  Erro ao remover arquivos temporários: {str(e)}")
    
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


@router.get("/logs/stream")
async def stream_logs():
    """
    Stream logs in real-time for frontend display.
    Returns Server-Sent Events stream.
    """
    return create_log_streaming_response()
