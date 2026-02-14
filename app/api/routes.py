"""
API routes for image processing endpoints.
"""
import os
import json
import tempfile
import logging
from typing import List
from datetime import datetime
from fastapi import UploadFile, File, Depends
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment


from app.models.schemas import BatchResponse, BatchProductResponse
from app.shared.gemini_client import send_to_gemini, generate_product_images_with_gemini
from app.core.auth import get_current_user

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Ensure exports directory exists
os.makedirs("exports", exist_ok=True)


def generate_excel_report(products_data: List[dict], filename: str) -> str:
    """
    Generate Excel report from products data.
    
    Args:
        products_data: List of product dictionaries
        filename: Output filename
        
    Returns:
        Path to generated Excel file
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Produtos Processados"
    
    # Define headers
    headers = ["ID", "Nome do Produto", "Pre\u00e7o", "EAN", "Especifica\u00e7\u00f5es", "Descri\u00e7\u00e3o", "Imagens Geradas", "Qtd Imagens"]
    
    # Style headers
    header_fill = PatternFill(start_color="667eea", end_color="667eea", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Add data
    for row_num, product in enumerate(products_data, 2):
        ws.cell(row=row_num, column=1, value=product.get("product_id", ""))
        ws.cell(row=row_num, column=2, value=product.get("nome_produto", ""))
        ws.cell(row=row_num, column=3, value=product.get("preco", ""))
        ws.cell(row=row_num, column=4, value=product.get("ean", ""))
        
        # Especificações (join list)
        specs = product.get("especificacoes", [])
        ws.cell(row=row_num, column=5, value="\n".join(specs) if specs else "")
        
        ws.cell(row=row_num, column=6, value=product.get("descricao", ""))
        
        # URLs (join list with comma)
        urls = product.get("generated_images_urls", [])
        ws.cell(row=row_num, column=7, value=", ".join(urls) if urls else "")
        
        ws.cell(row=row_num, column=8, value=product.get("num_generated", 0))
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 40
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 18
    ws.column_dimensions['E'].width = 50
    ws.column_dimensions['F'].width = 60
    ws.column_dimensions['G'].width = 80
    ws.column_dimensions['H'].width = 12
    
    # Set row heights and wrap text
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    
    # Save file
    filepath = os.path.join("exports", filename)
    wb.save(filepath)
    logger.info(f"\u2705 Excel gerado: {filepath}")
    
    return filepath


async def process_batch_endpoint(files: List[UploadFile] = File(...), user: dict = Depends(get_current_user)) -> BatchResponse:
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
        import re
        match = re.match(r'(product[_\s]?\d+)', filename.lower())
        if match:
            product_id = match.group(1).replace(' ', '_')
            if product_id not in product_groups:
                product_groups[product_id] = []
            product_groups[product_id].append(file)
        else:
            # Files without pattern will be distributed later
            unmatched_files.append(file)
    
    # If there are unmatched files, ask user or distribute by upload order
    # For now: group every 3 images as one product (standard: 3 images per product)
    if unmatched_files:
        logger.warning(f"⚠️  {len(unmatched_files)} arquivo(s) sem padrão 'productX_'. Agrupando a cada 3 imagens.")
        images_per_product = 3
        for i in range(0, len(unmatched_files), images_per_product):
            product_key = f"product_{len(product_groups) + 1}"
            product_groups[product_key] = unmatched_files[i:i + images_per_product]
    
    logger.info(f"📦 {len(product_groups)} produto(s) identificado(s)")
    for prod_key, prod_files in product_groups.items():
        logger.info(f"  • {prod_key}: {len(prod_files)} imagem(ns)")
    
    # Process each product group
    all_temp_files = []
    results = []
    total_images = 0
    product_counter = 1
    
    try:
        for product_key, product_files in product_groups.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"🔄 Processando Produto #{product_counter} ({product_key})")
            logger.info(f"{'='*60}")
            
            temp_files = []
            image_paths = []
            filenames = []
            
            try:
                logger.info(f"📸 Salvando {len(product_files)} imagem(ns) temporariamente...")
                # Save all images for this product as temporary files
                for file in product_files:
                    with tempfile.NamedTemporaryFile(
                        delete=False, 
                        suffix=os.path.splitext(file.filename)[1], 
                        mode="wb"
                    ) as temp_file:
                        content = await file.read()
                        temp_file.write(content)
                        temp_file.flush()
                        temp_file_path = temp_file.name
                        temp_files.append(temp_file_path)
                        all_temp_files.append(temp_file_path)

                    image_paths.append(temp_file_path)
                    filenames.append(file.filename)

                logger.info(f"🤖 Enviando imagens para Gemini (extração de dados)...")
                # Send directly to Gemini - returns dict with gemini_response and product_image_path
                gemini_result = send_to_gemini(image_paths, [], [], [])
                gemini_response_text = gemini_result["gemini_response"]
                product_image_path = gemini_result["product_image_path"]
                logger.info(f"✅ Dados extraídos com sucesso!")
                
                # Parse product name
                try:
                    gemini_data = json.loads(gemini_response_text.replace("```json", "").replace("```", "").strip())
                    product_name = gemini_data.get("nome_produto", "produto")
                    logger.info(f"📝 Produto identificado: {product_name}")
                except:
                    product_name = "produto"
                    logger.warning(f"⚠️  Não foi possível parsear nome do produto")
                
                logger.info(f"🎨 Gerando imagens com fundo branco (Gemini 2.0)...")
                # Generate images with Gemini 2.0 and upload to GCS
                generated_result = generate_product_images_with_gemini(product_image_path, product_name, product_counter)
                
                logger.info(f"☁️  {generated_result['num_generated']} imagem(ns) gerada(s) e enviada(s) para GCS!")
                
                # Build response data with clean JSON structure
                response_data = {
                    "nome_produto": gemini_data.get("nome_produto"),
                    "preco": gemini_data.get("preco"),
                    "ean": gemini_data.get("ean"),
                    "especificacoes": gemini_data.get("especificacoes", []),
                    "descricao": gemini_data.get("descricao"),
                    "generated_images_urls": generated_result["public_urls"],
                    "num_generated": generated_result["num_generated"]
                }
                
                logger.info(f"✅ Produto #{product_counter} processado com sucesso!\n")
                
                results.append(BatchProductResponse(
                    product_id=product_counter,
                    num_images=len(product_files),
                    filenames=filenames,
                    gemini_response=json.dumps(response_data, ensure_ascii=False, indent=2)
                ))
                
                total_images += len(product_files)
                product_counter += 1

            except Exception as e:
                logger.error(f"❌ Erro ao processar Produto #{product_counter}: {str(e)}")
                results.append(BatchProductResponse(
                    product_id=product_counter,
                    num_images=len(product_files),
                    filenames=[f.filename for f in product_files],
                    gemini_response="",
                    error=str(e)
                ))
                product_counter += 1

        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 Processamento concluído! {len(results)} produto(s) processado(s)")
        logger.info(f"{'='*60}\n")
        
        # Generate Excel report
        logger.info(f"\ud83d\udcc4 Gerando relat\u00f3rio Excel...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = f"produtos_{timestamp}.xlsx"
        
        # Extract clean data for Excel
        excel_data = []
        for result in results:
            if not result.error:
                try:
                    response_data = json.loads(result.gemini_response)
                    response_data["product_id"] = result.product_id
                    excel_data.append(response_data)
                except:
                    pass
        
        excel_path = generate_excel_report(excel_data, excel_filename) if excel_data else None
        excel_url = f"/exports/{excel_filename}" if excel_path else None
        
        if excel_url:
            logger.info(f"\u2705 Excel dispon\u00edvel em: {excel_url}")
        
        response = BatchResponse(
            total_products=len(product_groups),
            total_images=total_images,
            products=results
        )
        
        # Add excel_url to response (hacky but works for now)
        response_dict = response.dict()
        response_dict["excel_download_url"] = excel_url
        
        return response_dict

    finally:
        # Cleanup all temporary files
        for temp_file_path in all_temp_files:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
