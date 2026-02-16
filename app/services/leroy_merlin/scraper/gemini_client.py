"""
Gemini API client for Leroy Merlin product data extraction (SDK 2026).
Versão Final Corrigida: Ajuste de Atributos Settings + Extração de Metadados + Retry.
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
    Gerencia extração de metadados, geração de descrições e controle de custos.
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

    def extract_description_from_url(self, product_url: str, titulo: str) -> Dict[str, any]:
        """
        Gera descrição profissional e captura metadados de tokens para custo.
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
                
                # Captura de tokens para o dashboard financeiro
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
                if "503" in str(e) or "429" in str(e):
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                logger.error(f"❌ Falha na descrição: {str(e)}")
                return {"descricao": "", "usage": {"input": 0, "output": 0}}

    def extract_batch_from_urls(self, product_urls: List[str]) -> List[Dict[str, any]]:
        """Processamento sequencial de URLs para integração com rotas antigas."""
        results = []
        for idx, url in enumerate(product_urls, 1):
            logger.info(f"📑 Processando item {idx} de {len(product_urls)}")
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

    def _build_description_prompt(self, product_url: str, titulo: str) -> str:
        """Constrói o prompt para copywriting profissional."""
        return f"""
        TAREFA: Copywriter de alta conversão.
        PRODUTO: {titulo}
        URL: {product_url}
        
        Crie uma descrição com 3 parágrafos claros:
        - Design e aparência.
        - Benefícios técnicos.
        - Onde e como usar.
        
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