"""
URL and Image Extractor for Leroy Merlin Products

This module extracts high-resolution product images (1800x1800) from Leroy Merlin product pages.
Uses simple regex patterns for fast and cost-effective extraction without AI.
"""
import re
import json
import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, unquote

# curl_cffi imita o fingerprint TLS do Chrome, contornando bot-detection em cloud.
# Fallback para requests padrão se não estiver disponível.
try:
    from curl_cffi import requests
    _IMPERSONATE = "chrome124"
    logger_tmp = logging.getLogger(__name__)
    logger_tmp.debug("curl_cffi carregado — usando impersonation Chrome")
except ImportError:
    import requests
    _IMPERSONATE = None
    logger_tmp = logging.getLogger(__name__)
    logger_tmp.warning("curl_cffi não encontrado — usando requests padrão")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Algolia — mesmas credenciais do monitoring_service.py
# Endpoint público da Leroy, funciona do Cloud Run sem proxy.
# ---------------------------------------------------------------------------
_ALGOLIA_URL = (
    "https://1cf3zt43zu-dsn.algolia.net/1/indexes/*/queries"
    "?x-algolia-agent=Algolia%20for%20JavaScript%20(5.10.2)%3B%20Browser"
)
_ALGOLIA_HEADERS = {
    "x-algolia-application-id": "1CF3ZT43ZU",
    "x-algolia-api-key":        "150c68d1c61fc1835826a57a203dab72",
    "User-Agent":               "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Content-Type":             "application/json",
}


def _fetch_product_from_algolia(product_url: str) -> Optional[Dict]:
    """
    Busca dados do produto no Algolia da Leroy usando o product_id extraído da URL.
    Funciona do Cloud Run sem proxy — Algolia é a API de busca pública da Leroy.

    Retorna dict com: titulo, marca, ean, modelo, image_urls e dimensões (quando
    disponíveis), ou None se não encontrar nenhum resultado.
    """
    m = re.search(r'(\d{5,})', product_url)
    if not m:
        logger.warning("[Algolia] product_id não encontrado na URL")
        return None

    product_id = m.group(1)

    try:
        import requests as _req   # requests padrão (não curl_cffi) para chamadas JSON
        payload = {
            "requests": [{
                "indexName": "production_products",
                "params":    f"query={product_id}&hitsPerPage=20&page=0",
            }]
        }
        r = _req.post(_ALGOLIA_URL, headers=_ALGOLIA_HEADERS, json=payload, timeout=15)
        r.raise_for_status()
        hits = r.json()["results"][0].get("hits", [])

        # Preferência: hit com product_id exato; fallback: primeiro resultado
        hit = next((h for h in hits if str(h.get("product_id", "")) == product_id), None)
        if not hit and hits:
            hit = hits[0]
        if not hit:
            logger.warning(f"[Algolia] Nenhum hit para product_id={product_id}")
            return None

        # ── Extrai campos via `attributes` (lista de {name, value/values}) ──────
        # Esse campo contém marca, modelo, EAN e dimensões para produtos sem
        # campos de topo nível (ex: produto 3548310941).
        attributes = hit.get("attributes") or []
        attr_map: Dict[str, str] = {}
        if isinstance(attributes, list):
            for attr in attributes:
                if not isinstance(attr, dict):
                    continue
                name = str(attr.get("name") or attr.get("label") or "").strip().lower()
                vals = attr.get("values") or []
                value = (
                    str(vals[0]).strip() if isinstance(vals, list) and vals
                    else str(attr.get("value") or "").strip()
                )
                if name and value:
                    attr_map[name] = value

        # ── Marca ────────────────────────────────────────────────────────────
        brand_raw = hit.get("brand", "")
        if isinstance(brand_raw, dict):
            brand = brand_raw.get("name", "")
        else:
            brand = str(brand_raw) if brand_raw else ""
        brand = (
            brand or hit.get("manufacturer", "") or hit.get("Manufacturer", "") or
            attr_map.get("marca") or attr_map.get("brand") or attr_map.get("fabricante") or
            "Marca não encontrada"
        )

        # ── EAN ──────────────────────────────────────────────────────────────
        # Campo `eans` é uma lista; campo `ean` é string direta
        eans_raw = hit.get("eans")
        if isinstance(eans_raw, list) and eans_raw:
            ean = str(eans_raw[0])
        else:
            ean = (
                hit.get("ean") or hit.get("gtin13") or hit.get("gtin") or hit.get("EAN") or
                attr_map.get("ean") or attr_map.get("código de barras") or "EAN não encontrado"
            )

        # ── Modelo ───────────────────────────────────────────────────────────
        modelo = (
            hit.get("model") or hit.get("Modelo") or hit.get("modelo") or
            attr_map.get("modelo") or attr_map.get("model") or attr_map.get("referência") or
            "Modelo não encontrado"
        )

        # ── Dimensões via attributes ──────────────────────────────────────
        DIM_KEYS = {
            "altura":       re.compile(r'altura', re.IGNORECASE),
            "largura":      re.compile(r'largura', re.IGNORECASE),
            "profundidade": re.compile(r'profundidade', re.IGNORECASE),
            "comprimento":  re.compile(r'comprimento', re.IGNORECASE),
            "peso":         re.compile(r'peso', re.IGNORECASE),
        }
        dimensoes_algolia: Dict[str, Optional[str]] = {k: None for k in DIM_KEYS}
        for raw_name, raw_value in attr_map.items():
            for dim_key, pattern in DIM_KEYS.items():
                if pattern.search(raw_name) and not dimensoes_algolia[dim_key]:
                    dimensoes_algolia[dim_key] = raw_value
                    break
        # Fallback: tenta campos de topo nível (produtos mais antigos)
        for k in DIM_KEYS:
            if not dimensoes_algolia[k]:
                dimensoes_algolia[k] = hit.get(k)

        # ── Dimensões do título como último fallback ──────────────────────
        # Ex: "... 72x90x90cm ..." → largura=72, comprimento=90, altura=90
        titulo_raw = hit.get("name", "")
        if not all(dimensoes_algolia.values()):
            dim_match = re.search(
                r'(\d+(?:[.,]\d+)?)\s*[xX]\s*(\d+(?:[.,]\d+)?)\s*[xX]\s*(\d+(?:[.,]\d+)?)\s*cm',
                titulo_raw
            )
            if dim_match:
                if not dimensoes_algolia["largura"]:
                    dimensoes_algolia["largura"] = dim_match.group(1).replace(",", ".")
                if not dimensoes_algolia["comprimento"]:
                    dimensoes_algolia["comprimento"] = dim_match.group(2).replace(",", ".")
                if not dimensoes_algolia["altura"]:
                    dimensoes_algolia["altura"] = dim_match.group(3).replace(",", ".")
                logger.info(f"[Algolia] Dimensões extraídas do título: {dim_match.group(0)}")

        # ── Imagens via Cloudinary (1800x1800) ───────────────────────────
        # Tenta: image (ID simples), images (lista de IDs), pictures (formato novo)
        image_id = (
            hit.get("image") or hit.get("imageId") or hit.get("imageUrl") or
            hit.get("imageURL") or hit.get("photo") or hit.get("thumbnail") or ""
        )
        image_ids_simple = hit.get("images") or ([image_id] if image_id else [])
        images: List[str] = [
            f"https://res.cloudinary.com/lmru-brazil/image/upload/"
            f"d_v1:static:product:placeholder.png/"
            f"w_1800,h_1800,c_pad,b_white,f_auto,q_auto/"
            f"v1/static/product/{iid}/"
            for iid in image_ids_simple if iid
        ]

        # Campo `pictures` — pode ser dict {micro/normal/big/superzoom: id}
        # ou lista de dicts/strings.
        def _cloudinary(iid: str) -> str:
            return (
                f"https://res.cloudinary.com/lmru-brazil/image/upload/"
                f"d_v1:static:product:placeholder.png/"
                f"w_1800,h_1800,c_pad,b_white,f_auto,q_auto/"
                f"v1/static/product/{iid}/"
            )

        pictures_raw = hit.get("pictures") or []

        if isinstance(pictures_raw, dict):
            # Estrutura: {"micro": "id", "normal": "id", "big": "id", "superzoom": "id"}
            # Cada valor é o mesmo ID — pega o superzoom (maior resolução)
            best_id = (
                pictures_raw.get("superzoom") or pictures_raw.get("big") or
                pictures_raw.get("normal") or pictures_raw.get("micro") or ""
            )
            if best_id:
                url = best_id if best_id.startswith("http") else _cloudinary(best_id)
                if url not in images:
                    images.append(url)
                    logger.debug(f"[Algolia] pictures (dict) → {best_id[:60]}")
        elif isinstance(pictures_raw, list):
            for pic in pictures_raw:
                if isinstance(pic, str):
                    url = pic if pic.startswith("http") else _cloudinary(pic)
                elif isinstance(pic, dict):
                    # Cada elemento pode ser {superzoom/big/normal/micro: id}
                    # ou {url: "...", id: "..."}
                    iid = (
                        pic.get("superzoom") or pic.get("big") or
                        pic.get("url") or pic.get("src") or pic.get("large") or
                        pic.get("id") or pic.get("imageId") or pic.get("image") or ""
                    )
                    url = iid if iid.startswith("http") else (_cloudinary(iid) if iid else "")
                else:
                    url = ""
                if url and url not in images:
                    images.append(url)

        # Log diagnóstico — mostra o valor real do campo pictures
        logger.debug(
            f"[Algolia] pictures raw = {json.dumps(hit.get('pictures'), ensure_ascii=False)[:300]}"
        )
        if not images:
            logger.warning(
                f"[Algolia] Sem imagens para product_id={product_id}. "
                f"pictures={str(hit.get('pictures', []))[:120]}"
            )

        logger.info(
            f"[Algolia] ✅ product_id={product_id} | "
            f"titulo={titulo_raw[:60]} | imagens={len(images)} | "
            f"marca={brand} | ean={ean}"
        )

        return {
            "titulo":       titulo_raw,
            "marca":        brand,
            "ean":          str(ean),
            "modelo":       str(modelo),
            "image_urls":   images,
            **dimensoes_algolia,
        }

    except Exception as e:
        logger.error(f"[Algolia] Falhou para {product_url[:70]}: {e}")
        return None


