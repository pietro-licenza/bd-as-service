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


def extract_model_from_html(html: str, product_url: str = None) -> str:
    """
    Extrai o modelo do produto do HTML da Sodimac.
    
    Estratégias de regex (baseadas em análise de HTMLs reais):
    1. Ficha técnica HTML - div class="element key">Modelo
    2. JSON embutido - {"name":"Modelo","values":["..."]
    3. Área de exibição - class="product-model">Modelo<!-- --> <!-- -->...
    4. Especificações principais - attribute-text">Modelo : ...
    
    Se nenhuma funcionar, usa Gemini AI como fallback (custo ~$0.000014).
    
    Args:
        html: HTML content of the product page
        product_url: URL do produto (necessária para fallback com Gemini)
        
    Returns:
        Nome do modelo ou "Modelo não encontrado"
    """
    # Estratégia 1: Ficha técnica HTML - <div class="jsx-1675311072 element key">Modelo</div><div class="jsx-1675311072 element value">Look bambú</div>
    try:
        soup = BeautifulSoup(html, 'html.parser')
        modelo_key = soup.find('div', class_=re.compile('element key'), text=re.compile(r'^Modelo$', re.IGNORECASE))
        if modelo_key:
            # Busca o próximo div com a classe "element value"
            modelo_value = modelo_key.find_next_sibling('div', class_=re.compile('element value'))
            if modelo_value:
                model = modelo_value.get_text(strip=True)
                if model:
                    logger.info(f"✅ Modelo found (Strategy 1 - Ficha Técnica HTML): {model}")
                    return model
    except Exception as e:
        logger.debug(f"⚠️ Strategy 1 failed: {e}")

    # Estratégia 2: JSON embutido - {"name":"Modelo","values":["Look bambú"],...}
    try:
        pattern_json = r'\{"name"\s*:\s*"Modelo"\s*,\s*"values"\s*:\s*\["([^"]+)"\]'
        match = re.search(pattern_json, html)
        if match:
            model = match.group(1).strip()
            logger.info(f"✅ Modelo found (Strategy 2 - JSON embutido): {model}")
            return model
    except Exception as e:
        logger.debug(f"⚠️ Strategy 2 failed: {e}")

    # Estratégia 3: Área de exibição do modelo - <div class="jsx-283748275 product-model">Modelo<!-- --> <!-- -->Look bambú</div>
    try:
        pattern_display = r'class="[^"]*product-model[^"]*">Modelo(?:<!--[^>]*-->|\s)*([^<]+)'
        match = re.search(pattern_display, html)
        if match:
            model = match.group(1).strip()
            logger.info(f"✅ Modelo found (Strategy 3 - Área de exibição): {model}")
            return model
    except Exception as e:
        logger.debug(f"⚠️ Strategy 3 failed: {e}")

    # Estratégia 4: Especificações principais - <span class="jsx-1415091980 attribute-text">Modelo : Look bambú</span>
    try:
        pattern_specs = r'class="[^"]*attribute-text[^"]*">Modelo\s*:\s*([^<]+)'
        match = re.search(pattern_specs, html)
        if match:
            model = match.group(1).strip()
            logger.info(f"✅ Modelo found (Strategy 4 - Especificações principais): {model}")
            return model
    except Exception as e:
        logger.debug(f"⚠️ Strategy 4 failed: {e}")

    # ============================================================================
    # FALLBACK: Usar Gemini AI se não encontrou pelas estratégias de regex
    # ============================================================================
    logger.warning("⚠️ Campo 'Modelo' não encontrado por regex. Tentando com Gemini AI...")
    
    if product_url:
        try:
            from app.services.sodimac.scraper.gemini_client import get_gemini_client
            
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
            'modelo': extract_model_from_html(html, url),
            'image_urls': extract_images(url),
            'url_original': url
        }
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {'titulo': '', 'preco': None, 'modelo': 'Modelo não encontrado', 'image_urls': [], 'url_original': url, 'error': str(e)}