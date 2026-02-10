"""
API routes for Leroy Merlin product processing service.
"""
import logging
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.services.leroy_merlin.schemas import (
    ProductUrlRequest,
    ProductData,
    BatchResponse,
    ErrorResponse
)
from app.services.leroy_merlin.scraper.url_extractor import extract_images_1800, extract_product_data
from app.services.leroy_merlin.scraper.gemini_client import get_gemini_client
from app.core.config import settings
from app.shared.excel_generator import generate_standard_excel
from app.shared.log_streamer import log_streamer, create_log_streaming_response

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/leroy-merlin",
    tags=["Leroy Merlin"]
)

# Ensure exports directory exists
settings.EXPORTS_DIR.mkdir(exist_ok=True)


@router.post("/process-urls/", response_model=BatchResponse)
async def process_product_urls(request: ProductUrlRequest) -> BatchResponse:
    """
    Process multiple Leroy Merlin product URLs.
    
    For each URL:
    1. Extract title, price (highest), images using Python regex (fast, deterministic)
    2. Extract specifications using Gemini AI
    3. Combine results
    
    Args:
        request: Request with list of product URLs
        
    Returns:
        Batch response with all processed products and Excel download link
    """
    logger.info(f"🚀 Starting batch processing of {len(request.urls)} URLs")
    
    # Clear previous logs
    log_streamer.clear_logs()
    log_streamer.log(f"🚀 Iniciando processamento em lote de {len(request.urls)} URLs")
    
    if not request.urls:
        raise HTTPException(status_code=400, detail="No URLs provided")
    
    # Get Gemini client
    gemini_client = get_gemini_client()
    
    # Process each URL
    all_products = []
    excel_data = []
    
    for idx, product_url in enumerate(request.urls, 1):
        try:
            log_streamer.log(f"⚙️  Processando produto {idx}/{len(request.urls)}: {product_url[:50]}...")
            
            # Step 1: Extract title, price (highest), images using Python regex (fast, deterministic)
            log_streamer.log(f"📊 Extraindo dados do produto com Python regex...")
            product_data = extract_product_data(product_url)
            
            if not product_data.get("success"):
                log_streamer.log(f"❌ Falha ao extrair dados básicos: {product_data.get('error')}", "ERROR")
                product_response = ProductData(
                    titulo=product_data.get("titulo", ""),
                    preco=product_data.get("preco", ""),
                    marca=product_data.get("marca", ""),
                    ean=product_data.get("ean", ""),
                    descricao="",
                    image_urls=product_data.get("image_urls", []),
                    url_original=product_url,
                    error=product_data.get("error")
                )
                all_products.append(product_response)
                continue
            
            log_streamer.log(f"✅ Título: {product_data.get('titulo')}")
            log_streamer.log(f"✅ Preço (MAIOR): {product_data.get('preco')}")
            log_streamer.log(f"✅ Marca: {product_data.get('marca')}")
            log_streamer.log(f"✅ EAN: {product_data.get('ean')}")
            log_streamer.log(f"✅ Imagens: {len(product_data.get('image_urls', []))}")
            
            # Step 2: Extract specifications and generate description using Gemini AI
            log_streamer.log(f"🤖 Gerando descrição profissional com IA...")
            descricao = gemini_client.extract_description_from_url(
                product_url, 
                product_data.get("titulo", "")
            )
            log_streamer.log(f"✅ Descrição gerada ({len(descricao)} caracteres)")
            
            # Step 3: Combine results
            product_response = ProductData(
                titulo=product_data.get("titulo", ""),
                preco=product_data.get("preco", ""),
                marca=product_data.get("marca", ""),
                ean=product_data.get("ean", ""),
                descricao=descricao,
                image_urls=product_data.get("image_urls", []),
                url_original=product_url,
                error=None
            )
            
            all_products.append(product_response)
            
            # Prepare data for Excel
            excel_data.append({
                "titulo": product_data.get("titulo", ""),
                "preco": product_data.get("preco", ""),
                "marca": product_data.get("marca", ""),
                "ean": product_data.get("ean", ""),
                "descricao": descricao,
                "image_urls": product_data.get("image_urls", []),
                "url_original": product_url
            })
            
            log_streamer.log(f"✅ Produto {idx} processado com sucesso: {product_data.get('titulo', 'N/A')}")
            
        except Exception as e:
            log_streamer.log(f"❌ Erro ao processar URL {product_url[:50]}...: {str(e)}", "ERROR")
            product_response = ProductData(
                titulo="",
                preco="",
                marca="",
                ean="",
                descricao="",
                image_urls=[],
                url_original=product_url,
                error=str(e)
            )
            all_products.append(product_response)
    
    # Generate Excel report
    excel_url = None
    if excel_data:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"leroy_produtos_{timestamp}.xlsx"
            excel_path = generate_standard_excel(
                products_data=excel_data,
                filename=excel_filename,
                exports_dir=settings.EXPORTS_DIR,
                service_name="Leroy Merlin",
                header_color="00A859"
            )
            excel_url = f"/exports/{excel_filename}"
            logger.info(f"📊 Excel report available: {excel_url}")
        except Exception as e:
            logger.error(f"❌ Error generating Excel: {str(e)}")
    
    logger.info(f"✅ Batch processing complete: {len(all_products)} products processed")
    
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


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Leroy Merlin Product Processor",
        "version": "1.0.0"
    }