def _fetch_product_from_v3_api(product_url: str) -> Optional[Dict]:
    """
    Busca dados completos do produto na API v3 da Leroy Merlin.
    Mesmo endpoint family do sellers API — funciona do Cloud Run sem proxy.

    Retorna dict com: titulo, marca, ean, modelo, image_urls e dimensões,
    ou None se a chamada falhar.
    """
    m = re.search(r'(\d{5,})', product_url)
    if not m:
        return None

    product_id = m.group(1)
    url = f"https://www.leroymerlin.com.br/api/v3/products/{product_id}"
    headers = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Referer":         "https://www.leroymerlin.com.br/",
        "Origin":          "https://www.leroymerlin.com.br",
        "x-device":        "desktop",
        "x-region":        "grande_sao_paulo",
    }

    try:
        if _IMPERSONATE:
            r = requests.get(url, headers=headers, impersonate=_IMPERSONATE, timeout=10)
        else:
            import requests as _req
            r = _req.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            logger.warning(f"[v3 API] status {r.status_code} para produto {product_id}")
            return None

        data = r.json().get("data", r.json())

        # ── Título ───────────────────────────────────────────────────────────
        titulo = data.get("name") or data.get("title") or data.get("productName") or ""

        # ── Marca ────────────────────────────────────────────────────────────
        brand_raw = data.get("brand", {})
        if isinstance(brand_raw, dict):
            marca = brand_raw.get("name", "") or brand_raw.get("brandName", "")
        else:
            marca = str(brand_raw) if brand_raw else ""

        # ── EAN ─────────────────────────────────────────────────────────────
        ean = (
            data.get("ean") or data.get("gtin13") or data.get("gtin") or
            data.get("EAN") or "EAN não encontrado"
        )

        # ── Modelo ───────────────────────────────────────────────────────────
        modelo = data.get("model") or data.get("modelo") or "Modelo não encontrado"

        # ── Dimensões via characteristics ─────────────────────────────────
        FIELD_MAP = {
            "altura":       re.compile(r'^altura$', re.IGNORECASE),
            "largura":      re.compile(r'^largura$', re.IGNORECASE),
            "profundidade": re.compile(r'^profundidade$', re.IGNORECASE),
            "comprimento":  re.compile(r'^comprimento$', re.IGNORECASE),
            "peso":         re.compile(r'^peso', re.IGNORECASE),
        }
        dimensoes: Dict[str, Optional[str]] = {k: None for k in FIELD_MAP}

        characteristics = (
            data.get("characteristics") or
            data.get("technicalSpecifications") or
            data.get("specifications") or []
        )
        for item in characteristics:
            if not isinstance(item, dict):
                continue
            name  = item.get("name", "") or item.get("key", "")
            value = item.get("value", "") or item.get("values", [""])[0] if isinstance(item.get("values"), list) else item.get("value", "")
            for key, pattern in FIELD_MAP.items():
                if pattern.match(str(name).strip()) and not dimensoes[key]:
                    dimensoes[key] = str(value).strip()
                    break

        # ── Imagens ──────────────────────────────────────────────────────────
        images_raw = data.get("images") or data.get("medias") or data.get("photos") or []
        images = []
        if isinstance(images_raw, list):
            for img in images_raw:
                if isinstance(img, str) and img.startswith("http"):
                    images.append(img)
                elif isinstance(img, dict):
                    for key in ("url", "src", "large", "zoom", "fullImage"):
                        u = img.get(key, "")
                        if u and u.startswith("http"):
                            images.append(u)
                            break

        logger.info(
            f"[v3 API] ✅ product_id={product_id} | titulo={titulo[:60]} | "
            f"dims={[k for k,v in dimensoes.items() if v]} | imagens={len(images)}"
        )

        return {
            "titulo":       titulo,
            "marca":        marca or "Marca não encontrada",
            "ean":          str(ean),
            "modelo":       str(modelo),
            "image_urls":   images[:10],
            **dimensoes,
        }

    except Exception as e:
        logger.warning(f"[v3 API] Falhou para {product_url[:70]}: {e}")
        return None


