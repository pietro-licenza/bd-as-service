"""
Kit Builder Image Generator
Selects best product photos, removes backgrounds, and generates 3 composite kit images.
"""
import os
import logging
import tempfile
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from io import BytesIO

import requests
import PIL.Image
from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

IMAGE_MODEL = "models/gemini-2.5-flash-image"
IMAGE_OUTPUT_TOKENS_EST = 1290  # ~tokens per 1024x1024 output image

SAFETY_SETTINGS = [
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT",        threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH",       threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
]


class KitImageGenerator:

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # ------------------------------------------------------------------ helpers

    def _extract_usage(self, response) -> Dict:
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens     = int(getattr(usage, "prompt_token_count",     0) or 0)
        candidates_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)

        image_output_tokens = 0
        try:
            for attr in ("image_output_token_count", "imageOutputTokenCount",
                         "image_output_tokens", "imageOutputTokens"):
                if hasattr(usage, attr):
                    val = getattr(usage, attr)
                    if val is not None:
                        image_output_tokens = int(val)
                        break
            if image_output_tokens == 0:
                for attr in ("candidates_tokens_details", "candidatesTokensDetails",
                             "candidates_token_details", "candidatesTokenDetails"):
                    if hasattr(usage, attr):
                        for d in (getattr(usage, attr) or []):
                            modality = getattr(d, "modality", None) or getattr(d, "modality_type", None)
                            tc = getattr(d, "token_count", None) or getattr(d, "tokenCount", None)
                            if str(modality).upper() in {"IMAGE", "MODALITY_IMAGE"} and tc is not None:
                                image_output_tokens = int(tc)
                                break
                        if image_output_tokens:
                            break
        except Exception:
            pass

        return {
            "input":               prompt_tokens,
            "output":              candidates_tokens,
            "image_output_tokens": image_output_tokens or IMAGE_OUTPUT_TOKENS_EST,
        }

    def _zero_usage(self) -> Dict:
        return {"input": 0, "output": 0, "image_output_tokens": 0}

    def _resize_image(self, img: PIL.Image.Image, max_size: int = 1024) -> PIL.Image.Image:
        w, h = img.size
        if max(w, h) > max_size:
            img.thumbnail((max_size, max_size), PIL.Image.LANCZOS)
        return img

    def _download_image(self, url: str) -> Optional[PIL.Image.Image]:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            return PIL.Image.open(BytesIO(r.content)).convert("RGB")
        except Exception as e:
            logger.warning(f"⚠️ Falha ao baixar {url[:80]}: {e}")
            return None

    def _has_white_background(self, img: PIL.Image.Image, threshold: int = 240) -> bool:
        """True if all four image corners are near-white."""
        w, h = img.size
        corners = [
            img.getpixel((0, 0)),
            img.getpixel((w - 1, 0)),
            img.getpixel((0, h - 1)),
            img.getpixel((w - 1, h - 1)),
        ]
        return all(all(c >= threshold for c in corner[:3]) for corner in corners)

    def _select_best_photo(self, image_urls: List[str]) -> Optional[PIL.Image.Image]:
        """Download images and prefer the first one with a white background; fallback to first valid."""
        first_valid: Optional[PIL.Image.Image] = None
        for url in image_urls:
            img = self._download_image(url)
            if img is None:
                continue
            if first_valid is None:
                first_valid = img
            if self._has_white_background(img):
                return img
        return first_valid

    def _extract_image_part(self, response):
        """Returns the inline_data image part from a Gemini response, or None."""
        if not response.candidates:
            return None
        parts = response.candidates[0].content.parts or []
        return next((p for p in parts if getattr(p, "inline_data", None)), None)

    # --------------------------------------------------------- step B: bg removal

    def _remove_background(
        self, img: PIL.Image.Image, label: str
    ) -> Tuple[Optional[PIL.Image.Image], Dict]:
        """Calls Gemini to isolate the product on a white background."""
        from app.cloud import get_storage_client
        try:
            img = self._resize_image(img.copy(), 1024)
            response = self.client.models.generate_content(
                model=IMAGE_MODEL,
                contents=[
                    "Product background removal. Isolated product. White background. Front view.",
                    img,
                ],
                config=types.GenerateContentConfig(safety_settings=SAFETY_SETTINGS),
            )
            usage = self._extract_usage(response)
            image_part = self._extract_image_part(response)
            if not image_part:
                logger.warning(f"⚠️ bg_removal ({label}): nenhuma imagem retornada")
                return None, usage

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(image_part.inline_data.data)
                temp_path = tmp.name

            result_img = PIL.Image.open(temp_path).convert("RGB")
            # upload (for cost tracking, not needed in response)
            ts = datetime.now().strftime("%H%M%S%f")
            get_storage_client().upload_image(temp_path, f"kit_bg_removed_{label}_{ts}.png")
            os.remove(temp_path)

            logger.info(f"  ✅ bg_removal ({label}): {result_img.size}")
            return result_img, usage

        except Exception as e:
            logger.error(f"❌ Erro bg_removal ({label}): {e}")
            return None, self._zero_usage()

    # ------------------------------------------------------- step C: composite images

    def _generate_kit_image(
        self,
        product_images: List[PIL.Image.Image],
        prompt: str,
        filename_prefix: str,
    ) -> Tuple[Optional[str], Dict]:
        """Generates one composite image from all product images and uploads to GCS."""
        from app.cloud import get_storage_client
        try:
            resized = [self._resize_image(img.copy(), 1024) for img in product_images]
            response = self.client.models.generate_content(
                model=IMAGE_MODEL,
                contents=[prompt] + resized,
                config=types.GenerateContentConfig(safety_settings=SAFETY_SETTINGS),
            )
            usage = self._extract_usage(response)
            image_part = self._extract_image_part(response)
            if not image_part:
                logger.warning(f"⚠️ {filename_prefix}: nenhuma imagem retornada")
                return None, usage

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(image_part.inline_data.data)
                temp_path = tmp.name

            ts = datetime.now().strftime("%Y%m%d_%H%M%S%f")
            filename = f"{filename_prefix}_{ts}.png"
            public_url = get_storage_client().upload_image(temp_path, filename)
            os.remove(temp_path)

            logger.info(f"  ✅ {filename_prefix}: {public_url[:80]}...")
            return public_url, usage

        except Exception as e:
            logger.error(f"❌ Erro {filename_prefix}: {e}")
            return None, self._zero_usage()

    # ---------------------------------------------------------------- helpers

    def _detect_lifestyle_environment(self, kit_name: str, kit_description: str = "") -> str:
        """
        Detecta o ambiente ideal para a foto lifestyle com base no nome/descrição do kit.
        Retorna uma string em inglês pronta para usar no prompt do Gemini.
        """
        text = (kit_name + " " + kit_description).lower()

        outdoor_keywords = [
            "jardim", "garden", "externo", "área externa", "varanda", "terraço",
            "piscina", "quintal", "deck", "outdoor", "pátio", "sacada",
            "área gourmet", "churrasqueira", "balcony", "porch", "terrace",
        ]
        dining_keywords = [
            "jantar", "dining", "mesa de jantar", "cadeira de jantar",
            "sala de jantar", "cozinha", "kitchen",
        ]
        living_keywords = [
            "sala", "living", "sofá", "sofa", "poltrona", "armchair",
            "sala de estar", "living room",
        ]
        bedroom_keywords = [
            "quarto", "bedroom", "cama", "bed", "colchão", "travesseiro",
            "criado-mudo", "guarda-roupa", "wardrobe",
        ]
        office_keywords = [
            "escritório", "office", "home office", "mesa de escritório",
            "cadeira de escritório", "desk", "cadeira gamer",
        ]
        bathroom_keywords = [
            "banheiro", "bathroom", "toalha", "chuveiro", "banheira",
        ]

        if any(k in text for k in outdoor_keywords):
            return (
                "a beautiful outdoor garden or terrace setting, with green plants, "
                "natural sunlight and a wooden deck or stone patio"
            )
        if any(k in text for k in dining_keywords):
            return (
                "a modern and elegant dining room, with warm lighting and a tasteful table setting"
            )
        if any(k in text for k in living_keywords):
            return (
                "a cozy and modern living room, with soft ambient lighting and stylish decor"
            )
        if any(k in text for k in bedroom_keywords):
            return (
                "a serene and elegant bedroom, with soft natural light and minimalist decor"
            )
        if any(k in text for k in office_keywords):
            return (
                "a clean and productive home office, with soft lighting and modern decor"
            )
        if any(k in text for k in bathroom_keywords):
            return (
                "a modern and elegant bathroom, with soft lighting and clean surfaces"
            )

        # fallback: deixa o Gemini decidir o ambiente mais adequado ao contexto
        return "a realistic and elegant environment according to the product context, with soft natural lighting and tasteful decor"

    # ---------------------------------------------------------------- public API

    def generate_all_kit_images(
        self,
        products_image_urls: List[List[str]],
        kit_name: str,
        kit_description: str = "",
        products_qty_info: List[Dict] = None,
    ) -> Dict:
        """
        Full pipeline:
          A) Select best photo per product (prefer white bg)
          B) Remove background for each product
          C) Generate 3 composite kit images (frontal, angle, lifestyle)

        Returns:
          {
            "generated_urls":        List[str],   # up to 3 public GCS URLs
            "total_input_tokens":    int,
            "total_output_tokens":   int,
            "total_image_tokens":    int,
            "error":                 Optional[str],
          }
        """
        logger.info(f"🖼️ [Kit Image Gen] Kit: '{kit_name}' | {len(products_image_urls)} produtos")

        total_input = total_output = total_image = 0

        # ---- A: select best photo per product ----
        selected: List[PIL.Image.Image] = []
        for i, urls in enumerate(products_image_urls):
            img = self._select_best_photo(urls)
            if img:
                selected.append(img)
                logger.info(f"  ✅ Produto {i+1}: foto selecionada {img.size}")
            else:
                logger.warning(f"  ⚠️ Produto {i+1}: sem imagens válidas")

        if not selected:
            return {
                "generated_urls": [],
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_image_tokens": 0,
                "error": "Nenhuma imagem disponível para gerar o kit.",
            }

        # ---- B: remove backgrounds ----
        cleaned: List[PIL.Image.Image] = []
        for i, img in enumerate(selected):
            result, usage = self._remove_background(img, f"produto_{i+1}")
            total_input  += usage["input"]
            total_output += usage["output"]
            total_image  += usage["image_output_tokens"]
            cleaned.append(result if result is not None else img)

        # ---- C: generate 3 composite images ----
        environment = self._detect_lifestyle_environment(kit_name, kit_description)
        logger.info(f"  🏡 Ambiente lifestyle detectado: {environment}")

        # Regra de quantidade exata por produto
        if products_qty_info:
            qty_lines = ", ".join(
                f"{p['quantidade']}x {p['titulo']}" for p in products_qty_info
            )
            qty_rule = (
                f"The kit contains EXACTLY the following items and quantities: {qty_lines}. "
                "Do NOT add, remove or duplicate any item. Respect these quantities strictly."
            )
        else:
            qty_rule = "Include all kit items exactly as provided, with no additions or omissions."

        assembly_rule = (
            "Assemble all items realistically as they would be used or displayed for sale. "
            "Connected parts must be shown properly assembled (e.g. umbrella inserted in its base, "
            "chairs arranged around the table). No loose or disconnected pieces. "
            + qty_rule
        )

        composite_prompts = [
            (
                "kit_img_frontal",
                (
                    f"Professional e-commerce product photography. "
                    f"Compose all items of the kit '{kit_name}' together in a clean frontal view. "
                    f"White background. All items clearly visible. High resolution. {assembly_rule}"
                ),
            ),
            (
                "kit_img_angle",
                (
                    f"Professional e-commerce product photography. "
                    f"Compose all items of the kit '{kit_name}' together at a 45-degree angle. "
                    f"White background. Elegant composition. High resolution. {assembly_rule}"
                ),
            ),
            (
                "kit_img_lifestyle",
                (
                    f"Professional lifestyle photography. "
                    f"Place all items of the kit '{kit_name}' in {environment}. "
                    f"Depth of field, high resolution. Inspire the customer. {assembly_rule}"
                ),
            ),
        ]

        generated_urls: List[str] = []
        for prefix, prompt in composite_prompts:
            url, usage = self._generate_kit_image(cleaned, prompt, prefix)
            total_input  += usage["input"]
            total_output += usage["output"]
            total_image  += usage["image_output_tokens"]
            if url:
                generated_urls.append(url)

        return {
            "generated_urls":     generated_urls,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_image_tokens": total_image,
            "error": None if generated_urls else "Falha na geração de todas as imagens.",
        }


# ---- singleton ----
_image_generator: Optional[KitImageGenerator] = None


def get_image_generator() -> KitImageGenerator:
    global _image_generator
    if _image_generator is None:
        _image_generator = KitImageGenerator()
    return _image_generator
