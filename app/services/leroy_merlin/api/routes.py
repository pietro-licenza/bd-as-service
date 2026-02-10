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
    
    if not request.urls:
        raise HTTPException(status_code=400, detail="No URLs provided")
    
    # Get Gemini client
    gemini_client = get_gemini_client()
    
    # Process each URL
    all_products = []
    excel_data = []
    
    for idx, product_url in enumerate(request.urls, 1):
        try:
            logger.info(f"⚙️  Processing product {idx}/{len(request.urls)}: {product_url}")
            
            # Step 1: Extract title, price (highest), images using Python regex (fast, deterministic)
            logger.info(f"📊 Extracting product data with Python regex...")
            product_data = extract_product_data(product_url)
            
            if not product_data.get("success"):
                logger.error(f"❌ Failed to extract basic data: {product_data.get('error')}")
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
            
            logger.info(f"✅ Title: {product_data.get('titulo')}")
            logger.info(f"✅ Price (HIGHEST): {product_data.get('preco')}")
            logger.info(f"✅ Brand: {product_data.get('marca')}")
            logger.info(f"✅ EAN: {product_data.get('ean')}")
            logger.info(f"✅ Images: {len(product_data.get('image_urls', []))}")
            
            # Step 2: Extract specifications and generate description using Gemini AI
            logger.info(f"🤖 Generating professional description with AI...")
            descricao = gemini_client.extract_description_from_url(
                product_url, 
                product_data.get("titulo", "")
            )
            logger.info(f"✅ Description generated ({len(descricao)} characters)")
            
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
            
            logger.info(f"✅ Product {idx} processed successfully: {product_data.get('titulo', 'N/A')}")
            
        except Exception as e:
            logger.error(f"❌ Error processing URL {product_url}: {str(e)}")
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


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Leroy Merlin Product Processor",
        "version": "1.0.0"
    }
