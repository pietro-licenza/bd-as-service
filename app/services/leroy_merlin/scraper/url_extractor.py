"""
URL and Image Extractor for Leroy Merlin Products

This module extracts high-resolution product images (1800x1800) from Leroy Merlin product pages.
Uses simple regex patterns for fast and cost-effective extraction without AI.
"""
import requests
import re
import json
import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)


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
        response = requests.get(product_url, headers=headers, timeout=15)
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
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error downloading HTML: {e}")
        return []


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

    # Headers to simulate a browser and avoid blocking
    # IMPORTANT: Do NOT include Accept-Encoding to avoid gzip compression
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    try:
        response = requests.get(product_url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text
        
        logger.info(f"✅ HTML downloaded! Size: {len(html):,} characters")
        
        # Extract all data
        titulo = extract_title_from_html(html)
        preco = extract_price_from_html(html)
        marca = extract_brand_from_html(html)
        ean = extract_ean_from_html(html)
        modelo = extract_model_from_html(html, product_url)
        dimensoes = extract_dimensions_from_html(html)

        # Extract images using the improved extractor (single point of truth)
        logger.info("🔍 Extracting images using improved extractor...")
        image_urls = extract_images_1800(product_url)
        if image_urls:
            logger.info(f"✅ {len(image_urls)} images found")

        result = {
            "url": product_url,
            "titulo": titulo or "",
            "preco": preco or "",
            "marca": marca,
            "ean": ean,
            "modelo": modelo,
            "altura": dimensoes.get("altura"),
            "largura": dimensoes.get("largura"),
            "profundidade": dimensoes.get("profundidade"),
            "comprimento": dimensoes.get("comprimento"),
            "peso": dimensoes.get("peso"),
            "image_urls": image_urls,
            "success": bool(titulo and preco),
        }
        
        if not result["success"]:
            result["error"] = "Failed to extract title or price"
        
        logger.info(f"✅ Extraction complete - Success: {result['success']}")
        return result
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error downloading HTML: {e}")
        return {
            "url": product_url,
            "titulo": "",
            "preco": "",
            "marca": "Marca não encontrada",
            "ean": "EAN não encontrado",
            "modelo": "Modelo não encontrado",
            "image_urls": [],
            "success": False,
            "error": str(e)
        }

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        return {
            "url": product_url,
            "titulo": "",
            "preco": "",
            "marca": "Marca não encontrada",
            "ean": "EAN não encontrado",
            "image_urls": [],
            "success": False,
            "error": str(e)
        }


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