def _fetch(url: str, headers: dict, timeout: int = 20):
    """
    Faz GET usando curl_cffi (Chrome fingerprint) como primário.
    ScraperAPI usado apenas como último fallback se:
      - curl_cffi retornar status != 200, OU
      - HTML retornado for muito curto (< 10 KB — indica resposta bloqueada)

    Preço não passa mais por aqui: é obtido direto do /api/v3/products/{id}/sellers.
    """
    # --- tentativa primária: curl_cffi / requests padrão ---
    try:
        if _IMPERSONATE:
            r = requests.get(url, impersonate=_IMPERSONATE, timeout=timeout)
        else:
            r = requests.get(url, headers=headers, timeout=timeout)

        if r.status_code == 200 and len(r.text) >= 10_000:
            return r

        logger.warning(
            f"_fetch primario insuficiente (status={r.status_code}, "
            f"len={len(getattr(r, 'text', ''))}). Tentando ScraperAPI..."
        )
    except Exception as e:
        logger.warning(f"_fetch primario falhou ({e}). Tentando ScraperAPI...")

    # --- fallback: ScraperAPI ---
    try:
        from app.core.config import settings
        api_key = settings.SCRAPER_API_KEY
        if api_key:
            proxy_url = f"http://api.scraperapi.com?api_key={api_key}&url={url}"
            logger.info(f"[ScraperAPI fallback] {url[:60]}")
            import requests as _req
            return _req.get(proxy_url, timeout=timeout)
    except Exception as e:
        logger.error(f"ScraperAPI fallback falhou: {e}")

    # se chegou aqui, retorna o que temos (pode ser ruim, mas evita crash)
    if _IMPERSONATE:
        return requests.get(url, impersonate=_IMPERSONATE, timeout=timeout)
    return requests.get(url, headers=headers, timeout=timeout)


