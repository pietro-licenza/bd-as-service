"""
URL and Image Extractor for Sodimac Products

This module extracts product data from Sodimac product pages using JSON-LD structured data.
"""
import requests
import re
import json
import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)


def extract_images(product_url: str) -> List[str]:
    """
    Extract product image URLs from a Sodimac product page.

    Args:
        product_url: URL of the Sodimac product page

    Returns:
        List of image URLs
    """
    logger.info(f"📥 Downloading HTML from: {product_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    try:
        response = requests.get(product_url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text

        logger.info(f"✅ HTML downloaded! Size: {len(html):,} characters")

        candidates: List[str] = []

        # Extract from JSON-LD structured data (keep as fallback)
        try:
            json_ld_pattern = r'<script[^>]*application/ld\+json[^>]*>(.+?)</script>'
            json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)
            for json_block in json_blocks:
                try:
                    data = json.loads(json_block)
                    if isinstance(data, dict) and data.get('@type') == 'product':
                        image = data.get('image')
                        if image:
                            if isinstance(image, str):
                                candidates.append(image)
                            elif isinstance(image, list):
                                candidates.extend(image)
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.debug(f"⚠️  Error parsing JSON block: {e}")
                    continue
        except Exception as e:
            logger.debug(f"⚠️  JSON-LD extraction failed: {e}")

        # Extract from HTML gallery using BeautifulSoup
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Find all <img> tags with src containing 'media.falabella.com/sodimacBR/' and product id
        product_id_match = re.search(r'/product/(\d+)/', product_url)
        product_id = product_id_match.group(1) if product_id_match else None
        gallery_imgs = []
        if product_id:
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and f'sodimacBR/{product_id}' in src:
                    gallery_imgs.append(src)

        # Also check for <img> tags in gallery containers
        for div in soup.find_all('div', class_=re.compile('gallery-container|fotos-en-fila|product-image-holder')):
            for img in div.find_all('img'):
                src = img.get('src')
                if src and src not in gallery_imgs:
                    gallery_imgs.append(src)

        # Merge JSON-LD and gallery images, deduplicate
        all_imgs = candidates + gallery_imgs
        normalized: List[str] = []
        for u in all_imgs:
            if not u:
                continue
            u = u.replace('\/','/')
            u = unquote(u)
            # Try to prioritize high-quality images
            if 'media.falabella.com/sodimacBR/' in u:
                # If w=2348,h=832 is present, keep as is
                if re.search(r'w=2348.*h=832', u):
                    pass
                # If w= and h= present but not high quality, replace
                elif re.search(r'w=\d+', u) and re.search(r'h=\d+', u):
                    u = re.sub(r'w=\d+', 'w=2348', u)
                    u = re.sub(r'h=\d+', 'h=832', u)
                # If only w= present, add h=
                elif re.search(r'w=\d+', u):
                    u = re.sub(r'w=\d+', 'w=2348,h=832', u)
                # If neither, append params
                elif '?' in u:
                    u += ',w=2348,h=832'
                else:
                    u += '?w=2348,h=832'
            if u not in normalized:
                normalized.append(u)

        # Limit results to at most 10 images
        if len(normalized) > 10:
            normalized = normalized[:10]
            logger.info("ℹ️  Limiting image list to 10 items")

        logger.info(f"✅ Found {len(normalized)} candidate images")
        return normalized

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error downloading HTML: {e}")
        return []


def extract_price_from_html(html: str) -> str:
    """
    Extract the HIGHEST product price from Sodimac HTML using JSON-LD data.

    Args:
        html: HTML content of the product page

    Returns:
        Highest price found as string (e.g., "R$ 1.490,00") or None
    """
    all_prices = []

    logger.info("🔍 Extracting prices from Sodimac HTML...")

    # STRATEGY 1: JSON-LD Schema.org (MOST RELIABLE)
    try:
        json_ld_pattern = r'<script[^>]*application/ld\+json[^>]*>(.+?)</script>'
        json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)
        for json_block in json_blocks:
            try:
                data = json.loads(json_block)
                if isinstance(data, dict) and data.get('@type') == 'product':
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        price_raw = offers.get('price')
                        if price_raw:
                            price_float = float(price_raw)
                            price_str = f"R$ {price_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                            all_prices.append(price_str)
                            logger.info(f"✅ Price from JSON-LD: {price_str}")
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.debug(f"⚠️  Error parsing JSON block: {e}")
                continue
    except Exception as e:
        logger.debug(f"⚠️  Strategy 1 (JSON-LD) failed: {e}")

    # STRATEGY 2: Extract price near main product image or title
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    price_candidates = []
    # Try to find price in product-main-img or product-image-holder
    for div in soup.find_all('div', class_=re.compile('product-main-img|product-image-holder|gallery-container')):
        price_texts = re.findall(r'R\$\s*[\d.]+,\d{2}', div.get_text())
        price_candidates.extend(price_texts)
    # Try to find price in title area
    for h1 in soup.find_all('h1'):
        price_texts = re.findall(r'R\$\s*[\d.]+,\d{2}', h1.get_text())
        price_candidates.extend(price_texts)
    # Fallback: Use any R$ pattern if nothing found
    if not all_prices and not price_candidates:
        try:
            fallback_prices = re.findall(r'R\$\s*[\d.]+,\d{2}', html)[:5]
            if fallback_prices:
                price_candidates.extend(fallback_prices)
                logger.warning(f"⚠️  Using fallback prices: {fallback_prices}")
        except Exception as e:
            logger.debug(f"⚠️  Fallback strategy failed: {e}")

    # Filter out installment prices (e.g., 3x R$34,67, parcelado)
    def is_installment_price(price, html):
        idx = html.find(price)
        before = html[max(0, idx-40):idx]
        after = html[idx:idx+40]
        # Exclude if near 'x', 'parcelado', 'sem juros', or 'parcela'
        if re.search(r'(\d+x|parcelado|parcela|sem juros)', before+after, re.IGNORECASE):
            return True
        return False

    # Find all price blocks in HTML (including R$ 104 without cents)
    all_price_texts = re.findall(r'R\$\s*[\d.]+(?:,\d{2})?', html)
    # Also parse from <span class="price-value">R$ 104</span>
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    for span in soup.find_all('span', class_=re.compile('price-value')):
        price_text = span.get_text(strip=True)
        if price_text.startswith('R$') and price_text not in all_price_texts:
            all_price_texts.append(price_text)
    # Remove prices that are part of installment offers
    filtered_prices = [p for p in all_price_texts if not is_installment_price(p, html)]

    # Prefer price found near product title/main block, but only if not installment
    final_price = None
    for price in price_candidates:
        if not is_installment_price(price, html):
            final_price = price
            logger.info(f"✅ Price from HTML context: {final_price}")
            break

    # If not found, fallback to filtered_prices
    if not final_price and filtered_prices:
        final_price = filtered_prices[0]
        logger.info(f"✅ Price from filtered HTML: {final_price}")
    elif not final_price and all_prices:
        final_price = all_prices[0]
        logger.info(f"✅ Price from JSON-LD: {final_price}")
    if not final_price or final_price is None:
        logger.error("❌ No price found in HTML")
        return ""
    return str(final_price)


