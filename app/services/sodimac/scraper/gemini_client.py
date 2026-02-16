"""
Gemini API client for Sodimac product data extraction (SDK 2026).
Versão Final: Metadados Técnicos + Copywriting + Retry Logic + Token Tracking.
"""
import logging
import json
import re
import time
from google import genai
from typing import Dict, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class SodimacGeminiClient:
    """Client para interação com a API Gemini otimizado para produtos Sodimac."""

    def __init__(self):
        """Initialize Gemini client with SDK 2026 and safety checks."""
        # Novo padrão de inicialização SDK 2026
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        # Prevenção de AttributeError (conforme visto no log da Leroy)
        self.model = getattr(settings, "GEMINI_MODEL_TEXT", "gemini-1.5-flash")

    def extract_product_data_from_url(self, product_url: str) -> Dict[str, any]:
        """
        Extrai metadados técnicos (Título, Preço, Marca, EAN) diretamente via IA.
        Utilizado para garantir que dados difíceis de capturar via Regex sejam obtidos.
        """
        logger.info(f"🤖 [Sodimac] Extraindo dados técnicos da URL: {product_url}")
        prompt = self._build_extraction_prompt(product_url)
        
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )
                
                # Parsing Robusto do JSON
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if not json_match:
                    raise ValueError("JSON técnico não encontrado na resposta")
                
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
                        logger.warning(f"⚠️ Google instável (Tentativa {attempt+1}). Retentando em {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                logger.error(f"❌ Erro na extração técnica Sodimac: {str(e)}")
                return {"success": False, "error": str(e)}

    def extract_description_from_url(self, product_url: str, titulo: str) -> Dict[str, any]:
        """
        Gera descrição profissional com 3 parágrafos e captura tokens para custo.
        """
        logger.info(f"🤖 [Sodimac] Gerando copywriting para: {titulo}")
        prompt = self._build_description_prompt(product_url, titulo)

        max_retries = 3
        retry_delay = 2 

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )

                # Captura de Usage Metadata para o dashboard financeiro
                usage = response.usage_metadata
                u_data = {
                    "input": int(getattr(usage, 'prompt_token_count', 0)),
                    "output": int(getattr(usage, 'candidates_token_count', 0))
                }

                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if not json_match:
                    return {"descricao": "", "usage": u_data}

                data = json.loads(json_match.group(0))
                descricao = data.get("descricao", "").strip()

                return {
                    "descricao": descricao,
                    "usage": u_data
                }

            except Exception as e:
                if "503" in str(e) or "429" in str(e):
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                
                logger.error(f"❌ Erro final na descrição Sodimac: {str(e)}")
                return {"descricao": "", "usage": {"input": 0, "output": 0}}

    def extract_batch_from_urls(self, product_urls: List[str]) -> List[Dict[str, any]]:
        """Processamento sequencial de lote original preservado."""
        results = []
        for idx, url in enumerate(product_urls, 1):
            logger.info(f"📊 Lote Sodimac: {idx}/{len(product_urls)}")
            data = self.extract_product_data_from_url(url)
            data["url_original"] = url
            results.append(data)
        return results

    # --- Builders de Prompt ---

    def _build_extraction_prompt(self, product_url: str) -> str:
        return f"""
        TAREFA: Analise o HTML da Sodimac nesta URL: {product_url}
        Extraia e retorne APENAS um JSON com:
        - titulo
        - preco (valor atual)
        - marca
        - ean (código de barras)
        - especificacoes (lista de strings 'chave: valor')
        
        FORMATO:
        {{
            "titulo": "...",
            "preco": "...",
            "marca": "...",
            "ean": "...",
            "especificacoes": []
        }}
        """

    def _build_description_prompt(self, product_url: str, titulo: str) -> str:
        return f"""
        TAREFA: Copywriter para Sodimac.
        PRODUTO: {titulo}
        URL: {product_url}

        Crie uma descrição profissional com MÍNIMO 3 parágrafos:
        1. Aspectos físicos e design.
        2. Funcionalidades e diferenciais técnicos.
        3. Usos recomendados e benefícios.

        REGRAS: Tom impessoal, sem emojis, sem HTML, sem preços.
        Inclua resumo técnico linha a linha no final do texto.

        FORMATO JSON:
        {{"descricao": "Texto completo aqui..."}}
        """

# Singleton instance
_gemini_client = None

def get_gemini_client() -> SodimacGeminiClient:
    """Garante uma única instância do cliente."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = SodimacGeminiClient()
    return _gemini_client