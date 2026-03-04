import requests
import re
import json
import logging
from typing import Dict, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def extract_model_from_html(html: str, product_url: str = None) -> str:
    """
    Extrai o modelo do produto do HTML da Decathlon.
    
    Estratégia:
    1. URLs das imagens - packshot-codigo-modelo-XXXXXXX.jpg
    2. Fallback Gemini AI (custo ~$0.000014)
    
    Args:
        html: HTML content of the product page
        product_url: URL do produto (necessária para fallback com Gemini)
        
    Returns:
        Nome do modelo ou "Modelo não encontrado"
    """
    # Estratégia 1: Extração das URLs de imagens - packshot-codigo-modelo-8766093.jpg
    try:
        pattern_image_url = r'packshot-codigo-modelo-(\d+)\.jpg'
        match = re.search(pattern_image_url, html)
        if match:
            model = match.group(1)
            logger.info(f"✅ Modelo encontrado (Regex - packshot): {model}")
            return model
    except Exception as e:
        logger.debug(f"⚠️ Regex packshot failed: {e}")

    # ============================================================================
    # FALLBACK: Usar Gemini AI se não encontrou pelo código do modelo
    # ============================================================================
    logger.warning("⚠️ Código do modelo não encontrado no HTML. Tentando com Gemini AI...")
    
    if product_url:
        try:
            from app.services.decathlon.scraper.gemini_client import get_gemini_client
            
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

def extract_product_data(product_url: str) -> Dict:
    logger.info(f"📥 Acessando a URL: {product_url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        response = requests.get(product_url, headers=headers, timeout=15)
        response.raise_for_status()
        html_content = response.text
        
        # Usamos BeautifulSoup para capturar os scripts de forma robusta (Estratégia decathlon_parser.py)
        soup = BeautifulSoup(html_content, 'html.parser')
        
        title, brand, images, price = "", "", [], 0.0
        
        # 1. Busca em TODOS os scripts JSON-LD para encontrar o tipo 'Product'
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string.strip())
                # Trata caso o JSON seja uma lista de objetos
                items = data if isinstance(data, list) else [data]
                
                for item in items:
                    if item.get('@type') == 'Product':
                        title = item.get('name', '')
                        brand = item.get('brand', {}).get('name', '') if isinstance(item.get('brand'), dict) else item.get('brand', '')
                        
                        raw_images = item.get('image', [])
                        images = (raw_images if isinstance(raw_images, list) else [raw_images])[:10]
                        
                        offers = item.get('offers', {})
                        p_now = float(offers.get('price', 0) or offers.get('lowPrice', 0))
                        p_high = float(offers.get('highPrice', 0))
                        price = max(p_now, p_high)
                        break
                if title: break 
            except: continue

        # 2. CAPTURA DO EAN13 (Lógica Cirúrgica v17)
        # Procuramos o EAN dentro da string escapada (technical-description)
        ean = "Não disponível"
        # Regex aprimorada para lidar com escapes de aspas do VTEX
        ean_match = re.search(r'technical-description\\?\">(\d{13})', html_content)
        if ean_match:
            ean = ean_match.group(1)
        else:
            # Fallback para o rótulo visual
            fb_match = re.search(r'Códigos EAN13 do produto.*?(\d{13})', html_content, re.DOTALL)
            if fb_match: ean = fb_match.group(1)

        # 3. CAPTURA DO MODELO (Regex + Fallback Gemini AI)
        modelo = extract_model_from_html(html_content, product_url)

        success = True if title else False
        return {
            "titulo": title,
            "preco": f"R$ {price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            "marca": brand,
            "ean": ean,
            "modelo": modelo,
            "image_urls": images,
            "success": success,
            "error": None if success else "Dados do produto não encontrados no HTML (JSON-LD ausente)."
        }

    except Exception as e:
        logger.error(f"❌ Erro Crítico Decathlon: {e}")
        return {"success": False, "error": str(e)}