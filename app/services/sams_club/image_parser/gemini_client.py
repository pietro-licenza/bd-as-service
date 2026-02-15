import os
import json
import logging
import re
import tempfile
from typing import List, Dict, Any
from datetime import datetime
import google.generativeai as genai
import PIL.Image
from app.core.config import settings

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self.model_name = getattr(settings, 'GEMINI_MODEL_MULTIMODAL', 'gemini-2.5-flash-image')
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            logger.info(f"🚀 Gemini Client iniciado (Dual-Pass) com: {self.model_name}")


    def step1_extract_product_data(self, image_paths: List[str], extract_infos: bool = True) -> Dict[str, Any]:
        """
        Step 1: Extração de informações do produto (nome, preço, código de barras, descrição, foto ideal).
        Esta função é chamada quando o checkbox 'Extrair informações do produto' está marcado no frontend.
        O prompt é fixo e otimizado para o fluxo de extração de dados do produto.
        """
        pil_images = []
        try:
            for p in image_paths:
                if p and os.path.exists(p):
                    img = PIL.Image.open(p)
                    if img.mode != 'RGB': img = img.convert('RGB')
                    img.load()
                    pil_images.append(img)

            if not pil_images:
                return {"error": "Nenhuma imagem válida encontrada."}

            # Prompt fixo para extração de informações (step 1)
            if extract_infos:
                prompt = (
                    "You will receive 3 to 5 photos of a supermarket product. "
                    "1. Analyze the label photo(s) and extract: product name, brand, price, and barcode."
                    "2. Analyze the specification photo(s) and generate a professional marketplace description."
                    "3. Among all photos, select the 'ideal product photo', meaning the clearest and sharpest front view."
                    "Return a JSON with the fields: 'nome', 'preco', 'codigo_barras', 'descricao', 'foto_ideal_index' (index of the ideal photo, starting at 1)."
                    "If any field is not found, return empty for it."
                )
                model = genai.GenerativeModel(self.model_name)
                logger.info("📡 Step 1: Extraindo informações do produto...")
                res_analysis = model.generate_content([prompt] + pil_images)
                try:
                    json_match = re.search(r'\{.*\}', res_analysis.text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        # Corrige escapes unicode inválidos
                        json_str = re.sub(r'\\(?!["\\/bfnrtu])', r'\\', json_str)
                        res_json = json.loads(json_str)
                    else:
                        res_json = {}
                except Exception:
                    res_json = {"raw_output": res_analysis.text}
                return {
                    "gemini_response": json.dumps(res_json, ensure_ascii=False),
                    "infos_extraidas": res_json,
                    "generated_images_urls": []
                }
            else:
                return {"error": "Extração de informações não solicitada.", "infos_extraidas": {}, "generated_images_urls": []}
        except Exception as e:
            logger.error(f"💥 Erro no GeminiClient: {e}", exc_info=True)
            return {"error": str(e), "infos_extraidas": {}, "generated_images_urls": []}
        finally:
            for img in pil_images:
                try: img.close()
                except: pass

    def step2_generate_background_removed_image(self, image_path: str) -> Dict[str, Any]:
        """
        Step 2: Gera imagem com fundo removido usando a foto ideal.
        """
        from app.cloud import get_storage_client
        import tempfile
        from datetime import datetime

        logger.info(f"🎨 Step 2: Iniciando remoção de fundo para imagem: {image_path}")

        if not image_path or not os.path.exists(image_path):
            logger.error(f"❌ Step 2: Caminho da imagem inválido: {image_path}")
            return {"error": "Caminho da imagem inválido."}

        storage_client = get_storage_client()
        temp_files = []

        try:
            with PIL.Image.open(image_path) as img:
                if img.mode in ('RGBA', 'P'): img = img.convert('RGB')

                # Prompt para remoção de fundo
                prompt = "Isolate the packaged product from this supermarket shelf image. Remove the shelf, background, price tags, and any other elements. Keep only the product package itself, centered on a clean white background. Make sure the product packaging is fully visible and intact."
                logger.info(f"📝 Step 2: Enviando prompt para Gemini: {prompt}")
                
                # Usar o modelo configurado para geração de imagens
                model = genai.GenerativeModel(self.model_name)
                response = model.generate_content([prompt, img])

                if not response.candidates or not response.candidates[0].content.parts:
                    raise ValueError("Nenhuma imagem gerada pela IA.")

                # Extração do binário da imagem gerada
                image_data = response.candidates[0].content.parts[0].inline_data.data
                logger.info(f"📏 Tamanho dos dados da imagem gerada: {len(image_data)} bytes")
                if len(image_data) == 0:
                    raise ValueError("Dados da imagem estão vazios - Gemini não conseguiu gerar a imagem.")
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(image_data)
                    temp_image_path = tmp.name
                    temp_files.append(temp_image_path)

                # Upload para GCS
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"sams_club_bg_removed_{timestamp}.png"
                public_url = storage_client.upload_image(temp_image_path, filename)
                logger.info(f"✅ Step 2: Imagem sem fundo gerada e enviada: {public_url}")

                return {"public_urls": [public_url]}

        except Exception as e:
            logger.error(f"❌ Step 2: Erro na geração de imagem sem fundo: {e}", exc_info=True)
            return {"error": str(e), "public_urls": []}
        finally:
            for tmp in temp_files:
                try: os.unlink(tmp)
                except: pass

# --- FUNÇÕES DE COMPATIBILIDADE PARA O ROUTES.PY ---

def send_to_gemini(image_paths: List[str], extract_infos: bool = True):
    return GeminiClient().step1_extract_product_data(image_paths, extract_infos=extract_infos)

# Placeholder para compatibilidade futura
def generate_product_images_with_gemini(product_image_path: str, extract_infos: bool = False, **kwargs):
    client = GeminiClient()
    result = client.step1_extract_product_data([product_image_path], extract_infos=extract_infos)
    return {"public_urls": result.get("generated_images_urls", [])}