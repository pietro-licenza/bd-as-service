"""
Gemini API client for Decathlon product data extraction (SDK 2026).
Versão: Metadados Técnicos + Copywriting Esportivo + Retry Logic + Token Tracking.
"""
import logging
import json
import re
import time
from google import genai
from typing import Dict, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class DecathlonGeminiClient:
    """Client para interação com a API Gemini otimizado para produtos Decathlon."""

    def __init__(self):
        """Initialize Gemini client with SDK 2026 and safety checks."""
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = getattr(settings, "GEMINI_MODEL_TEXT", "gemini-1.5-flash")

    def extract_model_from_url(self, product_url: str) -> Optional[str]:
        """
        Extrai APENAS o nome/código do modelo do produto usando IA.
        Usado como fallback quando regex não encontra o modelo.
        
        Custo estimado: ~$0.000014 por produto (muito barato!).
        
        Args:
            product_url: URL do produto da Decathlon
            
        Returns:
            Nome do modelo ou None se falhar
        """
        logger.info(f"🤖 [Fallback Gemini - Decathlon] Extraindo modelo de: {product_url}")
        prompt = self._build_model_extraction_prompt(product_url)
        
        max_retries = 2
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )
                
                # Extrai apenas o texto limpo
                model = response.text.strip()
                model = model.replace('"', '').replace("'", "").replace('\n', ' ').strip()
                
                if model and len(model) > 0 and model.lower() not in ['null', 'none', 'não encontrado', 'n/a', 'modelo não encontrado']:
                    logger.info(f"✅ Modelo extraído pelo Gemini: {model}")
                    return model
                else:
                    logger.warning("⚠️ Gemini não encontrou o modelo")
                    return None

            except Exception as e:
                if "503" in str(e) or "429" in str(e):
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️ Google ocupado (Tentativa {attempt+1}). Retentando...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                logger.error(f"❌ Falha na extração de modelo: {str(e)}")
                return None
        
        return None

    def extract_description_from_url(self, product_url: str, titulo: str) -> Dict[str, any]:
        """
        Gera descrição profissional para artigos esportivos e captura tokens para custo.
        """
        logger.info(f"🤖 [Decathlon] Gerando copywriting para: {titulo}")
        prompt = self._build_description_prompt(product_url, titulo)

        max_retries = 3
        retry_delay = 2 

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )

                # Captura de Usage Metadata
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
                
                logger.error(f"❌ Erro final na descrição Decathlon: {str(e)}")
                return {"descricao": "", "usage": {"input": 0, "output": 0}}

    # --- Builders de Prompt ---

    def _build_model_extraction_prompt(self, product_url: str) -> str:
        """Constrói o prompt MINIMALISTA para extrair apenas o modelo."""
        return f"""
        URL: {product_url}
        
        TAREFA: Acesse esta URL da Decathlon e identifique APENAS o nome ou código do MODELO do produto esportivo.
        
        REGRAS:
        1. Retorne SOMENTE o nome/código do modelo, nada mais
        2. Não retorne marca, cor, tamanho ou outras características
        3. Se não encontrar o modelo, retorne: "Modelo não encontrado"
        4. Sem JSON, sem formatação, apenas o texto puro
        
        EXEMPLO:
        - Se o produto for "Barraca Arpenaz 4.1", retorne: "Arpenaz 4.1"
        - Se o produto for "Mochila NH Arpenaz 100", retorne: "NH Arpenaz 100"
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

# Singleton instance
_gemini_client = None

def get_gemini_client() -> DecathlonGeminiClient:
    """Garante uma única instância do cliente."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = DecathlonGeminiClient()
    return _gemini_client
