"""
URL and Image Extractor for Sodimac Products

This module extracts product data from Sodimac product pages using JSON-LD structured data.
"""
import requests
import re
import json
import logging
import time
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_images(product_url: str) -> List[str]:
    """
    Extract product image URLs from a Sodimac product page, filtering out data:image/svg strings.

    Args:
        product_url: URL of the Sodimac product page

    Returns:
        List of valid image URLs (http/https only)
    """
    logger.info(f"📥 Downloading HTML from: {product_url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    html = None
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(product_url, headers=headers, timeout=15)
            response.raise_for_status()
            html = response.text
            logger.info(f"✅ HTML downloaded! Size: {len(html):,} characters")
            break
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error downloading HTML (attempt {attempt}): {e}")
            if attempt < max_attempts:
                time.sleep(2)
            else:
                return []

    if not html:
        return []

    candidates: List[str] = []
    
    # 1. Extração via JSON-LD
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
            except (json.JSONDecodeError, ValueError, KeyError):
                continue
    except Exception as e:
        logger.debug(f"⚠️ JSON-LD extraction failed: {e}")

    # 2. Extração via BeautifulSoup (Galeria)
    try:
        soup = BeautifulSoup(html, 'html.parser')
        product_id_match = re.search(r'/product/(\d+)/', product_url)
        product_id = product_id_match.group(1) if product_id_match else None
        
        if product_id:
            for img in soup.find_all('img'):
                # Verifica src e data-src (comum em lazy loading)
                src = img.get('src') or img.get('data-src')
                if src and f'sodimacBR/{product_id}' in src:
                    candidates.append(src)

        for div in soup.find_all('div', class_=re.compile('gallery-container|fotos-en-fila|product-image-holder')):
            for img in div.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src:
                    candidates.append(src)
    except Exception as e:
        logger.debug(f"⚠️ Gallery extraction failed: {e}")

    # --- Filtro de Validação e Limpeza ---
    final_list: List[str] = []
    # Regex para aceitar apenas o que começa com http ou https
    valid_url_pattern = re.compile(r'^https?://', re.IGNORECASE)

    for u in candidates:
        if not u or not isinstance(u, str):
            continue
        
        # Limpa escapes e decodifica a URL
        u = u.replace('\\/', '/').strip()
        u = unquote(u)

        # VALIDAÇÃO: Só adiciona se for uma URL externa (http/https)
        # Isso remove automaticamente os "data:image/svg+xml..."
        if valid_url_pattern.match(u):
            if u not in final_list:
                final_list.append(u)

    # Limite de 10 imagens
    if len(final_list) > 10:
        final_list = final_list[:10]

    logger.info(f"✅ Found {len(final_list)} valid image URLs")
    return final_list


def extract_price_from_html(html: str) -> str:
    """Extract the HIGHEST product price from Sodimac HTML using JSON-LD data."""
    all_prices = []
    try:
        json_ld_pattern = r'<script[^>]*application/ld\+json[^>]*>(.+?)</script>'
        json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)
        for json_block in json_blocks:
            try:
                data = json.loads(json_block)
                if isinstance(data, dict) and data.get('@type') == 'product':
                    offers = data.get('offers', {})
                    prices = []
                    if isinstance(offers, dict):
                        p = offers.get('price')
                        if p: prices.append(float(p))
                    elif isinstance(offers, list):
                        for o in offers:
                            p = o.get('price') if isinstance(o, dict) else None
                            if p: prices.append(float(p))
                    
                    if prices:
                        price_float = max(prices)
                        all_prices.append(f"R$ {price_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
            except: continue
    except: pass

    if all_prices: return all_prices[0]
    
    fallback = re.findall(r'R\$\s*[\d.]+,\d{2}', html)
    return fallback[0] if fallback else ""


def extract_brand_from_html(html: str) -> str:
    """Extract product brand from Sodimac HTML."""
    try:
        json_ld_pattern = r'<script[^>]*application/ld\+json[^>]*>(.+?)</script>'
        json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)
        for json_block in json_blocks:
            data = json.loads(json_block)
            if isinstance(data, dict) and data.get('@type') == 'product':
                brand = data.get('brand', {})
                name = brand.get('name') if isinstance(brand, dict) else brand
                if name: return name
    except: pass
    return ""


def extract_ean_from_html(html: str) -> str:
    """Extract EAN/UPC code from Sodimac HTML."""
    try:
        json_ld_pattern = r'<script[^>]*application/ld\+json[^>]*>(.+?)</script>'
        json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)
        for json_block in json_blocks:
            data = json.loads(json_block)
            if isinstance(data, dict) and data.get('@type') == 'product':
                ean = data.get('gtin13')
                if ean and ean != "null": return ean
    except: pass
    return ""


def extract_title_from_html(html: str) -> str:
    """Extract product title from Sodimac HTML."""
    try:
        json_ld_pattern = r'<script[^>]*application/ld\+json[^>]*>(.+?)</script>'
        json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)
        for json_block in json_blocks:
            data = json.loads(json_block)
            if isinstance(data, dict) and data.get('@type') == 'product':
                return data.get('name', "")
    except: pass
    return ""


def extract_product_data(url: str) -> Dict[str, str]:
    """Main function to extract all product data."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text
        
        return {
            'titulo': extract_title_from_html(html),
            'preco': extract_price_from_html(html),
            'marca': extract_brand_from_html(html),
            'ean': extract_ean_from_html(html),
            'image_urls': extract_images(url),
            'url_original': url
        }
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {'titulo': '', 'preco': None, 'image_urls': [], 'url_original': url, 'error': str(e)}