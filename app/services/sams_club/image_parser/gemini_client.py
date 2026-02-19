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
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_extract = "models/gemini-2.5-flash-lite"
        self.model_image = "models/gemini-2.5-flash-image"

        # Configurações de segurança oficiais
        self.safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE")
        ]

        logger.info(f"🚀 Gemini Client iniciado. Extração: {self.model_extract} | Imagem: {self.model_image}")

    # ---------------------------
    # TOKEN TRACKING ROBUSTO
    # ---------------------------
    def _extract_usage(self, response):
        """
        Captura segura dos tokens retornados pela API Gemini.
        Evita problemas quando usage_metadata não é retornado.
        """
        usage = getattr(response, "usage_metadata", None)

        return {
            "input": int(getattr(usage, "prompt_token_count", 0) or 0),
            "output": int(getattr(usage, "candidates_token_count", 0) or 0)
        }

    def _resize_image(self, pil_img, max_size=800):
        """Reduz a resolução da imagem para economizar tokens"""
        w, h = pil_img.size
        if max(w, h) > max_size:
            logger.info(f"📏 Redimensionando: {w}x{h} -> {max_size}px")
            pil_img.thumbnail((max_size, max_size), PIL.Image.LANCZOS)
        return pil_img

    # ---------------------------
    # STEP 1
    # ---------------------------
    def step1_extract_product_data(self, image_paths: List[str], extract_infos: bool = True) -> Dict[str, Any]:
        processed_images = []
        try:
            for p in image_paths:
                if p and os.path.exists(p):
                    img = PIL.Image.open(p).convert('RGB')
                    img = self._resize_image(img)
                    processed_images.append(img)

            if not processed_images:
                return {"error": "Nenhuma imagem válida encontrada."}

            prompt = (
                "Analyze the product photos and return ONLY a JSON with: 'nome', 'preco', 'codigo_barras', 'descricao', 'foto_ideal_index'.\n\n"
                "STRICT RULES FOR THE 'descricao' FIELD:\n"
                "- Create a professional, well-written, and complete advertisement description.\n"
                "- Be clear, informative, and attractive in natural language.\n"
                "- AVOID: emojis, HTML, prices, brand names, quotes, and special characters.\n"
                "- MINIMUM 3 paragraphs.\n"
                "- Identify 'foto_ideal_index'."
            )

            response = self.client.models.generate_content(
                model=self.model_extract,
                contents=[prompt] + processed_images,
                config=types.GenerateContentConfig(safety_settings=self.safety_settings)
            )

            usage_data = self._extract_usage(response)

            try:
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
    # STEP 2
    # ---------------------------
    def step2_generate_background_removed_image(self, image_path: str) -> Dict[str, Any]:
        from app.cloud import get_storage_client
        logger.info(f"🎨 Step 2: Editando imagem com {self.model_image}")

        storage_client = get_storage_client()
        try:
            with PIL.Image.open(image_path).convert('RGB') as img:
                img = self._resize_image(img, max_size=1024)

                prompt = (
                    "Product background removal. "
                    "Front view. White background."
                )

                response = self.client.models.generate_content(
                    model=self.model_image,
                    contents=[prompt, img],
                    config=types.GenerateContentConfig(safety_settings=self.safety_settings)
                )

                usage_data = self._extract_usage(response)

                if not response.candidates or not response.candidates[0].content.parts:
                    return {"error": "IA bloqueou.", "usage": usage_data}

                image_part = next(
                    (p for p in response.candidates[0].content.parts if hasattr(p, 'inline_data') and p.inline_data),
                    None
                )

                if not image_part:
                    return {"error": "Sem imagem.", "usage": usage_data}

                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(image_part.inline_data.data)
                    temp_path = tmp.name

                filename = f"sams_bg_removed_{datetime.now().strftime('%H%M%S')}.png"
                public_url = storage_client.upload_image(temp_path, filename)

                return {"public_urls": [public_url], "local_path": temp_path, "usage": usage_data}

        except Exception as e:
            logger.error(f"❌ Erro Step 2: {e}")
            return {"error": str(e), "usage": {"input": 0, "output": 0}}

    # ---------------------------
    # STEP 3
    # ---------------------------
    def step3_generate_contextual_image(self, image_path: str, product_name: str) -> Dict[str, Any]:
        from app.cloud import get_storage_client
        logger.info(f"🖼️ Step 3: {product_name}")

        storage_client = get_storage_client()
        try:
            with PIL.Image.open(image_path).convert('RGB') as img:
                img = self._resize_image(img, max_size=1024)

                prompt = (
                    f"Professional commercial photography of {product_name}. "
                    "Realistic environment."
                )

                response = self.client.models.generate_content(
                    model=self.model_image,
                    contents=[prompt, img],
                    config=types.GenerateContentConfig(safety_settings=self.safety_settings)
                )

                usage_data = self._extract_usage(response)

                if not response.candidates:
                    return {"error": "Sem retorno.", "usage": usage_data}

                image_part = next(
                    (p for p in response.candidates[0].content.parts if hasattr(p, 'inline_data') and p.inline_data),
                    None
                )

                if not image_part:
                    return {"error": "Sem imagem.", "usage": usage_data}

                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(image_part.inline_data.data)
                    temp_path = tmp.name

                filename = f"sams_contextual_{datetime.now().strftime('%H%M%S')}.png"
                public_url = storage_client.upload_image(temp_path, filename)
                os.remove(temp_path)

                return {"public_urls": [public_url], "usage": usage_data}

        except Exception as e:
            logger.error(f"❌ Erro Step 3: {e}")
            return {"error": str(e), "usage": {"input": 0, "output": 0}}


# ---------------------------
# FUNÇÕES DE PONTE
# ---------------------------
def send_to_gemini(image_paths: List[str], extract_infos: bool = True):
    return GeminiClient().step1_extract_product_data(image_paths, extract_infos)


def generate_product_images_with_gemini(product_image_path: str, **kwargs):
    return GeminiClient().step2_generate_background_removed_image(product_image_path)
