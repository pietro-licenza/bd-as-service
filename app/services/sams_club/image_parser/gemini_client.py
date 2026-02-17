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
        
        # Configurações de segurança oficiais para evitar bloqueios de logotipos
        self.safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE")
        ]
        
        logger.info(f"🚀 Gemini Client iniciado. Extração: {self.model_extract} | Imagem: {self.model_image}")

    def _resize_image(self, pil_img, max_size=800):
        """Reduz a resolução da imagem para economizar tokens"""
        w, h = pil_img.size
        if max(w, h) > max_size:
            logger.info(f"📏 Redimensionando: {w}x{h} -> {max_size}px")
            pil_img.thumbnail((max_size, max_size), PIL.Image.LANCZOS)
        return pil_img

    def step1_extract_product_data(self, image_paths: List[str], extract_infos: bool = True) -> Dict[str, Any]:
        """Extração de dados com descrição profissional de 3 parágrafos"""
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
                "- AVOID: emojis, HTML, prices, brand names, quotes, and special characters at the start/end.\n"
                "- Focus on benefits and differentials with objective language.\n"
                "- Start directly with the description text (no 'Description:' header).\n"
                "- MINIMUM 3 paragraphs covering: physical characteristics, functional features, and recommended uses.\n"
                "- Use an impersonal and professional 'e-commerce showcase' tone.\n"
                "- Include a line-by-line summary of key technical specifications at the end.\n"
                "- CRITICAL: No double line breaks. Use single line breaks only. No blank lines between paragraphs.\n"
                "- Identify 'foto_ideal_index' as the best front-view photo number (1 to N)."
            )
            
            response = self.client.models.generate_content(
                model=self.model_extract,
                contents=[prompt] + processed_images,
                config=types.GenerateContentConfig(safety_settings=self.safety_settings)
            )

            usage = response.usage_metadata
            try:
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                res_json = json.loads(json_match.group(0)) if json_match else {}
            except Exception:
                res_json = {"raw_output": response.text}

            return {
                "gemini_response": json.dumps(res_json, ensure_ascii=False),
                "infos_extraidas": res_json,
                "usage": {
                    "input": int(usage.prompt_token_count or 0), 
                    "output": int(usage.candidates_token_count or 0)
                }
            }
        except Exception as e:
            logger.error(f"💥 Erro Step 1: {e}")
            return {"error": str(e), "usage": {"input": 0, "output": 0}}

    def step2_generate_background_removed_image(self, image_path: str) -> Dict[str, Any]:
            """Remoção de fundo com orientação vertical e visão frontal obrigatória"""
            from app.cloud import get_storage_client
            logger.info(f"🎨 Step 2: Editando imagem com {self.model_image}")

            storage_client = get_storage_client()
            try:
                with PIL.Image.open(image_path).convert('RGB') as img:
                    img = self._resize_image(img, max_size=1024) 
                    
                    prompt = (
                        "Product background removal. "
                        "Mandatory: Recreate the product in a perfect front view, standing vertically. "
                        "Ensure all text and logos on the front of the packaging are clearly visible and readable. "
                        "Output: Pure white background #FFFFFF. Image data only."
                    )
                    
                    response = self.client.models.generate_content(
                        model=self.model_image,
                        contents=[prompt, img],
                        config=types.GenerateContentConfig(safety_settings=self.safety_settings)
                    )
                    
                    usage = response.usage_metadata
                    u_data = {
                        "input": int(usage.prompt_token_count or 0), 
                        "output": int(usage.candidates_token_count or 0)
                    }

                    if not response.candidates or not response.candidates[0].content.parts:
                        return {"error": "IA bloqueou a geração.", "usage": u_data}

                    image_part = None
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            image_part = part
                            break

                    if not image_part:
                        text_part = response.candidates[0].content.parts[0]
                        if hasattr(text_part, 'text') and text_part.text:
                            return {"error": f"IA recusou: {text_part.text[:20]}", "usage": u_data}
                        raise ValueError("A IA não retornou imagem binária.")

                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                        tmp.write(image_part.inline_data.data)
                        temp_path = tmp.name

                    filename = f"sams_bg_removed_{datetime.now().strftime('%H%M%S')}.png"
                    public_url = storage_client.upload_image(temp_path, filename)
                    
                    # Retornamos o path local para o step 3 poder usar sem baixar de novo
                    return {"public_urls": [public_url], "local_path": temp_path, "usage": u_data}
            except Exception as e:
                logger.error(f"❌ Erro Step 2: {e}")
                return {"error": str(e), "usage": {"input": 0, "output": 0}}

    def step3_generate_contextual_image(self, image_path: str, product_name: str) -> Dict[str, Any]:
        """Gera imagem do produto num ambiente adequado (Ambientada)"""
        from app.cloud import get_storage_client
        logger.info(f"🖼️ Step 3: Gerando ambiente para {product_name}")

        storage_client = get_storage_client()
        try:
            with PIL.Image.open(image_path).convert('RGB') as img:
                img = self._resize_image(img, max_size=1024)
                
                # Prompt Profissional otimizado
                prompt = (
                    f"Professional commercial photography of {product_name}. "
                    "Place the product in its natural, highly realistic usage environment (e.g., modern kitchen for food, elegant office for furniture). "
                    "Ensure realistic cinematic lighting, accurate shadows, and correct scale. "
                    "The product must be the central focus. High-end lifestyle magazine style. "
                    "Output: Image data only."
                )
                
                response = self.client.models.generate_content(
                    model=self.model_image,
                    contents=[prompt, img],
                    config=types.GenerateContentConfig(safety_settings=self.safety_settings)
                )
                
                usage = response.usage_metadata
                u_data = {
                    "input": int(usage.prompt_token_count or 0), 
                    "output": int(usage.candidates_token_count or 0)
                }

                if not response.candidates or not response.candidates[0].content.parts:
                    return {"error": "IA bloqueou a geração ambientada.", "usage": u_data}

                image_part = next((p for p in response.candidates[0].content.parts if hasattr(p, 'inline_data') and p.inline_data), None)

                if not image_part:
                    return {"error": "A IA não retornou imagem para o ambiente.", "usage": u_data}

                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(image_part.inline_data.data)
                    temp_path = tmp.name

                filename = f"sams_contextual_{datetime.now().strftime('%H%M%S')}.png"
                public_url = storage_client.upload_image(temp_path, filename)
                os.remove(temp_path)

                return {"public_urls": [public_url], "usage": u_data}
        except Exception as e:
            logger.error(f"❌ Erro Step 3: {e}")
            return {"error": str(e), "usage": {"input": 0, "output": 0}}

# Funções de ponte fora da classe preservadas
def send_to_gemini(image_paths: List[str], extract_infos: bool = True):
    return GeminiClient().step1_extract_product_data(image_paths, extract_infos)

def generate_product_images_with_gemini(product_image_path: str, **kwargs):
    return GeminiClient().step2_generate_background_removed_image(product_image_path)