def extract_images_1800(product_url: str) -> List[str]:
    """
    Extract high-resolution image URLs (1800x1800) from a Leroy Merlin product page.
    
    This function uses regex patterns to extract images without AI, making it fast and free.
    It's designed to work with Leroy Merlin's CDN structure.
    
    Args:
        product_url: URL of the Leroy Merlin product page
        
    Returns:
        List of image URLs in 1800x1800 resolution
        
    Example:
        >>> urls = extract_images_1800("https://www.leroymerlin.com.br/produto_123456")
        >>> print(urls)
        ['https://cdn.leroymerlin.com.br/products/..._1800x1800.jpg', ...]
    """
    logger.info(f"📥 Downloading HTML from: {product_url}")
    
    # Headers to simulate a browser and avoid blocking
    # IMPORTANT: Do NOT include Accept-Encoding to avoid gzip compression
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    try:
        response = _fetch(product_url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text

        logger.info(f"✅ HTML downloaded! Size: {len(html):,} characters")

        # Strategy: collect candidate URLs from multiple places and then
        # filter them to only those that belong to the product referenced
        # by the input URL (to avoid picking unrelated images).
        candidates: List[str] = []

        # 1) Try to extract explicit "zoom" entries (JS/JSON embedded)
        try:
            pattern_zoom = re.compile(r'"zoom"\s*:\s*"(https://cdn.leroymerlin.com.br/products/[^"]*1800x1800\.[^"]+)"', re.IGNORECASE | re.DOTALL)
            zooms = pattern_zoom.findall(html)
            candidates.extend(zooms)
        except Exception:
            logger.debug("⚠️  zoom pattern failed", exc_info=True)

        # 2) Broad search for any 1800x1800 images (accept .jpg .jpeg .png)
        try:
            pattern_1800 = re.compile(r'https://cdn\.leroymerlin\.com\.br/products[^"\s]+1800x1800\.(?:jpe?g|png)', re.IGNORECASE)
            matches_1800 = pattern_1800.findall(html)
            candidates.extend(matches_1800)
        except Exception:
            logger.debug("⚠️  1800 pattern failed", exc_info=True)

        # 3) Fallback: extract any CDN product images (all sizes) from src/srcset/data-src/data-srcset
        try:
            # src and data-src
            pattern_src = re.compile(r'(?:src|data-src)=["\'](https://cdn.leroymerlin.com.br/products[^"\']+)["\']', re.IGNORECASE)
            candidates.extend(pattern_src.findall(html))

            # srcset/data-srcset entries (comma-separated list)
            pattern_srcset = re.compile(r'(?:srcset|data-srcset)=["\']([^"\']+)["\']', re.IGNORECASE)
            for srcset_block in pattern_srcset.findall(html):
                parts = [p.strip() for p in srcset_block.split(',') if p.strip()]
                for part in parts:
                    # part like 'https://... 600w' or just URL
                    url = part.split()[0]
                    if url.startswith('https://cdn.leroymerlin.com.br/products'):
                        candidates.append(url)
        except Exception:
            logger.debug("⚠️  src/srcset extraction failed", exc_info=True)

        # 4) Meta og:image as fallback
        try:
            og_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
            if og_match:
                og_url = og_match.group(1)
                if og_url.startswith('https://cdn.leroymerlin.com.br/products'):
                    candidates.append(og_url)
        except Exception:
            logger.debug("⚠️  og:image extraction failed", exc_info=True)

        # Normalize, deduplicate, and encode commas while preserving order
        normalized: List[str] = []
        for u in candidates:
            if not u:
                continue
            # Unescape common escapes
            u = u.replace('\\/', '/')
            u = unquote(u)
            # Encode commas as %2C for Mercado Livre compatibility
            u = u.replace(',', '%2C')
            if u not in normalized:
                normalized.append(u)

        # Determine product identifier to filter relevant images
        product_id = None
        try:
            # Simplest and more reliable: find any long numeric segment in URL
            m = re.search(r'(\d{5,})', product_url)
            if m:
                product_id = m.group(1)
        except Exception:
            product_id = None

        if product_id:
            filtered = [u for u in normalized if product_id in u]
        else:
            # If we can't derive an ID, try to match by last path token
            try:
                path = urlparse(product_url).path.rstrip('/')
                last = path.split('/')[-1]
                filtered = [u for u in normalized if last and last.split('_')[0] in u]
            except Exception:
                filtered = normalized

        # Filtrar apenas imagens 1800x1800
        only_1800 = [u for u in filtered if '1800x1800' in u]
        final_order: List[str] = only_1800 if only_1800 else filtered

        if not final_order:
            logger.warning("⚠️  No product-specific images found; returning best-effort list")
            final_order = normalized

        # Limit results to at most 10 images (marketplace requirement)
        if len(final_order) > 10:
            final_order = final_order[:10]
            logger.info("ℹ️  Limiting image list to 10 items")

        logger.info(f"✅ Found {len(final_order)} candidate images")
        return final_order
        
    except Exception as e:
        logger.error(f"❌ Error downloading HTML: {e}")
        return []


def _fetch_price_from_sellers_api(product_url: str) -> Optional[str]:
    """
    Busca o preço cheio direto do endpoint /api/v3/products/{id}/sellers.

    Vantagens sobre o HTML:
      - Endpoint JSON não é bloqueado por IP (nem localmente nem no Cloud Run)
      - Não consome créditos do ScraperAPI
      - Retorna price.from = preço sem desconto, price.to = preço promocional
        → usamos price.from (o mais alto)

    Retorna preço formatado "R$ X.XXX,XX" ou None se falhar.
    """
    m = re.search(r'(\d{5,})', product_url)
    if not m:
        logger.warning("_fetch_price_from_sellers_api: product_id não encontrado na URL")
        return None

    product_id = m.group(1)
    url = f"https://www.leroymerlin.com.br/api/v3/products/{product_id}/sellers"
    headers = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Referer":         "https://www.leroymerlin.com.br/",
        "Origin":          "https://www.leroymerlin.com.br",
        "x-device":        "desktop",
        "x-region":        "grande_sao_paulo",
    }

    try:
        # Chama diretamente com curl_cffi (sem ScraperAPI — endpoint não é bloqueado)
        if _IMPERSONATE:
            r = requests.get(url, headers=headers, impersonate=_IMPERSONATE, timeout=10)
        else:
            import requests as _req
            r = _req.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            logger.warning(f"sellers API status {r.status_code} para produto {product_id}")
            return None

        data = r.json()
        sellers = data.get("data", [])
        if not sellers:
            logger.warning(f"sellers API: sem sellers para produto {product_id}")
            return None

        price = sellers[0].get("pricing", {}).get("price", {})
        # price.from = preço cheio (sem desconto); price.to = preço promocional
        price_from = price.get("from")
        price_to   = price.get("to")

        best = price_from or price_to
        if not best:
            return None

        price_float = float(best)
        price_str = (
            f"R$ {price_float:,.2f}"
            .replace(",", "X").replace(".", ",").replace("X", ".")
        )
        logger.info(
            f"[sellers API] produto={product_id} | from={price_from} | to={price_to} "
            f"-> usando {price_str}"
        )
        return price_str

    except Exception as e:
        logger.warning(f"[sellers API] falhou para {product_url[:60]}: {e}")
        return None


