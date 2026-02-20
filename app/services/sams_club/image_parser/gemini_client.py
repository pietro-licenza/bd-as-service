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
        # Modelos usados
        self.model_text = "models/gemini-2.5-flash-lite"
        self.model_image = "models/gemini-2.5-flash-image"

        # Safety
        self.safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        ]

    def _extract_usage(self, response) -> Dict[str, int]:
        """
        Captura segura dos tokens retornados pela API Gemini.

        Observação importante:
        - A API pode cobrar tokens de modalidades diferentes (texto vs imagem).
        - Para geração de imagem, o Billing do GCP reporta "image output token count".
          Nem sempre esse número aparece diretamente em `usage_metadata`, então aqui
          tentamos extrair quando existir e, caso não exista, os steps de imagem
          vão estimar pelos parâmetros do modelo (ex.: 1290 tokens por imagem 1024x1024).
        """
        usage = getattr(response, "usage_metadata", None)

        prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        candidates_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        total_tokens = int(getattr(usage, "total_token_count", 0) or 0)

        # Tenta extrair campos adicionais que podem existir em versões diferentes do SDK/API.
        image_output_tokens = 0
        try:
            # Alguns SDKs/versões podem expor isso direto.
            for attr in (
                "image_output_token_count",
                "imageOutputTokenCount",
                "image_output_tokens",
                "imageOutputTokens",
            ):
                if hasattr(usage, attr):
                    val = getattr(usage, attr)
                    if val is not None:
                        image_output_tokens = int(val)
                        break

            # Outras versões expõem detalhes por modalidade (lista de objetos).
            if image_output_tokens == 0:
                for attr in (
                    "candidates_tokens_details",
                    "candidatesTokensDetails",
                    "candidates_token_details",
                    "candidatesTokenDetails",
                ):
                    if hasattr(usage, attr):
                        details = getattr(usage, attr) or []
                        for d in details:
                            modality = getattr(d, "modality", None) or getattr(d, "modality_type", None)
                            token_count = getattr(d, "token_count", None) or getattr(d, "tokenCount", None)
                            if str(modality).upper() in {"IMAGE", "MODALITY_IMAGE"} and token_count is not None:
                                image_output_tokens = int(token_count)
                                break
                        if image_output_tokens:
                            break
        except Exception:
            # Se não der pra ler, seguimos com 0 e os steps de imagem podem estimar.
            image_output_tokens = 0

        return {
            # Backward-compatible
            "input": prompt_tokens,
            "output": candidates_tokens,

            # Campos extras para aproximar do Billing do GCP
            "image_output_tokens": image_output_tokens,
            "total_token_count": total_tokens,
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
        except Exception as e:
            return {"error": f"Erro ao abrir imagens: {e}", "usage": {"input": 0, "output": 0}}

        prompt = """
Você é um assistente especialista em produtos do Sam's Club.
A partir das imagens do produto, extraia um JSON com:
- nome
- preco (apenas número se possível)
- codigo_barras (EAN/UPC se visível)
- descricao (curta e objetiva)
- foto_ideal_index (1 a N) apontando a melhor foto frontal do produto

Retorne APENAS um JSON válido (sem markdown).
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_text,
                contents=[prompt] + processed_images,
                config=types.GenerateContentConfig(safety_settings=self.safety_settings)
            )

            usage_data = self._extract_usage(response)

            try:
                # Extração robusta do JSON da resposta de texto
                json_text = response.text or "{}"
                json_text = re.sub(r"^```json|```$", "", json_text.strip(), flags=re.MULTILINE).strip()
                parsed = json.loads(json_text)
            except Exception:
                parsed = {}

            return {
                "infos_extraidas": parsed,
                "gemini_response": json.dumps(parsed, ensure_ascii=False),
                "usage": usage_data
            }

        except Exception as e:
            logger.error(f"❌ Erro Step 1: {e}")
            return {"error": str(e), "usage": {"input": 0, "output": 0}}

    # ---------------------------
    # STEP 2: Remoção de Fundo (via geração)
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

                # Estimativa de tokens de saída de imagem (para casar com Billing do GCP)
                # Gemini 2.5 Flash Image: ~1290 tokens por imagem até 1024x1024.
                if usage_data.get("image_output_tokens", 0) in (0, None):
                    usage_data["image_output_tokens"] = 1290

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

                # Estimativa de tokens de saída de imagem (para casar com Billing do GCP)
                # Gemini 2.5 Flash Image: ~1290 tokens por imagem até 1024x1024.
                if usage_data.get("image_output_tokens", 0) in (0, None):
                    usage_data["image_output_tokens"] = 1290

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