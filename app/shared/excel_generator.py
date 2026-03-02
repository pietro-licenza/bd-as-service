import os
import logging
from typing import List, Dict, Any
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

def parse_price(price_str: Any) -> float:
    """Converte string de preço (R$ 1.234,56) para float (1234.56)."""
    if isinstance(price_str, (int, float)):
        return float(price_str)
    if not price_str or not isinstance(price_str, str):
        return 0.0
    try:
        clean = price_str.replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(clean)
    except:
        return 0.0

def generate_standard_excel(products: List[Dict], filename: str, output_dir: str, store_name: str, brand_color: str = "475569"):
    """
    Gera um Excel padronizado com fórmulas automáticas e ALTURA DE LINHA PADRÃO.
    Ordem: Nome, Título, EAN, Imagens, Preço Loja, Desconto, Frete, Tarifa, 
    Preço Custo, Preço Anúncio, Arredondamento, Lucros, Descrição, Marca, Modelo.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    filepath = os.path.join(output_dir, filename)
    wb = Workbook()
    ws = wb.active
    ws.title = "Produtos"

    # --- CABEÇALHOS ---
    headers = [
        "NOME DO PRODUTO",       # A (1)
        "TÍTULO DO PRODUTO",     # B (2)
        "EAN",                   # C (3)
        "URL IMAGENS",           # D (4)
        "PREÇO LOJA",            # E (5)
        "DESCONTO",              # F (6)
        "FRETE",                 # G (7)
        "TARIFA",                # H (8)
        "PREÇO LOJA CUSTO",      # I (9)
        "PREÇO ANÚNCIO",         # J (10)
        "TESTE ARREDONDAMENTO",  # K (11)
        "LUCRO %",               # L (12)
        "LUCRO % ARREDONDAMENTO",# M (13)
        "LUCRO",                 # N (14)
        "LUCRO ARREDONDAMENTO",  # O (15)
        "DESCRIÇÃO",             # P (16)
        "MARCA",                 # Q (17)
        "MODELO"                 # R (18)
    ]

    header_fill = PatternFill(start_color=brand_color, end_color=brand_color, fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    center_align = Alignment(horizontal="center", vertical="center")
    # Alinhamento padrão: Esquerda, sem quebra de linha para manter a altura
    standard_align = Alignment(horizontal="left", vertical="center", wrap_text=False)

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    # Coluna T: % Lucro Desejado (Coluna S em branco)
    profit_target_col = 20  # T
    ws.cell(row=1, column=profit_target_col, value="% LUCRO DESEJADO").fill = header_fill
    ws.cell(row=1, column=profit_target_col).font = header_font
    ws.cell(row=2, column=profit_target_col, value=0.15).number_format = '0%'

    # --- PREENCHIMENTO DOS DADOS ---
    for idx, p in enumerate(products, 2):
        price_val = parse_price(p.get("preco", "0"))
        imgs = p.get("image_urls", [])
        img_str = ", ".join(imgs) if isinstance(imgs, list) else str(imgs)
        
        # Trava a altura da linha no padrão Excel (15)
        ws.row_dimensions[idx].height = 15
        
        # Inserção das células
        ws.cell(row=idx, column=1, value=p.get("titulo", "")).alignment = standard_align
        ws.cell(row=idx, column=2, value="").alignment = standard_align
        ws.cell(row=idx, column=3, value=p.get("ean", "")).alignment = standard_align
        ws.cell(row=idx, column=4, value=img_str).alignment = standard_align
        
        c_price = ws.cell(row=idx, column=5, value=price_val)
        c_price.number_format = '#,##0.00'
        c_price.alignment = standard_align
        
        ws.cell(row=idx, column=6, value=0).number_format = '#,##0.00'
        ws.cell(row=idx, column=7, value=50).number_format = '#,##0.00'
        ws.cell(row=idx, column=8, value=0.115).number_format = '0.00%'

        # Fórmulas (Referências fixas conforme nova ordem)
        ws.cell(row=idx, column=9, value=f"=E{idx}-F{idx}").number_format = '#,##0.00'
        ws.cell(row=idx, column=10, value=f"=(I{idx}+G{idx})/(1-H{idx}-$T$2)").number_format = '#,##0.00'
        ws.cell(row=idx, column=11, value=f"=CEILING(J{idx}, 10)-0.1").number_format = '#,##0.00'
        ws.cell(row=idx, column=12, value=f"=(J{idx}*(1-H{idx})-G{idx}-I{idx})/J{idx}").number_format = '0.00%'
        ws.cell(row=idx, column=13, value=f"=(K{idx}*(1-H{idx})-G{idx}-I{idx})/K{idx}").number_format = '0.00%'
        ws.cell(row=idx, column=14, value=f"=J{idx}*(1-H{idx})-G{idx}-I{idx}").number_format = '#,##0.00'
        ws.cell(row=idx, column=15, value=f"=K{idx}*(1-H{idx})-G{idx}-I{idx}").number_format = '#,##0.00'

        # Descrição, Marca e Modelo (Sem wrap_text para não esticar a linha)
        ws.cell(row=idx, column=16, value=p.get("descricao", "")).alignment = standard_align
        ws.cell(row=idx, column=17, value=p.get("marca", "")).alignment = standard_align
        ws.cell(row=idx, column=18, value=p.get("modelo", "")).alignment = standard_align

    # Ajuste de Larguras
    widths = {1:45, 2:45, 3:20, 4:25, 5:15, 6:12, 7:12, 8:12, 9:20, 10:20, 11:22, 12:15, 13:25, 14:12, 15:22, 16:60, 17:15, 18:15, 20:25}
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = w

    wb.save(filepath)
    return filepath