def extract_price_from_html(html: str) -> str:
    """
    Extract the HIGHEST product price from HTML using multiple strategies.
    
    This function extracts all available prices (à vista, parcelado, original)
    and returns the HIGHEST value found.
    
    Strategies used:
    1. JSON-LD Schema.org structured data (most reliable)
    2. HTML pattern matching for all price types
    3. Fallback to any R$ pattern
    
    Args:
        html: HTML content of the product page
        
    Returns:
        Highest price found as string (e.g., "R$ 1.190,43") or None
        
    Example:
        >>> price = extract_price_from_html(html)
        >>> print(price)
        'R$ 1.190,43'  # Sempre o maior preço
    """
    all_prices = []  # Lista para armazenar todos os preços encontrados
    
    logger.info("🔍 Extracting ALL prices from HTML to find the highest...")
    
    # ============================================================================
    # STRATEGY 1: JSON-LD Schema.org (MOST RELIABLE)
    # ============================================================================
    try:
        # Find JSON-LD Product schema
        json_ld_pattern = r'<script\s+type="application/ld\+json">(.+?)</script>'
        json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)
        
        for json_block in json_blocks:
            try:
                data = json.loads(json_block)
                
                # Check if it's a Product
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        price_raw = offers.get('price')
                        if price_raw:
                            # Add to all_prices list
                            price_float = float(price_raw)
                            price_str = f"R$ {price_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                            all_prices.append(price_str)
                            logger.info(f"✅ Price from JSON-LD: {price_str}")
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.debug(f"⚠️  Error parsing JSON block: {e}")
                continue
    except Exception as e:
        logger.debug(f"⚠️  Strategy 1 (JSON-LD) failed: {e}")
    
    # ============================================================================
    # STRATEGY 2: HTML pattern with "à vista" text
    # ============================================================================
    try:
        # Look for price followed by "à vista"
        # Pattern: R$ X.XXX,XX followed by text containing "à vista" or "a vista"
        pattern_vista = r'(R\$\s*[\d.]+,\d{2})\s*(?:</span>)?\s*(?:<[^>]+>)*\s*(?:à\s*vista|a\s*vista)'
        matches = re.findall(pattern_vista, html, re.IGNORECASE)
        for match in matches:
            all_prices.append(match)
            logger.info(f"✅ Price from 'à vista' pattern: {match}")
    except Exception as e:
        logger.debug(f"⚠️  Strategy 2 (à vista pattern) failed: {e}")
    
    # ============================================================================
    # STRATEGY 3: HTML pattern with "a prazo" / "parcelado"
    # ============================================================================
    try:
        # Look for "a prazo" or "em até Xx"
        pattern_parcelado = r'(R\$\s*[\d.]+,\d{2})\s*(?:</span>)?\s*(?:<[^>]+>)*\s*(?:a\s*prazo|em\s*até)'
        matches = re.findall(pattern_parcelado, html, re.IGNORECASE)
        for match in matches:
            all_prices.append(match)
            logger.info(f"✅ Price from 'parcelado' pattern: {match}")
    except Exception as e:
        logger.debug(f"⚠️  Strategy 3 (parcelado pattern) failed: {e}")
    
    # ============================================================================
    # STRATEGY 4: HTML pattern with large bold price (likely main price)
    # ============================================================================
    try:
        # Look for large heading price (heading-lg, heading-xl) - usually the main price
        pattern_heading = r'heading-(?:lg|xl|2xl|md)[^>]*>[^<]*?(R\$\s*[\d.]+,\d{2})'
        matches = re.findall(pattern_heading, html)
        for match in matches:
            all_prices.append(match)
            logger.info(f"✅ Price from heading pattern: {match}")
    except Exception as e:
        logger.debug(f"⚠️  Strategy 4 (heading pattern) failed: {e}")
    
    # ============================================================================
    # STRATEGY 5: priceWithoutDiscounts (preço cheio antes do desconto)
    # Aparece no JSON de paymentMethods embutido na página
    # ============================================================================
    try:
        pattern_full = re.compile(r'"priceWithoutDiscounts"\s*:\s*([\d]+\.[\d]+)', re.IGNORECASE)
        matches_full = pattern_full.findall(html)
        for val in matches_full:
            price_float = float(val)
            if price_float > 0:
                price_str = f"R$ {price_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                if price_str not in all_prices:
                    all_prices.append(price_str)
                    logger.info(f"✅ Price from priceWithoutDiscounts: {price_str}")
    except Exception as e:
        logger.debug(f"⚠️  Strategy 5 (priceWithoutDiscounts) failed: {e}")

    # ============================================================================
    # STRATEGY 6: preço tachado no HTML (classe line-through = preço original)
    # ============================================================================
    try:
        pattern_strike = re.compile(
            r'class="[^"]*line-through[^"]*"[^>]*>\s*R\$\s*([\d.,]+)', re.IGNORECASE
        )
        matches_strike = pattern_strike.findall(html)
        for val in matches_strike:
            clean = val.replace('.', '').replace(',', '.')
            price_float = float(clean)
            if price_float > 0:
                price_str = f"R$ {price_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                if price_str not in all_prices:
                    all_prices.append(price_str)
                    logger.info(f"✅ Price from line-through (preço cheio): {price_str}")
    except Exception as e:
        logger.debug(f"⚠️  Strategy 6 (line-through) failed: {e}")

    # ============================================================================
    # FALLBACK: Use any R$ pattern if nothing found
    # ============================================================================
    if not all_prices:
        try:
            # Get all prices and add first 5 to avoid noise
            fallback_prices = re.findall(r'R\$\s*[\d.]+,\d{2}', html)[:5]
            if fallback_prices:
                all_prices.extend(fallback_prices)
                logger.warning(f"⚠️  Using fallback prices: {fallback_prices}")
        except Exception as e:
            logger.debug(f"⚠️  Fallback strategy failed: {e}")
    
    # ============================================================================
    # FIND HIGHEST PRICE
    # ============================================================================
    logger.info(f"💰 Todos os preços encontrados: {all_prices}")

    if not all_prices:
        logger.error("❌ No price found in HTML")
        return None
    
    # Parse all prices to float for comparison
    def parse_price(price_str: str) -> float:
        """Convert 'R$ 1.190,43' to float 1190.43"""
        try:
            # Remove R$ and spaces
            clean = price_str.replace('R$', '').strip()
            # Remove thousand separator (.)
            clean = clean.replace('.', '')
            # Replace decimal separator (,) with (.)
            clean = clean.replace(',', '.')
            return float(clean)
        except:
            return 0.0
    
    # Find highest price
    price_values = [(p, parse_price(p)) for p in all_prices]
    highest_price_str, highest_price_val = max(price_values, key=lambda x: x[1])
    
    logger.info(f"💰 Found {len(all_prices)} prices. HIGHEST: {highest_price_str} (R$ {highest_price_val:.2f})")
    
    return highest_price_str


def extract_brand_from_html(html: str) -> str:
    """
    Extract product brand from HTML using JSON pattern matching.
    
    Tries these patterns:
    1. "brand":"BrandName" (simple string format)
    2. "brand":{"@type":"Brand","name":"BrandName"} (Schema.org format)
    
    Args:
        html: HTML content of the product page
        
    Returns:
        Brand name or "Marca não encontrada" if not found
        
    Example:
        >>> brand = extract_brand_from_html(html)
        >>> print(brand)
        'Toyama'
    """
    logger.info("🔍 Extracting brand from HTML...")
    
    # ============================================================================
    # STRATEGY 1: Simple string format - "brand":"BrandName"
    # ============================================================================
    try:
        pattern_simple = r'"brand"\s*:\s*"([^"]+)"'
        match = re.search(pattern_simple, html)
        if match:
            brand = match.group(1).strip()
            if brand and brand.lower() != 'null':
                logger.info(f"✅ Brand found (simple format): {brand}")
                return brand
    except Exception as e:
        logger.debug(f"⚠️  Strategy 1 (simple brand) failed: {e}")
    
    # ============================================================================
    # STRATEGY 2: Schema.org format - "brand":{"@type":"Brand","name":"BrandName"}
    # ============================================================================
    try:
        pattern_schema = r'"brand"\s*:\s*\{\s*"@type"\s*:\s*"Brand"\s*,\s*"name"\s*:\s*"([^"]+)"'
        match = re.search(pattern_schema, html)
        if match:
            brand = match.group(1).strip()
            logger.info(f"✅ Brand found (Schema.org format): {brand}")
            return brand
    except Exception as e:
        logger.debug(f"⚠️  Strategy 2 (Schema.org brand) failed: {e}")
    
    logger.warning("⚠️  No brand found in HTML")
    return "Marca não encontrada"


