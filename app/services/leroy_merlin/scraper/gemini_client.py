"""
Gemini API client for Leroy Merlin product data extraction (SDK 2026).
Versão: Dual Prompting - Chamadas separadas para Descrição e Dimensões Técnicas (com Specs).
"""
import logging
import json
import re
import time
from google import genai
from typing import Dict, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class LeroyMerlinGeminiClient:
    """
    Client robusto para interação com a API Gemini para Leroy Merlin.
    Gerencia extração de metadados, geração de descrições, dimensões e controle de custos.
    """
    
    def __init__(self):
        """Inicializa o cliente com o novo SDK 2026."""
        # Novo padrão SDK 2026
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Correção do AttributeError: Usa o que existe no seu Settings
        self.model_text = getattr(settings, "GEMINI_MODEL_TEXT", "gemini-1.5-flash")
        self.model_vision = "gemini-1.5-flash" # Fallback direto para evitar quebra no Pydantic

    def extract_product_data_from_url(self, product_url: str) -> Dict[str, any]:
        """
        Extrai metadados técnicos (EAN, Marca, Specs) da URL.
        Implementa lógica de Retry para suportar instabilidades do Google (Erro 503).
        """
        logger.info(f"🤖 [Metadados] Analisando: {product_url}")
        prompt = self._build_extraction_prompt(product_url)
        
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_text,
                    contents=prompt
                )
                
                # Parsing Robusto do JSON
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if not json_match:
                    raise ValueError("JSON não encontrado na resposta da extração")
                
                data = json.loads(json_match.group(0))
                
                return {
                    "titulo": data.get("titulo", ""),
                    "preco": data.get("preco", ""),
                    "marca": data.get("marca", ""),
                    "ean": data.get("ean", ""),
                    "especificacoes": data.get("especificacoes", []),
                    "success": True
                }

            except Exception as e:
                if "503" in str(e) or "429" in str(e):
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️ Google ocupado (Tentativa {attempt+1}). Retentando...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                logger.error(f"❌ Falha na extração técnica: {str(e)}")
                return {"success": False, "error": str(e)}

    def extract_model_from_url(self, product_url: str) -> Optional[str]:
        """
        Extrai APENAS o nome/código do modelo do produto usando IA.
        """
        logger.info(f"🤖 [Fallback Gemini] Extraindo modelo de: {product_url}")
        prompt = self._build_model_extraction_prompt(product_url)
        
        max_retries = 2
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_text,
                    contents=prompt
                )
                
                model = response.text.strip()
                model = model.replace('"', '').replace("'", "").replace('\n', ' ').strip()

                # Rejeita resultados inválidos: vazio, palavras reservadas ou puramente numérico
                invalid = ['null', 'none', 'não encontrado', 'n/a', 'modelo não encontrado']
                if (model and len(model) > 0
                        and model.lower() not in invalid
                        and not model.replace(' ', '').isdigit()):
                    logger.info(f"✅ Modelo extraído pelo Gemini: {model}")
                    return model
                else:
                    logger.warning(f"⚠️ Gemini retornou modelo inválido: '{model}'")
                    return None

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return None
        
        return None

    def extract_description_from_url(self, product_url: str, titulo: str) -> Dict[str, any]:
        """
        Gera APENAS a descrição profissional (Copywriting).
        """
        logger.info(f"🤖 [IA Copywriter] Gerando texto para: {titulo}")
        prompt = self._build_description_prompt(product_url, titulo)
        
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_text,
                    contents=prompt
                )
                
                usage = response.usage_metadata
                u_data = {
                    "input": int(usage.prompt_token_count or 0),
                    "output": int(usage.candidates_token_count or 0)
                }
                
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                data = json.loads(json_match.group(0)) if json_match else {}
                
                return {
                    "descricao": data.get("descricao", "").strip(),
                    "usage": u_data
                }

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logger.error(f"❌ Falha na descrição: {str(e)}")
                return {"descricao": "", "usage": {"input": 0, "output": 0}}

    def extract_brand_and_model_from_url(self, product_url: str) -> Dict[str, str]:
        """
        Pede ao Gemini para acessar a URL e extrair APENAS marca e modelo.
        Usado como fallback quando HTML está bloqueado (Cloud Run / Cloudflare).
        Retorna {"marca": "...", "modelo": "..."} ou campos vazios se falhar.
        """
        logger.info(f"🤖 [Gemini marca/modelo] Extraindo de: {product_url}")
        prompt = f"""
URL: {product_url}

Acesse esta URL de produto e extraia APENAS dois campos:
1. "marca": a marca/fabricante do produto (ex: "Naterial", "Tramontina", "Vonder").
2. "modelo": o nome ou código do modelo do produto (ex: "SOLARIUM", "Ref. 12345").

RESPONDA APENAS EM JSON, sem explicações:
{{"marca": "...", "modelo": "..."}}

Se não encontrar um campo, coloque string vazia "".
"""
        for attempt in range(2):
            try:
                response = self.client.models.generate_content(
                    model=self.model_text,
                    contents=prompt
                )
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if not json_match:
                    raise ValueError("JSON não encontrado na resposta")
                data = json.loads(json_match.group(0))
                marca  = str(data.get("marca",  "") or "").strip()
                modelo = str(data.get("modelo", "") or "").strip()
                logger.info(f"✅ [Gemini marca/modelo] marca={marca} | modelo={modelo}")
                return {"marca": marca, "modelo": modelo}
            except Exception as e:
                if attempt == 0:
                    import time; time.sleep(1)
                    continue
                logger.error(f"❌ [Gemini marca/modelo] falhou: {e}")
        return {"marca": "", "modelo": ""}

    def extract_batch_from_urls(self, product_urls: List[str]) -> List[Dict[str, any]]:
        """Processamento sequencial de URLs para integração com rotas antigas."""
        results = []
        for idx, url in enumerate(product_urls, 1):
            data = self.extract_product_data_from_url(url)
            data["url_original"] = url
            results.append(data)
        return results

    # --- Métodos de Construção de Prompt ---

    def _build_extraction_prompt(self, product_url: str) -> str:
        """Constrói o prompt focado em extração de dados brutos."""
        return f"""
        TAREFA: Extração técnica de e-commerce.
        URL: {product_url}
        
        Extraia do HTML da página:
        1. Título completo.
        2. Preço de venda atual.
        3. Marca do fabricante.
        4. Código EAN/GTIN.
        5. Lista de especificações técnicas (ex: Cor: Branco, Material: Aço).
        
        RESPONDA APENAS EM JSON:
        {{
            "titulo": "...",
            "preco": "...",
            "marca": "...",
            "ean": "...",
            "especificacoes": ["chave: valor"]
        }}
        """

    def _build_model_extraction_prompt(self, product_url: str) -> str:
        """Constrói o prompt MINIMALISTA para extrair apenas o modelo."""
        return f"""
        URL: {product_url}
        TAREFA: Acesse esta URL e identifique APENAS o nome ou código do MODELO do produto.
        """

    def _build_description_prompt(self, product_url: str, titulo: str) -> str:
        """Constrói o prompt focado exclusivamente em copywriting profissional."""
        return f"""
        TAREFA: Especialista em Copywriting de E-commerce.
        PRODUTO: {titulo}
        URL: {product_url}
        
        Crie uma descrição profissional de 3 a 5parágrafos claros:
        - Design e estética.
        - Diferenciais técnicos e qualidade.
        - Sugestões de uso e benefícios reais.
	    - Ao final da descrição, insira um resumo linha-a-linha com as principais características do produto (dimensoes, peso, potencia, utilidades, etc., conforme aplicável).
	    - Caso seja um kit ou conjunto, acrescente um parágrafo para indicar o que está incluso no kit (bem como dimensões de cada um dos produtos que compõe o kit, conforme aplicável).

        REGRAS: Sem emojis, sem HTML, sem preços, sem citar a loja Leroy Merlin.
        RETORNE JSON:
        {{ "descricao": "..." }}
        """

# Singleton
_gemini_client = None

def get_gemini_client() -> LeroyMerlinGeminiClient:
    """Garante instância única do cliente para economia de memória."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = LeroyMerlinGeminiClient()
    return _gemini_client