"""
Kit Builder API Routes

POST /api/kit-builder/process-urls/  → Processa N URLs e retorna o kit unificado
POST /api/kit-builder/generate-excel/ → Gera Excel do kit
"""
import logging
import re
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.services.kit_builder.schemas import (
    KitBuildRequest, KitBuildResponse, KitProductData, IndividualProductData
)
from app.services.kit_builder.scraper.url_extractor import (
    extract_product_for_kit,
    build_kit_dimensions,
    sum_prices,
    merge_images,
    detect_marketplace,
)
from app.services.kit_builder.scraper.gemini_client import get_gemini_client
from app.services.kit_builder.scraper.image_generator import get_image_generator
from app.core.config import settings
from app.shared.excel_generator import generate_standard_excel
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.entities import ScrapingLog

USD_TO_BRL = 5.10

# gemini-1.5-flash (text) pricing
TOKEN_IN_PRICE  = (0.10 / 1_000_000) * USD_TO_BRL
TOKEN_OUT_PRICE = (0.40 / 1_000_000) * USD_TO_BRL

# gemini-2.5-flash-image pricing
IMG_TOKEN_IN_PRICE   = (0.10 / 1_000_000) * USD_TO_BRL   # text input tokens
IMG_TEXT_OUT_PRICE   = (0.40 / 1_000_000) * USD_TO_BRL   # text output tokens (negligível em chamadas de imagem)
IMG_TOKEN_OUT_PRICE  = (30.0 / 1_000_000) * USD_TO_BRL   # image output tokens (~1290 por imagem 1024x1024)

router = APIRouter(prefix="/api/kit-builder", tags=["Kit Builder"])
logger = logging.getLogger(__name__)


