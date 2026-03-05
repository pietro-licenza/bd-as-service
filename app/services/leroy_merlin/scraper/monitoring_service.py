"""
Serviço de Monitoramento - Leroy Merlin
=========================================

Este módulo realiza o monitoramento automático de produtos da Leroy Merlin.

MODOS DE FILTRAGEM:
-------------------
Por padrão, usa modo FLEXÍVEL que aceita todos os produtos Leroy encontrados.
Isso é ideal para buscas por:
  - Códigos específicos (ex: "90560491")
  - Nomes exatos de produtos (ex: "gazebo oxis")
  - Termos amplos (ex: "furadeira")

Para ativar o modo ESTRITO (filtra apenas produtos relacionados ao termo):
  - Edite a linha 44 e mude strict_filter=False para strict_filter=True
  - Útil quando o termo é muito genérico e você quer apenas produtos da categoria

FUNCIONAMENTO:
--------------
1. Busca produtos no Algolia com base nos termos cadastrados
2. Filtra produtos oficiais Leroy (IDs começando com 8 ou 9, até 9 dígitos)
3. Consulta estoque e preço na API V3 da Leroy
4. Salva snapshot no histórico para análise de tendências
"""

import requests
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.models.entities import MonitoringTerm, MonitoredProduct, StockHistory

logger = logging.getLogger(__name__)

# Configurações de conexão estáveis
ALGOLIA_URL = "https://1cf3zt43zu-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(5.10.2)%3B%20Lite%20(5.10.2)%3B%20Browser%3B%20instantsearch.js%20(4.80.0)%3B%20react%20(18.2.0)%3B%20react-instantsearch%20(7.16.3)%3B%20react-instantsearch-core%20(7.16.3)%3B%20JS%20Helper%20(3.26.0)"
ALGOLIA_HEADERS = {
    "x-algolia-application-id": "1CF3ZT43ZU",
    "x-algolia-api-key": "150c68d1c61fc1835826a57a203dab72",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

STOCK_API_URL = "https://www.leroymerlin.com.br/api/v3/products/{}/store-stock"
STOCK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "x-region": "grande_sao_paulo"
}

