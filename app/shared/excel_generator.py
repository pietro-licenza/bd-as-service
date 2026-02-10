"""
Shared Excel Generator - Universal format for all services

This module provides a centralized Excel generator with the standard format
including pricing formulas, profit calculations, and consistent styling.
"""
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from pathlib import Path
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def generate_standard_excel(
    products_data: List[dict],
    filename: str,
    exports_dir: Path,
    service_name: str = "Produtos",
    header_color: str = "667eea"
) -> str:
    """
    Generate Excel report with universal format and pricing formulas.
    
    This is the standard format used across all services (Sam's Club, Leroy Merlin, etc.)
    
    Args:
        products_data: List of product dictionaries with keys:
            - nome_produto or titulo: Product name
            - preco: Price (can be string like "R$ 1.190,43" or float)
            - descricao: Product description
            - image_urls or generated_images_urls: List of image URLs
            - ean: EAN code (optional)
            - especificacoes: List of specifications (optional)
        filename: Output filename (e.g., "produtos_20260206.xlsx")
        exports_dir: Directory to save the file
        service_name: Name for the worksheet tab (e.g., "Sam's Club", "Leroy Merlin")
        header_color: Hex color for header (without #, e.g., "667eea" or "00A859")
        
    Returns:
        str: Full path to the generated Excel file
        
    Excel structure:
        A: NOME DO PRODUTO
        B: TÍTULO DO PRODUTO (empty for manual editing)
        C: MARCA
        D: URL IMAGENS (comma-separated)
        E: EAN
        F: DESCRIÇÃO
        G: PREÇO LOJA
        H: DESCONTO (default 0)
        I: FRETE (default 0)
        J: TARIFA (default 0)
        K: PREÇO LOJA CUSTO (formula)
        L: PREÇO ANÚNCIO (formula)
        M: TESTE ARREDONDAMENTO (formula)
        N: LUCRO % (formula)
        O: LUCRO % ARREDONDAMENTO (formula)
        P: LUCRO (formula)
        Q: LUCRO ARREDONDAMENTO (formula)
        R: (blank separator)
        S: % LUCRO DESEJADO (15% default, fixed reference $S$2)
    """
    logger.info(f"📊 Generating Excel report: {filename}")
    
    wb = Workbook()
    ws = wb.active
    ws.title = service_name
    
    # Define headers - Padrão universal
    headers = [
        "NOME DO PRODUTO",          # A
        "TÍTULO DO PRODUTO",        # B (vazio)
        "MARCA",                    # C
        "URL IMAGENS",              # D
        "EAN",                      # E
        "DESCRIÇÃO",                # F
        "PREÇO LOJA",               # G
        "DESCONTO",                 # H
        "FRETE",                    # I
        "TARIFA",                   # J
        "PREÇO LOJA CUSTO",         # K (fórmula)
        "PREÇO ANÚNCIO",            # L (fórmula)
        "TESTE ARREDONDAMENTO",     # M (fórmula)
        "LUCRO %",                  # N (fórmula)
        "LUCRO % ARREDONDAMENTO",   # O (fórmula)
        "LUCRO",                    # P (fórmula)
        "LUCRO ARREDONDAMENTO",     # Q (fórmula)
        "",                         # R (vazio)
        "% LUCRO DESEJADO"          # S
    ]
    
    # Style headers
    header_fill = PatternFill(start_color=header_color, end_color=header_color, fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Add data
    for row_num, product in enumerate(products_data, 2):
        # A - NOME DO PRODUTO
        nome = product.get("nome_produto") or product.get("titulo", "")
        ws.cell(row=row_num, column=1, value=nome)
        
        # B - TÍTULO DO PRODUTO (vazio para edição manual)
        ws.cell(row=row_num, column=2, value="")
        
        # C - MARCA (tentar extrair das especificações)
        marca = extract_marca(product)
        ws.cell(row=row_num, column=3, value=marca)
        
        # D - URL IMAGENS (separadas por vírgula)
        image_urls = product.get("image_urls") or product.get("generated_images_urls", [])
        ws.cell(row=row_num, column=4, value=", ".join(image_urls) if image_urls else "")
        
        # E - EAN
        ws.cell(row=row_num, column=5, value=product.get("ean", ""))
        
        # F - DESCRIÇÃO
        ws.cell(row=row_num, column=6, value=product.get("descricao", ""))
        
        # G - PREÇO LOJA (converter para número)
        preco_float = parse_price(product.get("preco", ""))
        ws.cell(row=row_num, column=7, value=preco_float)
        ws.cell(row=row_num, column=7).number_format = 'R$ #,##0.00'
        
        # H - DESCONTO (0 por padrão)
        ws.cell(row=row_num, column=8, value=0)
        
        # I - FRETE (0 por padrão)
        ws.cell(row=row_num, column=9, value=0)
        
        # J - TARIFA (0 por padrão)
        ws.cell(row=row_num, column=10, value=0)
        
        # K - PREÇO LOJA CUSTO (fórmula)
        ws.cell(row=row_num, column=11, value=f"=G{row_num}*(100-H{row_num})/100+I{row_num}+(J{row_num}/100)*L{row_num}+(6/100)*L{row_num}")
        ws.cell(row=row_num, column=11).number_format = 'R$ #,##0.00'
        
        # L - PREÇO ANÚNCIO (fórmula)
        ws.cell(row=row_num, column=12, value=f"=(G{row_num}*(100-H{row_num})/100+I{row_num}) / (1 - J{row_num}/100 - 6/100 - $S$2)")
        ws.cell(row=row_num, column=12).number_format = 'R$ #,##0.00'
        
        # M - TESTE ARREDONDAMENTO (fórmula) - MROUND
        ws.cell(row=row_num, column=13, value=f"=MROUND((G{row_num}*(100-H{row_num})/100 + I{row_num}) / (1 - J{row_num}/100 - 6/100 - $S$2), 10) - 0.1")
        ws.cell(row=row_num, column=13).number_format = 'R$ #,##0.00'
        
        # N - LUCRO % (fórmula)
        ws.cell(row=row_num, column=14, value=f"=P{row_num}/L{row_num}")
        ws.cell(row=row_num, column=14).number_format = '0.00%'
        
        # O - LUCRO % ARREDONDAMENTO (fórmula)
        ws.cell(row=row_num, column=15, value=f"=Q{row_num}/M{row_num}")
        ws.cell(row=row_num, column=15).number_format = '0.00%'
        
        # P - LUCRO (fórmula)
        ws.cell(row=row_num, column=16, value=f"=L{row_num}-K{row_num}")
        ws.cell(row=row_num, column=16).number_format = 'R$ #,##0.00'
        
        # Q - LUCRO ARREDONDAMENTO (fórmula)
        ws.cell(row=row_num, column=17, value=f"=M{row_num}-K{row_num}")
        ws.cell(row=row_num, column=17).number_format = 'R$ #,##0.00'
        
        # R - EM BRANCO
        ws.cell(row=row_num, column=18, value="")
        
        # S - % LUCRO DESEJADO (apenas na linha 2, demais referenciam S2)
        if row_num == 2:
            ws.cell(row=row_num, column=19, value=0.15)  # 15%
            ws.cell(row=row_num, column=19).number_format = '0%'
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 50  # Nome produto
    ws.column_dimensions['B'].width = 50  # Título produto
    ws.column_dimensions['C'].width = 20  # Marca
    ws.column_dimensions['D'].width = 80  # URLs imagens
    ws.column_dimensions['E'].width = 18  # EAN
    ws.column_dimensions['F'].width = 70  # Descrição
    ws.column_dimensions['G'].width = 15  # Preço loja
    ws.column_dimensions['H'].width = 12  # Desconto
    ws.column_dimensions['I'].width = 12  # Frete
    ws.column_dimensions['J'].width = 12  # Tarifa
    ws.column_dimensions['K'].width = 18  # Preço loja custo
    ws.column_dimensions['L'].width = 18  # Preço anúncio
    ws.column_dimensions['M'].width = 20  # Teste arredondamento
    ws.column_dimensions['N'].width = 12  # Lucro %
    ws.column_dimensions['O'].width = 20  # Lucro % arredondamento
    ws.column_dimensions['P'].width = 15  # Lucro
    ws.column_dimensions['Q'].width = 20  # Lucro arredondamento
    ws.column_dimensions['R'].width = 5   # Vazio
    ws.column_dimensions['S'].width = 18  # % Lucro desejado
    
    # Set row height to default (15) and alignment
    for row_num in range(2, ws.max_row + 1):
        ws.row_dimensions[row_num].height = 15  # Altura padrão do Excel
        # Align cells without wrap_text to keep rows compact
        for cell in ws[row_num]:
            cell.alignment = Alignment(horizontal="left", vertical="center")
    
    # Save file
    filepath = exports_dir / filename
    wb.save(str(filepath))
    logger.info(f"✅ Excel saved: {filepath}")
    
    return str(filepath)


def extract_marca(product: dict) -> str:
    """
    Extract brand/marca from product data.
    
    Args:
        product: Product dictionary
        
    Returns:
        Brand name or empty string
    """
    # First, try to get marca field directly (Leroy Merlin provides this)
    marca = product.get("marca", "")
    if marca:
        return marca
    
    # Fallback: try to extract from specifications
    specs = product.get("especificacoes", [])
    if not specs:
        return ""
    
    for spec in specs:
        spec_lower = spec.lower()
        if "marca" in spec_lower or "brand" in spec_lower:
            # Try to extract value after colon
            if ":" in spec:
                return spec.split(":", 1)[1].strip()
            return spec
    
    return ""


def parse_price(price_value) -> float:
    """
    Parse price from string or number to float.
    
    Args:
        price_value: Price as string ("R$ 1.190,43") or number
        
    Returns:
        Price as float (1190.43)
    """
    if isinstance(price_value, (int, float)):
        return float(price_value)
    
    if not price_value or not isinstance(price_value, str):
        return 0.0
    
    try:
        # Remove "R$" and spaces
        clean = price_value.replace("R$", "").replace(" ", "").strip()
        # Remove thousand separator (.)
        clean = clean.replace(".", "")
        # Replace decimal separator (,) with (.)
        clean = clean.replace(",", ".")
        return float(clean)
    except (ValueError, AttributeError):
        return 0.0