@router.post("/process-urls/", response_model=KitBuildResponse)
async def process_kit_urls(
    request: KitBuildRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
) -> KitBuildResponse:
    """
    Recebe 2+ URLs de qualquer marketplace suportado, extrai os dados de cada produto
    e monta um kit unificado com:
    - Preço = soma dos maiores preços de cada produto
    - Dimensões = maior dimensão entre os produtos (+ margem de embalagem)
    - Marca = sempre Brazil Home Living
    - Descrição e título = gerados pelo Gemini
    """
    logger.info(f"🎁 Kit Builder: {len(request.urls)} URLs para {user.username}")

    gemini_client = get_gemini_client()
    individual_products: List[IndividualProductData] = []
    raw_products: List[dict] = []

    # Normaliza quantities (preenche com 1 se não informado)
    quantities = list(request.quantities) if request.quantities else []
    while len(quantities) < len(request.urls):
        quantities.append(1)
    quantities = [max(1, q) for q in quantities]

    # Produto central: garante índice válido
    central_idx = max(0, min(request.produto_central_index, len(request.urls) - 1))

    # -----------------------------------------------------------------------
    # PASSO 1: Extrair dados de cada URL individualmente
    # -----------------------------------------------------------------------
    for i, url in enumerate(request.urls):
        marketplace = detect_marketplace(url)
        qty = quantities[i]
        is_central = (i == central_idx)
        p_info = extract_product_for_kit(url)

        # Preço total do item = preço unitário × quantidade
        preco_unit = p_info.get("preco", "")
        preco_total_str = ""
        if preco_unit:
            from app.services.kit_builder.scraper.url_extractor import parse_price_to_float, format_price
            preco_total_str = format_price(parse_price_to_float(preco_unit) * qty)

        individual_products.append(IndividualProductData(
            titulo=p_info.get("titulo") or None,
            preco=preco_unit or None,
            preco_total=preco_total_str or None,
            marca=p_info.get("marca") or None,
            ean=p_info.get("ean") or None,
            modelo=p_info.get("modelo") or None,
            marketplace=marketplace,
            url_original=url,
            quantidade=qty,
            is_produto_central=is_central,
            largura_cm=p_info.get("largura") or None,
            comprimento_cm=(p_info.get("comprimento") or p_info.get("profundidade")) or None,
            altura_cm=p_info.get("altura") or None,
            peso_kg=p_info.get("peso") or None,
            image_urls=p_info.get("image_urls", []),
            error=p_info.get("error") or None,
        ))

        # Adiciona metadata de quantidade e central ao raw_product para o Gemini
        p_info["quantidade"] = qty
        p_info["is_produto_central"] = is_central
        raw_products.append(p_info)

        logger.info(
            f"{'⭐' if is_central else '  '} Extraído: {p_info.get('titulo', 'N/A')} | "
            f"Qtd: {qty} | Preço unit: {preco_unit} | Marketplace: {marketplace}"
        )

    # -----------------------------------------------------------------------
    # PASSO 2: Gerar título e descrição do kit via Gemini
    # -----------------------------------------------------------------------
    gemini_res = gemini_client.generate_kit_content(raw_products, central_idx)
    usage = gemini_res.get("usage", {"input": 0, "output": 0})

    c_in   = usage["input"]  * TOKEN_IN_PRICE
    c_out  = usage["output"] * TOKEN_OUT_PRICE
    total_cost = c_in + c_out

    # -----------------------------------------------------------------------
    # PASSO 3: Unificação de preço e dimensões
    # Preço = soma de (preço_unitário × quantidade) de cada produto
    # -----------------------------------------------------------------------
    from app.services.kit_builder.scraper.url_extractor import parse_price_to_float, format_price
    kit_preco_total = sum(
        parse_price_to_float(p.get("preco", "")) * p.get("quantidade", 1)
        for p in raw_products
    )
    kit_preco  = format_price(kit_preco_total)
    kit_dims   = build_kit_dimensions(raw_products)
    kit_images = merge_images(raw_products, limit=10)

    # URL original = concatenação das URLs para referência
    kit_url = " | ".join(request.urls)

    # Título: gerado pelo Gemini; fallback legível
    kit_titulo = gemini_res.get("titulo_kit") or " + ".join(
        p.get("titulo", "Produto") for p in raw_products
    )

    # -----------------------------------------------------------------------
    # PASSO 4: Geração de imagens do kit via Gemini Image
    # -----------------------------------------------------------------------
    individual_product_urls: list = []
    kit_urls: list = []
    generated_image_urls: list = []
    image_gen_cost_brl: float = 0.0
    try:
        image_generator = get_image_generator()
        products_image_urls = [p.get("image_urls", []) for p in raw_products]
        products_qty_info = [
            {"titulo": p.get("titulo", f"Produto {i+1}"), "quantidade": p.get("quantidade", 1)}
            for i, p in enumerate(raw_products)
        ]
        img_result = image_generator.generate_all_kit_images(
            products_image_urls,
            kit_titulo,
            kit_description=gemini_res.get("descricao", ""),
            products_qty_info=products_qty_info,
        )
        individual_product_urls = img_result.get("individual_product_urls", [])
        kit_urls                = img_result.get("kit_urls", [])
        generated_image_urls    = img_result.get("generated_urls", [])

        img_in   = img_result.get("total_input_tokens",  0)
        img_out  = img_result.get("total_output_tokens", 0)
        img_imgs = img_result.get("total_image_tokens",  0)
        image_gen_cost_brl = (
            img_in   * IMG_TOKEN_IN_PRICE  +
            img_out  * IMG_TEXT_OUT_PRICE  +
            img_imgs * IMG_TOKEN_OUT_PRICE
        )
        logger.info(
            f"🖼️ Fotos individuais: {len(individual_product_urls)} | "
            f"Fotos kit: {len(kit_urls)} | "
            f"Custo: R$ {image_gen_cost_brl:.4f}"
        )
    except Exception as img_err:
        logger.error(f"❌ Falha na geração de imagens do kit: {img_err}")

    total_cost_all = total_cost + image_gen_cost_brl

    kit = KitProductData(
        titulo=kit_titulo,
        preco=kit_preco,
        marca="Brazil Home Living",
        modelo="Kit",
        ean="",
        descricao=gemini_res.get("descricao", ""),
        image_urls=kit_images,
        individual_product_urls=individual_product_urls,
        kit_urls=kit_urls,
        generated_image_urls=generated_image_urls,
        image_generation_cost_brl=round(image_gen_cost_brl, 6),
        url_original=kit_url,
        largura_cm=kit_dims["largura_cm"],
        comprimento_cm=kit_dims["comprimento_cm"],
        altura_cm=kit_dims["altura_cm"],
        dimensoes_lca=kit_dims["dimensoes_lca"],
        peso_kg=kit_dims["peso_kg"],
        input_tokens=usage["input"],
        output_tokens=usage["output"],
        input_cost_brl=round(c_in, 6),
        output_cost_brl=round(c_out, 6),
        total_cost_brl=round(total_cost_all, 6),
    )

    # -----------------------------------------------------------------------
    # PASSO 5: Log no banco
    # -----------------------------------------------------------------------
    try:
        log_entry = ScrapingLog(
            user_id=user.id,
            loja="kit_builder",
            url_count=len(request.urls),
            total_tokens=usage["input"] + usage["output"],
            total_cost_brl=total_cost_all,
        )
        db.add(log_entry)
        db.commit()
    except Exception as db_err:
        db.rollback()
        logger.error(f"❌ Erro log Kit Builder: {db_err}")

    # -----------------------------------------------------------------------
    # PASSO 6: Gerar Excel
    # -----------------------------------------------------------------------
    excel_url = None
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = f"kit_produtos_{timestamp}.xlsx"
        excel_dict = kit.dict()
        # Usa as imagens geradas pela IA no Excel (em vez das fotos originais dos produtos)
        # Excel usa fotos do kit (fundo branco + lifestyle); fallback nas originais
        excel_dict["image_urls"] = kit.kit_urls or kit.generated_image_urls or kit.image_urls
        generate_standard_excel([excel_dict], excel_filename, settings.EXPORTS_DIR, "Kit Builder", "7C3AED")
        excel_url = f"/exports/{excel_filename}"
    except Exception as e:
        logger.error(f"❌ Falha Excel Kit: {e}")

    return KitBuildResponse(
        kit=kit,
        individual_products=individual_products,
        excel_download_url=excel_url,
        total_cost_batch_brl=total_cost_all,
    )


@router.post("/generate-excel/")
async def generate_excel(request: Request):
    """
    Gera Excel do kit. Aceita o kit já processado para regeneração.
    """
    body = await request.json()
    kit = body.get("kit", {})

    # Garante marca Brazil Home Living
    kit["marca"] = "Brazil Home Living"

    # Remove menções de marcas originais na descrição, se houver
    descricao = kit.get("descricao", "")
    for loja in ["Leroy Merlin", "Sodimac", "Decathlon", "Sam's Club", "SamsClub"]:
        pattern = re.compile(rf"\b{re.escape(loja)}\b", re.IGNORECASE)
        descricao = pattern.sub("Brazil Home Living", descricao)
    kit["descricao"] = descricao

    # Usa as imagens geradas pela IA no Excel (em vez das fotos originais)
    kit["image_urls"] = kit.get("generated_image_urls") or kit.get("image_urls", [])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_filename = f"kit_produtos_{timestamp}.xlsx"
    generate_standard_excel([kit], excel_filename, settings.EXPORTS_DIR, "Kit Builder", "7C3AED")

    excel_path = f"{settings.EXPORTS_DIR}/{excel_filename}"
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=excel_filename,
    )