def extract_brand_from_html(html: str) -> str:
    """
    Extract product brand from Sodimac HTML using JSON-LD data.

    Args:
        html: HTML content of the product page

    Returns:
        Brand name or empty string
    """
    logger.info("🏷️  Extracting brand from HTML...")

    try:
        json_ld_pattern = r'<script[^>]*application/ld\+json[^>]*>(.+?)</script>'
        json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)

        for json_block in json_blocks:
            try:
                data = json.loads(json_block)

                # Check if it's a Product
                if isinstance(data, dict) and data.get('@type') == 'product':
                    brand = data.get('brand', {})
                    if isinstance(brand, dict):
                        brand_name = brand.get('name')
                        if brand_name:
                            logger.info(f"✅ Brand from JSON-LD: {brand_name}")
                            return brand_name
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.debug(f"⚠️  Error parsing JSON block: {e}")
                continue
    except Exception as e:
        logger.debug(f"⚠️  Brand extraction failed: {e}")

    logger.warning("⚠️  No brand found")
    return ""


def extract_ean_from_html(html: str) -> str:
    """
    Extract EAN/UPC code from Sodimac HTML using JSON-LD data.

    Args:
        html: HTML content of the product page

    Returns:
        EAN code or empty string
    """
    logger.info("📦 Extracting EAN from HTML...")

    try:
        json_ld_pattern = r'<script[^>]*application/ld\+json[^>]*>(.+?)</script>'
        json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)

        for json_block in json_blocks:
            try:
                data = json.loads(json_block)

                # Check if it's a Product
                if isinstance(data, dict) and data.get('@type') == 'product':
                    # Try gtin13 first
                    ean = data.get('gtin13')
                    if ean and ean != "null":
                        logger.info(f"✅ EAN from gtin13: {ean}")
                        return ean

                    # Try variants array
                    variants = data.get('variants', [])
                    if isinstance(variants, list) and variants:
                        for variant in variants:
                            if isinstance(variant, dict):
                                upc = variant.get('upc')
                                if upc:
                                    logger.info(f"✅ EAN from variants: {upc}")
                                    return upc
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.debug(f"⚠️  Error parsing JSON block: {e}")
                continue
    except Exception as e:
        logger.debug(f"⚠️  EAN extraction failed: {e}")

    logger.warning("⚠️  No EAN found")
    return ""


def extract_title_from_html(html: str) -> str:
    """
    Extract product title from Sodimac HTML using JSON-LD data.

    Args:
        html: HTML content of the product page

    Returns:
        Product title or empty string
    """
    logger.info("📝 Extracting title from HTML...")

    try:
        json_ld_pattern = r'<script[^>]*application/ld\+json[^>]*>(.+?)</script>'
        json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)

        for json_block in json_blocks:
            try:
                data = json.loads(json_block)

                # Check if it's a Product
                if isinstance(data, dict) and data.get('@type') == 'product':
                    name = data.get('name')
                    if name:
                        logger.info(f"✅ Title from JSON-LD: {name}")
                        return name
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.debug(f"⚠️  Error parsing JSON block: {e}")
                continue
    except Exception as e:
        logger.debug(f"⚠️  Title extraction failed: {e}")

    logger.warning("⚠️  No title found")
    return ""


def extract_product_data(url: str) -> Dict[str, str]:
    """
    Extract all product data from a Sodimac URL.

    Args:
        url: Sodimac product URL

    Returns:
        Dictionary with extracted data
    """
    logger.info(f"🔍 Extracting product data from: {url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text

        data = {
            'titulo': extract_title_from_html(html),
            'preco': extract_price_from_html(html),
            'marca': extract_brand_from_html(html),
            'ean': extract_ean_from_html(html),
            'image_urls': extract_images(url),
            'url_original': url
        }

        logger.info("✅ Product data extraction completed")
        return data

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error downloading HTML: {e}")
        return {
            'titulo': '',
            'preco': None,
            'marca': '',
            'ean': '',
            'image_urls': [],
            'url_original': url,
            'error': str(e)
        }