"""
Kit Builder URL Extractor

Detecta o marketplace de cada URL e chama o extrator correspondente.
Concentra também a lógica de unificação de preço e dimensões.
"""
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Marketplaces suportados
MARKETPLACE_MAP = {
    "leroymerlin.com.br": "leroy_merlin",
    "sodimac.com.br":     "sodimac",
    "decathlon.com.br":   "decathlon",
    "samsclub.com.br":    "sams_club",
}


def detect_marketplace(url: str) -> str:
    """Detecta o marketplace a partir da URL."""
    for domain, name in MARKETPLACE_MAP.items():
        if domain in url:
            return name
    return "unknown"


_EMPTY_PRODUCT: Dict = {
    "titulo": "", "preco": "", "marca": "", "ean": "", "modelo": "",
    "largura": None, "comprimento": None, "profundidade": None,
    "altura": None, "peso": None, "image_urls": [],
    "success": False, "error": None,
}


def _normalize(data: Dict, url: str, marketplace: str) -> Dict:
    """
    Garante que o dict retornado por qualquer scraper sempre possui
    todas as chaves esperadas pelo kit builder, preenchendo com None/[]
    quando o marketplace não fornece o campo (ex: Sodimac/Decathlon não
    têm dimensões).
    """
    base = dict(_EMPTY_PRODUCT)
    base.update(data)
    base["marketplace"] = marketplace
    base["url"] = url
    return base


def extract_product_for_kit(url: str) -> Dict:
    """
    Extrai dados do produto usando o extrator do marketplace correspondente.
    Sempre retorna dict com as mesmas chaves, independente do marketplace.
    """
    marketplace = detect_marketplace(url)
    logger.info(f"🔍 Marketplace detectado: {marketplace} | URL: {url}")

    try:
        if marketplace == "leroy_merlin":
            from app.services.leroy_merlin.scraper.url_extractor import extract_product_data
        elif marketplace == "sodimac":
            from app.services.sodimac.scraper.url_extractor import extract_product_data
        elif marketplace == "decathlon":
            from app.services.decathlon.scraper.url_extractor import extract_product_data
        elif marketplace == "sams_club":
            from app.services.sams_club.scraper.url_extractor import extract_product_data
        else:
            return _normalize(
                {"error": f"Marketplace não suportado: {url}", "success": False},
                url, marketplace
            )

        data = extract_product_data(url)
        return _normalize(data, url, marketplace)

    except Exception as e:
        logger.error(f"❌ Erro ao extrair produto de {url}: {e}")
        return _normalize({"error": str(e), "success": False}, url, marketplace)


# ---------------------------------------------------------------------------
# Helpers de preço
# ---------------------------------------------------------------------------

def parse_price_to_float(price_str: Optional[str]) -> float:
    """Converte 'R$ 1.190,43' para float 1190.43"""
    if not price_str:
        return 0.0
    try:
        clean = price_str.replace("R$", "").strip()
        clean = clean.replace(".", "").replace(",", ".")
        return float(clean)
    except Exception:
        return 0.0


def format_price(value: float) -> str:
    """Converte float 1190.43 para 'R$ 1.190,43'"""
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def sum_prices(products: List[Dict]) -> str:
    """
    Soma os preços de todos os produtos.
    Regra: pega o maior preço de cada produto e soma todos.
    (Neste contexto cada produto já tem seu maior preço extraído pelo scraper.)
    """
    total = sum(parse_price_to_float(p.get("preco")) for p in products)
    return format_price(total)


# ---------------------------------------------------------------------------
# Helpers de dimensão
# ---------------------------------------------------------------------------

def parse_dimension_to_cm(value_str: Optional[str]) -> Optional[float]:
    """
    Converte string de dimensão para float em cm.
    Suporta metros (ex: '1,50 m') e centímetros (ex: '45 cm' ou '45').
    """
    if not value_str:
        return None
    try:
        s = value_str.strip().lower()
        is_meters = bool(re.search(r"\bm\b", s) and not re.search(r"\bcm\b", s))
        numeric = re.sub(r"[^\d,.]", "", value_str).replace(",", ".")
        val = float(numeric)
        if is_meters:
            val = val * 100
        return val
    except Exception:
        return None


def apply_packaging_margin(value_str: Optional[str], margin: float) -> str:
    """Aplica margem de embalagem (+7cm / +2kg) ao valor da dimensão."""
    if not value_str:
        return ""
    try:
        s = value_str.strip().lower()
        is_meters = bool(re.search(r"\bm\b", s) and not re.search(r"\bcm\b", s))
        numeric = re.sub(r"[^\d,.]", "", value_str).replace(",", ".")
        val = float(numeric)
        if is_meters:
            val = val * 100
        return f"{val + margin:.2f}"
    except Exception:
        return value_str


def get_max_dimension_with_margin(dimension_key: str, products: List[Dict], margin: float) -> str:
    """
    Retorna a maior dimensão entre todos os produtos e aplica a margem de embalagem.
    dimension_key: 'largura', 'comprimento', 'altura', 'peso', 'profundidade'
    """
    values = []
    for p in products:
        raw = p.get(dimension_key) or p.get("profundidade") if dimension_key == "comprimento" else p.get(dimension_key)
        cm = parse_dimension_to_cm(raw)
        if cm is not None:
            values.append(cm)

    if not values:
        return ""

    max_val = max(values)
    return f"{max_val + margin:.2f}"


def build_kit_dimensions(products: List[Dict]) -> Dict[str, str]:
    """
    Calcula as dimensões do kit:
    - Maior largura entre os produtos + 7cm
    - Maior comprimento (ou profundidade) entre os produtos + 7cm
    - Maior altura entre os produtos + 7cm
    - Maior peso entre os produtos + 2kg
    """
    def _max_dim(key: str, fallback_key: Optional[str] = None) -> str:
        vals = []
        for p in products:
            raw = p.get(key)
            if not raw and fallback_key:
                raw = p.get(fallback_key)
            cm = parse_dimension_to_cm(raw)
            if cm is not None:
                vals.append(cm)
        if not vals:
            return ""
        return f"{max(vals) + 7.0:.2f}"

    def _max_weight() -> str:
        vals = []
        for p in products:
            kg = parse_dimension_to_cm(p.get("peso"))
            if kg is not None:
                vals.append(kg)
        if not vals:
            return ""
        return f"{max(vals) + 2.0:.2f}"

    largura    = _max_dim("largura")
    comprimento = _max_dim("comprimento", fallback_key="profundidade")
    altura     = _max_dim("altura")
    peso       = _max_weight()

    dimensoes_lca = ""
    if largura and comprimento and altura:
        dimensoes_lca = f"{largura}x{comprimento}x{altura}"

    return {
        "largura_cm":    largura,
        "comprimento_cm": comprimento,
        "altura_cm":     altura,
        "dimensoes_lca": dimensoes_lca,
        "peso_kg":       peso,
    }


def merge_images(products: List[Dict], limit: int = 10) -> List[str]:
    """Combina as imagens de todos os produtos, removendo duplicatas, limitando a 'limit'."""
    seen = set()
    result = []
    for p in products:
        for url in p.get("image_urls", []):
            if url and url not in seen:
                seen.add(url)
                result.append(url)
                if len(result) >= limit:
                    return result
    return result
