"""
Gemini API client for Sodimac product data extraction.

This module uses Google's Gemini AI to extract product information
by analyzing the product URL directly.
"""
import logging
import json
import google.generativeai as genai
from typing import Dict, List

from app.core.config import settings

logger = logging.getLogger(__name__)


class SodimacGeminiClient:
    """Client for interacting with Google Gemini API for Sodimac products."""

    def __init__(self):
        """Initialize Gemini client with API key from settings."""
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL_TEXT)

    def extract_description_from_url(self, product_url: str, titulo: str) -> str:
        """
        Extract product specifications and generate professional description.

        This function is used in hybrid mode where Python regex extracts title/price/images,
        and Gemini extracts specifications and generates a professional product description.

        Args:
            product_url: URL of the Sodimac product
            titulo: Product title (already extracted by Python regex)

        Returns:
            Professional product description or empty string if extraction fails
        """
        logger.info(f"🤖 Extracting specifications and generating description with Gemini AI")
        logger.info(f"📝 Product: {titulo}")

        prompt = self._build_description_prompt(product_url, titulo)
        response_text = ""

        try:
            response = self.model.generate_content(prompt)

            if not response or not hasattr(response, 'text'):
                logger.error(f"❌ Empty response from Gemini API")
                return ""

            response_text = response.text

            if not response_text or len(response_text.strip()) == 0:
                logger.error(f"❌ Gemini returned empty text")
                return ""

            logger.info(f"✅ Description received from Gemini ({len(response_text)} chars)")

            # Parse JSON response
            clean_json = response_text.replace("```json", "").replace("```", "").strip()

            if not clean_json:
                logger.error(f"❌ Clean JSON is empty after removing markdown")
                return ""

            data = json.loads(clean_json)

            descricao = data.get("descricao", "")

            if not isinstance(descricao, str):
                logger.warning(f"⚠️  Description is not a string, converting...")
                descricao = str(descricao) if descricao else ""

            logger.info(f"✅ Description extracted successfully ({len(descricao)} characters)")
            return descricao.strip()

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing error: {str(e)}")
            logger.error(f"📄 Full response was: {response_text}")
            return ""
        except Exception as e:
            logger.error(f"❌ Error extracting description: {str(e)}", exc_info=True)
            if response_text:
                logger.error(f"📄 Response was: {response_text[:1000]}")
            return ""

    def _build_description_prompt(self, product_url: str, titulo: str) -> str:
        """
        Build the prompt for extracting specifications and generating description.

        Args:
            product_url: URL of the product to analyze
            titulo: Product title

        Returns:
            Formatted prompt string
        """
        return f"""TAREFA: Acesse e analise a página do produto da Sodimac na URL fornecida.

URL DO PRODUTO: {product_url}
TÍTULO DO PRODUTO: {titulo}

PASSO 1: Extraia TODAS as especificações técnicas do produto principal desta URL.

Considere como produto principal apenas aquele cujo:
- título corresponde ao H1 da página
- código/SKU coincide com o código presente na URL
- especificações técnicas estão no bloco de detalhes do produto

Desconsidere totalmente:
- produtos relacionados
- carrosséis
- recomendações
- kits
- variações
- upsell/cross-sell

PASSO 2: Com as especificações em mãos, crie uma descrição profissional seguindo estas regras:

Crie uma descrição de anúncio profissional, bem redigida e completa para o produto: {titulo}.
Use as especificações extraídas como base.

A descrição deve:
- Ser clara, informativa e atrativa, escrita em linguagem natural
- Evitar emojis, HTML, preços, nomes de marcas, aspas e caracteres especiais no início/fim
- Focar em benefícios e diferenciais do produto, com linguagem objetiva
- Começar diretamente com a descrição, sem usar introduções como 'Descrição:' ou similares
- Ter no mínimo 3 parágrafos, abordando características físicas, funcionais e usos recomendados
- Utilizar tom impessoal e profissional, como um texto de vitrine de e-commerce bem elaborado
- Fazer um resumo linha a linha das principais características e especificações do produto
- Sem nenhuma quebra de linha dupla, pode pular linhas, mas sem deixar linhas em branco

FORMATO DE RESPOSTA (JSON - retorne APENAS o JSON, sem texto adicional):
{{
    "descricao": "Texto completo da descrição profissional do produto..."
}}"""


# Singleton instance
_gemini_client = None


def get_gemini_client() -> SodimacGeminiClient:
    """Get or create the Gemini client singleton."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = SodimacGeminiClient()
    return _gemini_client