class LeroyMonitoringService:
    @staticmethod
    def run_sync(db: Session):
        """Executa o monitoramento completo: Algolia -> DB -> Stock API -> History"""
        terms = db.query(MonitoringTerm).filter(
            MonitoringTerm.marketplace == "leroy_merlin",
            MonitoringTerm.is_active == True
        ).all()

        if not terms:
            logger.warning("⚠️ Nenhum termo ativo para monitoramento.")
            return 0

        total_saved = 0

        for term_obj in terms:
            logger.info(f"🚀 [INÍCIO] Termo: '{term_obj.term}'")
            
            # 1. Busca produtos candidatos no Algolia (modo flexível por padrão)
            # Para ativar filtro estrito, use: _fetch_products(term_obj.term, strict_filter=True)
            candidates = LeroyMonitoringService._fetch_products(term_obj.term, strict_filter=False)
            total_candidates = len(candidates)
            logger.info(f"📦 {total_candidates} produtos oficiais identificados.")
            
            for idx, prod_data in enumerate(candidates, 1):
                p_id = prod_data['product_id']
                p_name = prod_data['name']
                
                try:
                    logger.info(f"   ➔ [{idx}/{total_candidates}] Processando ID: {p_id}...")

                    # 2. Upsert do Produto (Garante nome, url e imagem atualizados)
                    product_db = LeroyMonitoringService._get_or_create_product(db, prod_data)
                    
                    # 3. Busca estoque e disponibilidade na API V3
                    stock_info = LeroyMonitoringService._fetch_stock(p_id)
                    
                    if "error" in stock_info:
                        logger.error(f"      ❌ Erro de Estoque no ID {p_id}: {stock_info['error']}")
                        continue
                    
                    # 4. Salva no Histórico (Incluindo o preço capturado no Algolia)
                    new_history = StockHistory(
                        product_internal_id=product_db.id,
                        stock_count=stock_info.get('stock', 0),
                        is_available=stock_info.get('isAvailable', False),
                        price=prod_data.get('price'),  # Preço vem do Algolia
                        recorded_at=datetime.now(timezone.utc)
                    )
                    db.add(new_history)
                    total_saved += 1
                    
                    logger.info(f"      ✅ Sucesso! Estoque: {new_history.stock_count} | Preço: R$ {new_history.price}")

                except Exception as e:
                    logger.error(f"      ❌ Erro Crítico no ID {p_id}: {str(e)}")
                    continue
            
            # Atualiza o timestamp da última execução e commita o termo
            term_obj.last_run = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"🏁 Finalizado termo '{term_obj.term}'.")

        return total_saved

    @staticmethod
    def _fetch_products(term, max_pages=10, strict_filter=False):
        """
        Busca produtos no Algolia com extração de Imagem e Preço.
        
        Args:
            term: Termo de busca
            max_pages: Número máximo de páginas
            strict_filter: Se True, aplica filtro rigoroso de categoria/termo.
                          Se False (padrão), aceita todos produtos Leroy encontrados.
        """
        all_products = []
        filtered_count = {'by_id': 0, 'by_term': 0}

        for page in range(max_pages):
            payload = {
                "requests": [
                    {
                        "indexName": "production_products",
                        "params": f"query={term}&hitsPerPage=40&page={page}"
                    }
                ]
            }
            try:
                response = requests.post(ALGOLIA_URL, headers=ALGOLIA_HEADERS, json=payload, timeout=15)
                hits = response.json()['results'][0].get('hits', [])
                if not hits: break
                
                for hit in hits:
                    p_id = str(hit.get('product_id', ''))
                    p_name = hit.get('name', '')
                    
                    # FILTRO 1: Padrão de ID Leroy 1P (8-9 dígitos, inicia com 8 ou 9)
                    if len(p_id) > 9 or not (p_id.startswith('9') or p_id.startswith('8')):
                        filtered_count['by_id'] += 1
                        continue
                        
                    # FILTRO 2: FLEXÍVEL - Só aplica se strict_filter=True
                    # Verifica se QUALQUER palavra do termo está no nome/categoria
                    if strict_filter:
                        cat = hit.get('CategoryUnique') or ''
                        term_words = term.lower().split()
                        
                        # Verifica se pelo menos UMA palavra do termo aparece
                        found = False
                        for word in term_words:
                            if len(word) > 2:  # Ignora palavras muito curtas
                                if word in cat.lower() or word in p_name.lower():
                                    found = True
                                    break
                        
                        if not found:
                            filtered_count['by_term'] += 1
                            continue
                    
                    # EXTRAÇÃO DE IMAGEM: Constrói a URL do Cloudinary da Leroy
                    image_id = hit.get('image')
                    clean_img_url = None
                    if image_id:
                        clean_img_url = f"https://res.cloudinary.com/lmru-brazil/image/upload/d_v1:static:product:placeholder.png/w_600,h_600,c_pad,b_white,f_auto,q_auto/v1/static/product/{image_id}/"

                    # EXTRAÇÃO DE PREÇO - Tenta vários campos possíveis
                    price = (
                        hit.get('price') or 
                        hit.get('sellingPrice') or 
                        hit.get('final_price') or 
                        hit.get('Price') or 
                        0.0
                    )
                    
                    # Log de debug se preço estiver zerado
                    if price == 0.0:
                        logger.warning(f"      ⚠️  Preço R$ 0.0 para produto {p_id} - {p_name[:50]}")
                    
                    # CORREÇÃO DE URL
                    raw_url = hit.get('url', '')
                    clean_url = raw_url if raw_url.startswith('http') else f"https://www.leroymerlin.com.br{raw_url}"

                    all_products.append({
                        'product_id': p_id,
                        'name': p_name,
                        'url': clean_url,
                        'image_url': clean_img_url,
                        'price': float(price) if price else 0.0
                    })
            except Exception as e:
                logger.error(f"Erro na busca Algolia: {e}")
                break
        
        # Logs de resumo de filtragem
        if filtered_count['by_id'] > 0 or filtered_count['by_term'] > 0:
            logger.info(f"   🗑️  Produtos filtrados: {filtered_count['by_id']} por ID, {filtered_count['by_term']} por termo")
        
        return all_products

    @staticmethod
    def _fetch_stock(product_id):
        """Consulta a API de estoque real da Leroy (V3)"""
        try:
            url = STOCK_API_URL.format(product_id)
            response = requests.get(url, headers=STOCK_HEADERS, timeout=10)
            if response.status_code != 200:
                return {"error": f"HTTP {response.status_code}"}
            
            data = response.json().get('data', {})
            return data.get('ecommerce', {})
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _get_or_create_product(db: Session, prod_data):
        """Upsert para manter os dados do produto atualizados"""
        product = db.query(MonitoredProduct).filter(
            MonitoredProduct.product_id == prod_data['product_id']
        ).first()

        if not product:
            product = MonitoredProduct(
                product_id=prod_data['product_id'],
                marketplace="leroy_merlin",
                name=prod_data['name'],
                url=prod_data['url'],
                image_url=prod_data['image_url']
            )
            db.add(product)
            db.flush() 
        else:
            # Atualiza se algo mudou (preço/imagem/nome)
            product.name = prod_data['name']
            product.url = prod_data['url']
            product.image_url = prod_data['image_url']
            
        return product