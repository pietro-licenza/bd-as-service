import os
import json
import logging
import re
import tempfile
from typing import List, Dict, Any
from datetime import datetime
from google import genai
from google.genai import types 
import PIL.Image
from app.core.config import settings

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        """Inicializa o cliente com suporte a rastreamento de tokens e modelos específicos."""
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # Modelos configurados para extração e geração de imagens
        self.model_extract = "models/gemini-2.5-flash-lite"
        self.model_image = "models/gemini-2.5-flash-image"

        # Configurações de segurança para permitir o processamento sem bloqueios indevidos
        self.safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE")
        ]

        logger.info(f"🚀 Gemini Client iniciado. Extração: {self.model_extract} | Imagem: {self.model_image}")

    def _extract_usage(self, response) -> Dict[str, int]:
        """
        Captura segura dos tokens retornados pela API Gemini.
        Essencial para o cálculo de custos no Dashboard.
        """
        usage = getattr(response, "usage_metadata", None)
        return {
            "input": int(getattr(usage, "prompt_token_count", 0) or 0),
            "output": int(getattr(usage, "candidates_token_count", 0) or 0)
        }

    def _resize_image(self, pil_img, max_size=800):
        """Reduz a resolução da imagem para economizar tokens e melhorar a velocidade."""
        w, h = pil_img.size
        if max(w, h) > max_size:
            logger.info(f"📏 Redimensionando imagem: {w}x{h} -> máximo {max_size}px")
            pil_img.thumbnail((max_size, max_size), PIL.Image.LANCZOS)
        return pil_img

    # ---------------------------
    # STEP 1: Extração de Dados e Descrição
    # ---------------------------
    def step1_extract_product_data(self, image_paths: List[str], extract_infos: bool = True) -> Dict[str, Any]:
        """Processa fotos do produto para extrair JSON de informações e gerar descrição."""
        processed_images = []
        try:
            for p in image_paths:
                if p and os.path.exists(p):
                    img = PIL.Image.open(p).convert('RGB')
                    img = self._resize_image(img)
                    processed_images.append(img)

            if not processed_images:
                return {"error": "Nenhuma imagem válida encontrada.", "usage": {"input": 0, "output": 0}}

            # PROMPT AJUSTADO: Instruções claras sobre a indexação da foto ideal
            prompt = (
                "Analyze the product photos and return ONLY a JSON with: 'nome', 'preco', 'codigo_barras', 'descricao', 'foto_ideal_index'.\n\n"
                "RULES FOR 'foto_ideal_index':\n"
                "- Use 1 for the first image, 2 for the second, and so on. Do NOT use 0.\n\n"
                "STRICT RULES FOR THE 'descricao' FIELD:\n"
                "- Create a professional, well-written, and complete advertisement description.\n"
                "- Be clear, informative, and attractive in natural language.\n"
                "- AVOID: emojis, HTML, prices, brand names, quotes, and special characters.\n"
                "- MINIMUM 3 paragraphs."
            )

            response = self.client.models.generate_content(
                model=self.model_extract,
                contents=[prompt] + processed_images,
                config=types.GenerateContentConfig(safety_settings=self.safety_settings)
            )

            usage_data = self._extract_usage(response)

            try:
                # Extração robusta do JSON da resposta de texto
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                res_json = json.loads(json_match.group(0)) if json_match else {}
            except Exception:
                res_json = {"raw_output": response.text}

            return {
                "gemini_response": json.dumps(res_json, ensure_ascii=False),
                "infos_extraidas": res_json,
                "usage": usage_data
            }

        except Exception as e:
            logger.error(f"💥 Erro Step 1: {e}")
            return {"error": str(e), "usage": {"input": 0, "output": 0}}

    # ---------------------------
    # STEP 2: Remoção de Fundo
    # ---------------------------
    def step2_generate_background_removed_image(self, image_path: str) -> Dict[str, Any]:
        """Gera uma imagem do produto com fundo branco puro."""
        from app.cloud import get_storage_client
        logger.info(f"🎨 Step 2: Removendo fundo da imagem com {self.model_image}")

        storage_client = get_storage_client()
        try:
            with PIL.Image.open(image_path).convert('RGB') as img:
                img = self._resize_image(img, max_size=1024)

                prompt = "Product background removal. Front view. White background."

                response = self.client.models.generate_content(
                    model=self.model_image,
                    contents=[prompt, img],
                    config=types.GenerateContentConfig(safety_settings=self.safety_settings)
                )

                usage_data = self._extract_usage(response)

                if not response.candidates or not response.candidates[0].content.parts:
                    return {"error": "IA bloqueou a geração da imagem.", "usage": usage_data}

                image_part = next(
                    (p for p in response.candidates[0].content.parts if hasattr(p, 'inline_data') and p.inline_data),
                    None
                )

                if not image_part:
                    return {"error": "Nenhuma imagem foi retornada na resposta.", "usage": usage_data}

                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(image_part.inline_data.data)
                    temp_path = tmp.name

                filename = f"sams_bg_removed_{datetime.now().strftime('%H%M%S')}.png"
                public_url = storage_client.upload_image(temp_path, filename)

                return {
                    "public_urls": [public_url], 
                    "local_path": temp_path, 
                    "usage": usage_data
                }

        except Exception as e:
            logger.error(f"❌ Erro Step 2: {e}")
            return {"error": str(e), "usage": {"input": 0, "output": 0}}

    # ---------------------------
    # STEP 3: Geração Ambientada
    # ---------------------------
    def step3_generate_contextual_image(self, image_path: str, product_name: str) -> Dict[str, Any]:
        """Gera uma imagem do produto inserido em um ambiente realista e profissional."""
        from app.cloud import get_storage_client
        logger.info(f"🖼️ Step 3: Gerando imagem ambientada para {product_name}")

        storage_client = get_storage_client()
        try:
            with PIL.Image.open(image_path).convert('RGB') as img:
                img = self._resize_image(img, max_size=1024)

                prompt = (
                    f"Professional commercial photography of {product_name}. "
                    "Realistic and elegant environment, soft lighting, depth of field."
                )

                response = self.client.models.generate_content(
                    model=self.model_image,
                    contents=[prompt, img],
                    config=types.GenerateContentConfig(safety_settings=self.safety_settings)
                )

                usage_data = self._extract_usage(response)

                if not response.candidates:
                    return {"error": "IA não retornou candidatos para a imagem.", "usage": usage_data}

                image_part = next(
                    (p for p in response.candidates[0].content.parts if hasattr(p, 'inline_data') and p.inline_data),
                    None
                )

                if not image_part:
                    return {"error": "Não foi possível extrair a imagem ambientada.", "usage": usage_data}

                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(image_part.inline_data.data)
                    temp_path = tmp.name

                filename = f"sams_contextual_{datetime.now().strftime('%H%M%S')}.png"
                public_url = storage_client.upload_image(temp_path, filename)
                os.remove(temp_path)

                return {
                    "public_urls": [public_url], 
                    "usage": usage_data
                }

        except Exception as e:
            logger.error(f"❌ Erro Step 3: {e}")
            return {"error": str(e), "usage": {"input": 0, "output": 0}}

# ---------------------------
# Funções de Ponte (Wrappers)
# ---------------------------
def send_to_gemini(image_paths: List[str], extract_infos: bool = True):
    return GeminiClient().step1_extract_product_data(image_paths, extract_infos)

def generate_product_images_with_gemini(product_image_path: str, **kwargs):
    return GeminiClient().step2_generate_background_removed_image(product_image_path)