def extract_ean_from_html(html: str) -> str:
    """
    Extract product EAN code from HTML using JSON pattern matching.
    
    Looks for "ean":"XXXXXXXXXXXXX" pattern in the HTML.
    Returns "EAN não encontrado" if not found or if value is null.
    
    Args:
        html: HTML content of the product page
        
    Returns:
        EAN code or "EAN não encontrado" if not found or null
        
    Example:
        >>> ean = extract_ean_from_html(html)
        >>> print(ean)
        '7898438035496'
    """
    logger.info("🔍 Extracting EAN from HTML...")
    
    try:
        # Pattern 1: Standard JSON format with quotes "ean":"1234567890123"
        pattern_ean = r'"ean"\s*:\s*"([0-9]+)"'
        match = re.search(pattern_ean, html)
        if match:
            ean = match.group(1).strip()
            logger.info(f"✅ EAN found (pattern 1): {ean}")
            return ean
        
        # Pattern 2: Escaped quotes format \"ean\":\"1234567890123\" (common in embedded HTML/JS)
        pattern_escaped = r'\\"ean\\"\s*:\s*\\"([0-9]+)\\"'
        match = re.search(pattern_escaped, html)
        if match:
            ean = match.group(1).strip()
            logger.info(f"✅ EAN found (pattern 2 - escaped): {ean}")
            return ean
        
        # Check if EAN is explicitly null
        pattern_null = r'"ean"\s*:\s*null'
        if re.search(pattern_null, html):
            logger.info("ℹ️  EAN is null (product without EAN code)")
            return "EAN não encontrado"
        
    except Exception as e:
        logger.debug(f"⚠️  EAN extraction failed: {e}")
    
    logger.warning("⚠️  No EAN found in HTML")
    return "EAN não encontrado"


def extract_title_from_html(html: str) -> Optional[str]:
    """
    Extract product title from HTML using multiple strategies.
    
    Tries these strategies:
    1. JSON-LD Schema.org "name" field
    2. H1 tag content
    3. Meta og:title
    
    Args:
        html: HTML content of the product page
        
    Returns:
        Product title or None if not found
        
    Example:
        >>> title = extract_title_from_html(html)
        >>> print(title)
        'Roçadeira a Gasolina Toyama TBC43X 1,7Hp'
    """
    logger.info("🔍 Extracting title from HTML...")
    
    # ============================================================================
    # STRATEGY 1: JSON-LD Schema.org (MOST RELIABLE)
    # ============================================================================
    try:
        json_ld_pattern = r'<script\s+type="application/ld\+json">(.+?)</script>'
        json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)
        
        for json_block in json_blocks:
            try:
                data = json.loads(json_block)
                
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    title = data.get('name')
                    if title:
                        logger.info(f"✅ Title from JSON-LD: {title}")
                        return title.strip()
            except (json.JSONDecodeError, ValueError, KeyError):
                continue
    except Exception as e:
        logger.debug(f"⚠️  Strategy 1 (JSON-LD) failed: {e}")
    
    # ============================================================================
    # STRATEGY 2: H1 tag
    # ============================================================================
    try:
        h1_pattern = r'<h1[^>]*>(.+?)</h1>'
        h1_match = re.search(h1_pattern, html, re.DOTALL)
        if h1_match:
            # Clean HTML tags from h1 content
            h1_text = re.sub(r'<[^>]+>', '', h1_match.group(1))
            title = h1_text.strip()
            if title:
                logger.info(f"✅ Title from H1: {title}")
                return title
    except Exception as e:
        logger.debug(f"⚠️  Strategy 2 (H1) failed: {e}")
    
    # ============================================================================
    # STRATEGY 3: Meta og:title
    # ============================================================================
    try:
        og_pattern = r'<meta\s+property="og:title"\s+content="([^"]+)"'
        og_match = re.search(og_pattern, html)
        if og_match:
            title = og_match.group(1).strip()
            logger.info(f"✅ Title from og:title: {title}")
            return title
    except Exception as e:
        logger.debug(f"⚠️  Strategy 3 (og:title) failed: {e}")
    
    logger.error("❌ No title found in HTML")
    return None


def extract_model_from_html(html: str, product_url: str = None) -> Optional[str]:
    """
    Extrai o modelo do produto do HTML da Leroy Merlin.
    Procura por 'Modelo' na tabela de especificações (JSON embutido ou HTML), semelhante à extração da marca.
    
    Se não encontrar pelas estratégias de regex, usa Gemini AI como fallback (custo ~$0.000014).
    
    Args:
        html: HTML content of the product page
        product_url: URL do produto (necessária para fallback com Gemini)
        
    Returns:
        Nome do modelo ou "Modelo não encontrado"
    """
    # Estratégia 1: Buscar na tabela de especificações técnica (Visual/HTML)
    # Procura por um texto que contenha "Modelo" e tenta pegar o próximo valor
    import bs4
    soup = bs4.BeautifulSoup(html, 'html.parser')
    label = soup.find(text=re.compile(r'^Modelo$', re.IGNORECASE))
    if label:
        try:
            value = label.find_parent().find_next_sibling() or label.find_parent('tr').find_all('td')[-1]
            if value:
                model_found = value.get_text(strip=True)
                if model_found:
                    logger.info(f"✅ Modelo found (Strategy 1 - HTML table): {model_found}")
                    return model_found
        except Exception:
            pass

    # Estratégia 2: Regex flexível no bloco JSON/Next.js State
    match = re.search(r'["\']Modelo["\']\s*:\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
    if match:
        model_found = match.group(1).strip()
        logger.info(f"✅ Modelo found (Strategy 2 - JSON block): {model_found}")
        return model_found

    # Estratégia 3: Busca no objeto de características (characteristics)
    match_carac = re.search(r'"characteristics"\s*:\s*\[(.*?)\]', html, re.DOTALL)
    if match_carac:
        carac_block = match_carac.group(1)
        match_modelo = re.search(r'\{"name"\s*:\s*"Modelo"\s*,\s*"value"\s*:\s*"([^"]+)"\}', carac_block)
        if match_modelo:
            model_value = match_modelo.group(1).strip()
            logger.info(f"✅ Modelo found (Strategy 3 - characteristics): {model_value}")
            return model_value

    # ============================================================================
    # FALLBACK: Usar Gemini AI se não encontrou pelas estratégias de regex
    # ============================================================================
    logger.warning("⚠️ Campo 'Modelo' não encontrado por regex. Tentando com Gemini AI...")
    
    if product_url:
        try:
            from app.services.leroy_merlin.scraper.gemini_client import get_gemini_client
            
            gemini_client = get_gemini_client()
            model_from_ai = gemini_client.extract_model_from_url(product_url)
            
            if model_from_ai:
                logger.info(f"✅ Modelo encontrado com Gemini (Fallback): {model_from_ai}")
                return model_from_ai
            else:
                logger.warning("⚠️ Gemini não conseguiu identificar o modelo")
        except Exception as e:
            logger.error(f"❌ Erro ao usar Gemini como fallback: {str(e)}")
    
    logger.error("❌ Nenhum modelo encontrado após todas as estratégias")
    return "Modelo não encontrado"


def extract_dimensions_from_html(html: str) -> Dict[str, Optional[str]]:
    """
    Extract product physical dimensions from HTML.

    Looks for these fields (case-insensitive): Altura, Largura, Profundidade,
    Comprimento, Peso do Produto (also "Peso").

    Strategies:
    1. JSON "characteristics" array embedded in the page (fastest)
    2. HTML <th>/<td> specification table (fallback)

    Args:
        html: HTML content of the product page

    Returns:
        Dictionary with keys: altura, largura, profundidade, comprimento, peso
        Each value is a string (e.g. "2,55 m") or None if not found.
    """
    logger.info("🔍 Extracting dimensions from HTML...")

    FIELDS = {
        "altura":       re.compile(r'^altura$', re.IGNORECASE),
        "largura":      re.compile(r'^largura$', re.IGNORECASE),
        "profundidade": re.compile(r'^profundidade$', re.IGNORECASE),
        "comprimento":  re.compile(r'^comprimento$', re.IGNORECASE),
        "peso":         re.compile(r'^peso', re.IGNORECASE),
    }

    result: Dict[str, Optional[str]] = {k: None for k in FIELDS}

    def _match_field(name: str) -> Optional[str]:
        for key, pattern in FIELDS.items():
            if pattern.match(name.strip()):
                return key
        return None

    # =========================================================================
    # STRATEGY 1: JSON "characteristics" block
    # =========================================================================
    try:
        carac_match = re.search(r'"characteristics"\s*:\s*\[(.*?)\]', html, re.DOTALL)
        if carac_match:
            items = re.findall(r'\{"name"\s*:\s*"([^"]+)"\s*,\s*"value"\s*:\s*"([^"]+)"\}', carac_match.group(1))
            for name, value in items:
                key = _match_field(name)
                if key and result[key] is None:
                    result[key] = value.strip()
                    logger.info(f"✅ {key} from JSON characteristics: {value.strip()}")
    except Exception as e:
        logger.debug(f"⚠️  Strategy 1 (characteristics JSON) failed: {e}")

    # Check if all fields found already
    if all(v is not None for v in result.values()):
        return result

    # =========================================================================
    # STRATEGY 2: HTML <th><strong>Label</strong></th><td>Value</td> table
    # =========================================================================
    try:
        import bs4
        soup = bs4.BeautifulSoup(html, 'html.parser')
        for th in soup.find_all('th'):
            label_text = th.get_text(strip=True)
            key = _match_field(label_text)
            if key and result[key] is None:
                td = th.find_next_sibling('td')
                if td:
                    value = td.get_text(strip=True)
                    result[key] = value
                    logger.info(f"✅ {key} from HTML table: {value}")
    except Exception as e:
        logger.debug(f"⚠️  Strategy 2 (HTML table) failed: {e}")

    missing = [k for k, v in result.items() if v is None]
    if missing:
        logger.warning(f"⚠️  Dimensions not found: {missing}")

    return result


def extract_product_data(product_url: str) -> Dict[str, any]:
    """
    Extract complete product data (title, prices, images, brand, EAN) from a Leroy Merlin URL.
    
    This is a comprehensive extraction function that gets all product information
    using Python regex patterns - no AI, no extra cost, 100% deterministic.
    
    Args:
        product_url: URL of the Leroy Merlin product page
        
    Returns:
        Dictionary with extracted data:
        {
            "url": str,
            "titulo": str,
            "preco": str (highest price found),
            "marca": str,
            "ean": str,
            "image_urls": List[str],
            "success": bool,
            "error": str (if failed)
        }
    """
    logger.info(f"📥 Extracting full product data from: {product_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    titulo = marca = ean = modelo = None
    image_urls: List[str] = []
    dimensoes: Dict[str, Optional[str]] = {k: None for k in ("altura", "largura", "profundidade", "comprimento", "peso")}
    html_available = False

    # -----------------------------------------------------------------------
    # ESTRATÉGIA 1: Algolia (funciona do Cloud Run sem proxy)
    # -----------------------------------------------------------------------
    algolia = _fetch_product_from_algolia(product_url)
    if algolia and algolia.get("titulo"):
        titulo      = algolia["titulo"]
        marca       = algolia["marca"]
        ean         = algolia["ean"]
        modelo      = algolia["modelo"]
        image_urls  = algolia["image_urls"]
        dimensoes   = {k: algolia.get(k) for k in dimensoes}
        logger.info(f"[Algolia] Dados obtidos com sucesso: {titulo[:60]}")
    else:
        logger.warning("[Algolia] Sem resultado — tentando APIs seguintes...")

    # -----------------------------------------------------------------------
    # ESTRATÉGIA 2: API v3 da Leroy (funciona do Cloud Run sem proxy)
    # Complementa dimensões, EAN, modelo e imagens que o Algolia não retornou.
    # -----------------------------------------------------------------------
    v3 = _fetch_product_from_v3_api(product_url)
    if v3:
        if not titulo or titulo == "":
            titulo = v3.get("titulo", "") or titulo
        if not marca or marca == "Marca não encontrada":
            marca = v3.get("marca") or marca
        if not ean or ean == "EAN não encontrado":
            ean = v3.get("ean") or ean
        if not modelo or modelo == "Modelo não encontrado":
            modelo = v3.get("modelo") or modelo
        # Dimensões: preenche os campos que ainda estão vazios
        for k in dimensoes:
            if not dimensoes[k]:
                dimensoes[k] = v3.get(k)
        # Imagens: se a v3 trouxe mais imagens, usa (senão mantém Algolia)
        if v3.get("image_urls") and len(v3["image_urls"]) > len(image_urls):
            image_urls = v3["image_urls"]

    # -----------------------------------------------------------------------
    # ESTRATÉGIA 3: HTML via curl_cffi; ESTRATÉGIA 4: ScraperAPI (último recurso)
    # Tenta complementar com HTML quando disponível (funciona localmente).
    # -----------------------------------------------------------------------
    try:
        response = _fetch(product_url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text

        if len(html) < 10_000:
            raise ValueError(f"HTML insuficiente ({len(html)} chars) — provavelmente bloqueado")

        html_available = True
        logger.info(f"✅ HTML disponível ({len(html):,} chars) — complementando dados")

        # Preenche apenas campos ainda ausentes (Algolia tem prioridade)
        if not titulo:
            titulo = extract_title_from_html(html)
        if not marca or marca == "Marca não encontrada":
            marca = extract_brand_from_html(html)
        if not ean or ean == "EAN não encontrado":
            ean = extract_ean_from_html(html)
        if not modelo or modelo == "Modelo não encontrado":
            modelo = extract_model_from_html(html, product_url)

        # Dimensões: HTML é a fonte mais confiável
        dims_html = extract_dimensions_from_html(html)
        for k in dimensoes:
            if not dimensoes[k]:
                dimensoes[k] = dims_html.get(k)

        # Imagens: prefere 1800x1800 do CDN quando HTML disponível
        imgs_html = extract_images_1800(product_url)
        if imgs_html:
            image_urls = imgs_html

    except Exception as e:
        if not titulo:
            # Nem Algolia nem HTML funcionaram
            logger.error(f"❌ Todos os métodos falharam: {e}")
            return {
                "url": product_url, "titulo": "", "preco": "",
                "marca": "Marca não encontrada", "ean": "EAN não encontrado",
                "modelo": "Modelo não encontrado", "image_urls": [],
                "success": False, "error": str(e),
            }
        logger.warning(f"HTML indisponível ({e}) — usando apenas dados do Algolia")

    # -----------------------------------------------------------------------
    # ESTRATÉGIA 5: Gemini por URL — fallback para marca e modelo
    # Roda sempre que algum campo ainda estiver faltando, independente do HTML.
    # Gemini acessa a URL nos servidores do Google (AFC), sem depender do nosso IP.
    # -----------------------------------------------------------------------
    needs_gemini = (
        (not marca or marca == "Marca não encontrada") or
        (not modelo or modelo == "Modelo não encontrado")
    )
    if needs_gemini:
        try:
            from app.services.leroy_merlin.scraper.gemini_client import get_gemini_client
            gm = get_gemini_client().extract_brand_and_model_from_url(product_url)
            if (not marca or marca == "Marca não encontrada") and gm.get("marca"):
                marca = gm["marca"]
                logger.info(f"[Gemini] Marca preenchida: {marca}")
            if (not modelo or modelo == "Modelo não encontrado") and gm.get("modelo"):
                modelo = gm["modelo"]
                logger.info(f"[Gemini] Modelo preenchido: {modelo}")
        except Exception as e:
            logger.warning(f"[Gemini fallback marca/modelo] falhou: {e}")

    # -----------------------------------------------------------------------
    # Preço: Sellers API (funciona do Cloud Run); fallback no HTML
    # -----------------------------------------------------------------------
    preco = _fetch_price_from_sellers_api(product_url)
    if not preco and html_available:
        logger.info("sellers API sem resultado — extraindo preço do HTML")
        try:
            preco = extract_price_from_html(response.text)
        except Exception:
            pass

    result = {
        "url":          product_url,
        "titulo":       titulo or "",
        "preco":        preco or "",
        "marca":        marca or "Marca não encontrada",
        "ean":          ean or "EAN não encontrado",
        "modelo":       modelo or "Modelo não encontrado",
        "altura":       dimensoes.get("altura"),
        "largura":      dimensoes.get("largura"),
        "profundidade": dimensoes.get("profundidade"),
        "comprimento":  dimensoes.get("comprimento"),
        "peso":         dimensoes.get("peso"),
        "image_urls":   image_urls,
        "success":      bool(titulo and preco),
    }

    if not result["success"]:
        result["error"] = "Título ou preço não encontrado"

    logger.info(
        f"✅ Extração concluída — Algolia={'sim' if algolia else 'não'} | "
        f"HTML={'sim' if html_available else 'não'} | "
        f"Success={result['success']}"
    )
    return result


def extract_images_1800_batch(product_urls: List[str]) -> List[Dict[str, any]]:
    """
    Extract images from multiple product URLs in batch.

    Args:
        product_urls: List of Leroy Merlin product URLs

    Returns:
        List of dictionaries with URL and extracted images.
    """
    results = []

    for idx, url in enumerate(product_urls, 1):
        logger.info(f"Processing product {idx}/{len(product_urls)}: {url}")
        images = extract_images_1800(url)
        results.append({
            "url": url,
            "images": images,
            "success": len(images) > 0,
            "num_images": len(images)
        })

    return results


# =============================================================================
# LEGACY COMPATIBILITY (for testing)
# =============================================================================

def extrair_imagens_1800(url_produto: str) -> List[str]:
    """
    Legacy function name for backward compatibility.
    Delegates to extract_images_1800.
    """
    return extract_images_1800(url_produto)
