"""
Shared Gemini API client for product data extraction.

This module provides a centralized Gemini client used by all services
(validation flow, Sam's Club, Leroy Merlin, etc.)
"""
import os
import json
import logging
import tempfile
import imghdr
from typing import List, Tuple
from pathlib import Path
import google.generativeai as genai
import PIL.Image

logger = logging.getLogger(__name__)


def convert_mpo_to_jpeg(image_path: str) -> Tuple[str, bool]:
    """
    Convert MPO (Multi-Picture Object) images to JPEG.
    MPO format is not supported by Gemini API.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Tuple of (converted_path, was_converted)
        - If conversion needed: returns new temp file path and True
        - If no conversion needed: returns original path and False
    """
    try:
        # Check if file is MPO by trying to detect format
        file_ext = Path(image_path).suffix.lower()
        
        # Try to open and check format
        with PIL.Image.open(image_path) as img:
            img_format = img.format
            
            # Check if it's MPO or unsupported format
            if img_format == 'MPO' or file_ext == '.mpo':
                logger.info(f"🔄 Convertendo MPO para JPEG: {Path(image_path).name}")
                
                # Create temporary JPEG file
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False, 
                    suffix='.jpg',
                    prefix='converted_'
                )
                temp_path = temp_file.name
                temp_file.close()
                
                # Convert to RGB (MPO might be in different color mode)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Save as JPEG
                img.save(temp_path, 'JPEG', quality=95)
                logger.info(f"✅ Conversão concluída: {Path(temp_path).name}")
                
                return temp_path, True
            else:
                # No conversion needed
                return image_path, False
                
    except Exception as e:
        logger.warning(f"⚠️  Erro ao verificar/converter imagem {image_path}: {str(e)}")
        # Return original path if conversion fails
        return image_path, False


class GeminiClient:
    """Client for interacting with Google Gemini API."""
    
    def __init__(self):
        """Initialize Gemini client with API key from settings."""
        from app.core.config import settings
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_text = 'gemini-2.5-flash-lite'  # For text extraction
        self.model_multimodal = 'gemini-2.5-flash-image'  # For image generation
        self.model_validation = 'gemini-2.5-flash-lite'  # For validation (cheaper)
    
    def extract_product_data(
        self, 
        image_paths: List[str]
    ) -> dict:
        """
        Extract product data from multiple images using Gemini API.
        
        Expected 3 images:
        1. Price tag/label (name, price, EAN)
        2. Product box/packaging (specifications)
        3. Product itself (for image generation)
        
        Args:
            image_paths: List of paths to product images (3 expected)
            
        Returns:
            Dictionary with extracted data and product image path
        """
        # Convert MPO images to JPEG if needed
        converted_paths = []
        temp_files_to_cleanup = []
        
        for path in image_paths:
            converted_path, was_converted = convert_mpo_to_jpeg(path)
            converted_paths.append(converted_path)
            if was_converted:
                temp_files_to_cleanup.append(converted_path)
        
        try:
            # Load all images (now guaranteed to be compatible formats)
            images = [PIL.Image.open(path) for path in converted_paths]
        
            # Build prompt
            prompt = self._build_extraction_prompt()
            
            # Prepare content (prompt + all images)
            contents = [prompt] + images
            
            # Send to Gemini API
            model = genai.GenerativeModel(self.model_text)
            response = model.generate_content(contents)
            
            # Close images to release file handles
            for img in images:
                img.close()
            
            # Parse response to find which image is the product
            try:
                response_json = json.loads(response.text.replace("```json", "").replace("```", "").strip())
                product_index = response_json.get("product_image_index", 2) - 1  # Convert to 0-based index
                # Use original path, not converted path
                product_image_path = image_paths[product_index] if 0 <= product_index < len(image_paths) else image_paths[-1]
            except:
                # Fallback: use last image (original path)
                product_image_path = image_paths[-1] if len(image_paths) >= 3 else image_paths[0]
            
            return {
                "gemini_response": response.text,
                "product_image_path": product_image_path
            }
        
        finally:
            # Cleanup temporary converted files
            for temp_file in temp_files_to_cleanup:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"🧹 Arquivo temporário removido: {temp_file}")
                except Exception as e:
                    logger.warning(f"⚠️  Erro ao remover arquivo temporário {temp_file}: {str(e)}")
    
    def _build_extraction_prompt(self) -> str:
        """
        Build the extraction prompt for Gemini.
        
        Returns:
            Formatted prompt string
        """
        return (
            f"TAREFA: Analise as imagens fornecidas do MESMO PRODUTO (podem ser 2,3, 4 a 5 imagens em ORDEM ALEATÓRIA).\n\n"
            
            "PASSO 1 - IDENTIFICAÇÃO AUTOMÁTICA:\n"
            "Identifique automaticamente QUANTAS e QUAIS TIPOS de imagens foram enviadas:\n"
            "- ETIQUETA/PREÇO: Foto com etiqueta de preço, código de barras, nome do produto (OBRIGATÓRIA)\n"
            "- EMBALAGEM/CAIXA: Foto da caixa/embalagem com especificações técnicas (OPCIONAL)\n"
            "- PRODUTO LIMPO: Foto do produto físico (pode ter papéis/etiquetas sobre ele), ele tambem pode estar em sua caixa, ou embalagem (OBRIGATÓRIA)\n\n"
            "- CONSIDERE DE TODAS FOTOS ENVIADAS, APENAS AS 3 MAIS CONDIZENTES COM OS TIPOS ACIMA\n\n"

            "PASSO 2 - EXTRAÇÃO DE DADOS:\n\n"
            "DA FOTO COM ETIQUETA/PREÇO (SEMPRE PRESENTE), extraia:\n"
            "- nome_produto: Nome COMPLETO do produto (marca + tipo + volume/tamanho)\n"
            "- preco: Preço no formato 'XX,XX' ou 'X.XXX,XX' (COM R$ se visível)\n"
            "- ean: Código de barras EAN-13 (13 dígitos numéricos)\n\n"
            
            "DA FOTO DA EMBALAGEM/CAIXA (SE PRESENTE), extraia:\n"
            "- especificacoes: Lista com TODAS as especificações técnicas encontradas\n\n"
            
            "SE NÃO HOUVER FOTO DA EMBALAGEM:\n"
            "- especificacoes: Liste informações básicas visíveis (tamanho, marca, tipo)\n\n"
            
            "DA FOTO DO PRODUTO LIMPO, OU FOTO DO PRODUTO NA CAIXA OU EMBALAGEM (SEMPRE PRESENTE):\n"
            "- Identifique qual é a imagem (número) para retornar no campo 'product_image_index'\n\n"
            "- Mantenha a foto original, desde a embalagem até as cores'\n\n"
            
            "REGRAS IMPORTANTES:\n"
            "- As fotos PODEM estar em QUALQUER ORDEM\n"
            "- PODEM ser 2, 3, 4 a 5 fotos (mínimo 2: etiqueta + produto)\n"
            "- Identifique automaticamente qual foto é qual tipo\n"
            "- SEMPRE preencha todos os campos, mesmo com dados mínimos\n"
            "- Seja EXTREMAMENTE PRECISO com números (preço, EAN)\n\n"
            
            "FORMATO DE RESPOSTA (retorne APENAS este JSON):\n"
            "{\n"
            '  "nome_produto": "NOME COMPLETO",\n'
            '  "preco": "R$ XX,XX",\n'
            '  "ean": "1234567890123",\n'
            '  "especificacoes": ["Spec 1", "Spec 2"],\n'
            '  "descricao": "Descrição completa e profissional...",\n'
            '  "product_image_index": 2,\n'
            '  "num_images_received": 3,\n'
            '  "identificacao": {\n'
            '    "imagem_1": "etiqueta|embalagem|produto",\n'
            '    "imagem_2": "etiqueta|embalagem|produto",\n'
            '    "imagem_3": "etiqueta|embalagem|produto"\n'
            "  }\n"
            "}\n"
        )

    def generate_description(self, titulo: str, especificacoes: list) -> str:
        """
        Generate a professional product description using provided title and specifications.

        Returns a cleaned string with no surrounding markdown/code fences and
        with consecutive blank lines collapsed to a single newline.
        """
        try:
            specs_text = json.dumps(especificacoes, ensure_ascii=False) if isinstance(especificacoes, (list, dict)) else str(especificacoes)

            prompt = (
                f"Crie uma descrição de anúncio profissional, bem redigida e completa para o seguinte produto: {titulo}. "
                f"Use as seguintes especificações como base: {specs_text}. "
                "A descrição deve:\n"
                "- Ser clara, informativa e atrativa, escrita em linguagem natural;\n"
                "- Evitar emojis, HTML, preços, nomes de marcas, aspas e caracteres especiais no início/fim;\n"
                "- Focar em benefícios e diferenciais do produto, com linguagem objetiva;\n"
                "- Começar diretamente com a descrição, sem usar introduções como 'Descrição:' ou similares;\n"
                "- Ter no mínimo 3 parágrafos, abordando características físicas, funcionais e usos recomendados;\n"
                "- Utilizar tom impessoal e profissional, como um texto de vitrine de e-commerce bem elaborado.\n"
                "- Faça um resumo linha a linha das principais características e especificações do produto.\n"
                "- Sem nenhuma quebra de linha em branco entre parágrafos (pule linhas apenas com uma única quebra de linha)."
            )

            model = genai.GenerativeModel(self.model_text)
            response = model.generate_content([prompt])
            text = response.text if hasattr(response, 'text') else str(response)

            # Remove markdown code fences and trim
            cleaned = text.replace("```", "").replace("```json", "").strip()
            # Collapse multiple blank lines into single newline (no empty lines)
            import re
            cleaned = re.sub(r"\n{2,}", "\n", cleaned)
            return cleaned

        except Exception as e:
            logger.error(f"❌ Erro ao gerar descrição: {str(e)}")
            return ""
    
    def validate_generated_image(
        self,
        original_image: PIL.Image.Image,
        generated_image_path: str,
        angle_description: str
    ) -> dict:
        """
        Validate if generated image maintains product fidelity and has good angle.
        
        Args:
            original_image: Original product image (PIL Image)
            generated_image_path: Path to generated image file
            angle_description: Description of what angle should be (e.g., "45-degree side view")
            
        Returns:
            Dictionary with 'approved', 'confidence', and 'issues' keys
        """
        try:
            generated_image = PIL.Image.open(generated_image_path)
            
            prompt = (
                f"Compare these two images of the SAME product:\n\n"
                f"Image 1: Original product/packaging\n"
                f"Image 2: Generated variation (should be {angle_description})\n\n"
                
                "VALIDATION CRITERIA:\n"
                "✅ APPROVE if:\n"
                "- Same brand/logo visible and readable\n"
                "- Same packaging colors (small variations OK)\n"
                "- Same product type\n"
                "- Product in COMMERCIAL position (upright, presentable, not sideways/tilted)\n"
                "- Professional e-commerce quality\n\n"
                
                "❌ REJECT if:\n"
                "- Different brand or logo missing/changed\n"
                "- Completely different colors\n"
                "- Product sideways, upside down, or tilted awkwardly\n"
                "- Product cut off or poorly framed\n"
                "- Different product type\n"
                "- Unprofessional angle for e-commerce\n\n"
                
                "BE STRICT about product position - reject if sideways or bad angle.\n"
                "Small color variations are OK, but major changes = reject.\n\n"
                
                "Respond ONLY with JSON:\n"
                "{\n"
                '  "approved": true/false,\n'
                '  "confidence": 0-100,\n'
                '  "issues": ["list", "of", "problems", "if", "any"]\n'
                "}"
            )
            
            model = genai.GenerativeModel(self.model_validation)
            response = model.generate_content([prompt, original_image, generated_image])
            
            generated_image.close()
            
            # Parse validation response
            try:
                result = json.loads(response.text.replace("```json", "").replace("```", "").strip())
                return result
            except:
                # If can't parse, return uncertain result
                logger.warning(f"⚠️  Não foi possível parsear resposta de validação")
                return {
                    "approved": True,  # Default to approved if validation fails
                    "confidence": 50,
                    "issues": ["Validation response parsing failed"]
                }
                
        except Exception as e:
            logger.error(f"❌ Erro na validação: {str(e)}")
            return {
                "approved": True,  # Default to approved on error
                "confidence": 50,
                "issues": [f"Validation error: {str(e)}"]
            }
    
    def detect_product_bboxes(self, image: PIL.Image.Image) -> list:
        """
        Ask Gemini to detect product bounding boxes in the provided image.

        Returns a list of boxes in pixel coordinates:
        [{"label": "product", "bbox": [ymin, xmin, ymax, xmax]}, ...]
        If none found, returns an empty list.
        """
        # NOTE (crop): This detection is used downstream to decide whether to
        # perform a crop of the original image before sending it to the
        # generative model. The detector is asked to return ONE large box
        # that encompasses the product illustration on packaging artwork.
        # Caveats:
        # - The detector can return boxes that correspond to texture or
        #   decorative artwork rather than the physical product; such
        #   boxes can confuse the generator if used to crop the input.
        # - We therefore keep detection separated from the cropping
        #   decision (crop thresholds are applied later) and log the
        #   returned boxes for debugging.
        try:
            prompt = (
                "IMAGE ANALYSIS: This is a photo of product packaging.\n"
                "TASK: Detect the bounding box of the MAIN PHYSICAL PRODUCT as it appears in the artwork.\n"
                "1. FOCUS: Only on the product illustration (e.g., the pots and pans themselves).\n"
                "2. IGNORE: Box corners, barcodes, nutritional tables, '4 pieces' badges, and store background.\n"
                "3. Return a JSON: {\"boxes\": [{\"label\": \"product_illustration\", \"bbox\": [ymin, xmin, ymax, xmax]}]}.\n"
                "Use PIXEL coordinates."
            )

            model = genai.GenerativeModel(self.model_validation)
            response = model.generate_content([prompt, image])

            try:
                result = json.loads(response.text.replace("```json", "").replace("```", "").strip())
                boxes = result.get("boxes", []) if isinstance(result, dict) else []
                # Basic normalization: ensure bboxes are int lists of length 4
                normalized = []
                for b in boxes:
                    try:
                        lbl = b.get("label", "product") if isinstance(b, dict) else "product"
                        coords = b.get("bbox") if isinstance(b, dict) else None
                        if coords and len(coords) == 4:
                            coords = [int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3])]
                            normalized.append({"label": lbl, "bbox": coords})
                    except Exception:
                        continue
                return normalized
            except Exception:
                logger.warning("⚠️  Não foi possível parsear resposta de detecção de bounding boxes")
                return []

        except Exception as e:
            logger.error(f"❌ Erro na detecção de bboxes: {str(e)}")
            return []


# Singleton instance
_gemini_client = None


def get_gemini_client() -> GeminiClient:
    """Get or create GeminiClient singleton instance."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client


def send_to_gemini(
    image_paths: List[str], 
    ocr_texts: List[str] = None,  # Deprecated, kept for compatibility
    eans: List[str] = None,  # Deprecated, kept for compatibility
    metadatas: List[dict] = None  # Deprecated, kept for compatibility
) -> dict:
    """
    Convenience function to send data to Gemini API.
    
    Args:
        image_paths: List of paths to product images (3 expected)
        ocr_texts: DEPRECATED - not used anymore
        eans: DEPRECATED - not used anymore
        metadatas: DEPRECATED - not used anymore
        
    Returns:
        Dictionary with gemini_response and product_image_path
    """
    client = get_gemini_client()
    return client.extract_product_data(image_paths)


def generate_product_images_with_gemini(product_image_path: str, product_name: str, product_id: int = None) -> dict:
    """
    Generate product images with white background using Gemini 2.0 multimodal.
    Upload to GCS and return public URLs.
    
    Args:
        product_image_path: Path to the original product image
        product_name: Name of the product (used only for file naming)
        product_id: Optional product ID for better organization in GCS
        
    Returns:
        Dictionary with public_urls only
    """
    from app.cloud import get_storage_client
    import io
    import tempfile
    import os
    from datetime import datetime
    
    client = get_gemini_client()
    storage_client = get_storage_client()
    
    # Convert MPO to JPEG if needed
    converted_path, was_converted = convert_mpo_to_jpeg(product_image_path)
    temp_files = []
    if was_converted:
        temp_files.append(converted_path)
    
    # Load the original product image (now guaranteed to be compatible)
    original_image = PIL.Image.open(converted_path)
    
    # Detect product inside packaging and crop if appropriate
    # NOTE (crop): we call `detect_product_bboxes` to attempt a tight
    # crop around the product illustration. Cropping can help when the
    # product artwork is large and centered; however, cropping small
    # or texture-only regions removes visual cues and often causes the
    # generator to hallucinate unrelated products. The crop here is
    # guarded by thresholds (area ratio + minimum pixels) — see below.
    try:
        # keep reference to full image in case we need it
        original_full = original_image
        boxes = client.detect_product_bboxes(original_full)
        if not boxes:
            logger.info("    ℹ️  No product bboxes detected in image; using full image")
        else:
            # choose largest box by area
            w, h = original_full.size
            def area(box):
                ymin, xmin, ymax, xmax = box['bbox']
                return max(0, (ymax - ymin)) * max(0, (xmax - xmin))
            largest = max(boxes, key=area)
            ymin, xmin, ymax, xmax = largest['bbox']
            bbox_area = area(largest)
            area_ratio = bbox_area / (w * h) if (w * h) > 0 else 0
            logger.info(f"    🧭 Detected product bbox area_ratio={area_ratio:.3f} (pixels={bbox_area})")
            # Crop thresholds:
            # - AREA_RATIO_THRESHOLD: fraction of the whole image area the
            #   detected bbox must occupy to be considered meaningful.
            # - MIN_BBOX_PIXELS: absolute minimum pixel area to avoid tiny
            #   texture-only crops (common on packaging photography).
            # These values are conservative to reduce false crops; adjust
            # via code if you want more aggressive cropping for other datasets.
            AREA_RATIO_THRESHOLD = 0.03
            MIN_BBOX_PIXELS = 5000
            if area_ratio >= AREA_RATIO_THRESHOLD and bbox_area >= MIN_BBOX_PIXELS:
                # add small padding
                pad = 0.05
                pad_y = int((ymax - ymin) * pad)
                pad_x = int((xmax - xmin) * pad)
                left = max(0, xmin - pad_x)
                upper = max(0, ymin - pad_y)
                right = min(w, xmax + pad_x)
                lower = min(h, ymax + pad_y)
                cropped = original_full.crop((left, upper, right, lower))
                # Save crop to temp file for inspection (helps debug bad crops).
                # These temporary crops are appended to `temp_files` so they
                # are cleaned up at the end of processing. If you want to
                # preserve problematic crops, move them to a persistent
                # debug directory instead of deleting.
                try:
                    tmp_crop = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                    tmp_crop_path = tmp_crop.name
                    tmp_crop.close()
                    cropped.save(tmp_crop_path, 'PNG')
                    temp_files.append(tmp_crop_path)
                    logger.info(f"    🧩 Image cropped and saved for inspection: {tmp_crop_path}")
                except Exception as save_err:
                    logger.warning(f"    ⚠️  Could not save crop file: {save_err}")
                # replace original_image with cropped PIL image for processing/validation
                try:
                    original_full.close()
                except Exception:
                    pass
                # Replace `original_image` with the cropped region for
                # subsequent generation/validation only when thresholds
                # are met (see above). If cropping is later disabled,
                # this assignment can be removed so generation always
                # receives the full original image.
                original_image = cropped
            else:
                logger.info(f"    ℹ️  Crop skipped (area_ratio={area_ratio:.3f}, pixels={bbox_area}) — using full image to avoid texture-only crops")
                # keep original_image as full image
                original_image = original_full
    except Exception as e:
        logger.warning(f"⚠️  Detection/crop step failed: {e}")
        # fallback to full image on error
        try:
            original_image = original_full
        except Exception:
            pass
            
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    public_urls = []
    
    logger.info(f"  🎨 Gerando imagens em 2 etapas...")
    
    # Generation config for deterministic results
    generation_config = {
        'temperature': 0,
        'top_p': 0.95,
        'top_k': 20
    }
    
    # Helper function to generate with retry and validation
    def generate_with_retry(prompt: str, input_image: PIL.Image.Image, angle_name: str, 
                           validate: bool = True, max_retries: int = 2) -> tuple:
        """
        Generate image with retry and optional validation.
        
        Returns:
            Tuple of (image_data_bytes, success: bool)
        """
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"        🔄 Tentativa {attempt + 1}/{max_retries}...")
                
                import time
                model = genai.GenerativeModel(
                    client.model_multimodal,
                    generation_config=generation_config
                )
                start_ts = time.time()
                response = model.generate_content([prompt, input_image])
                elapsed = time.time() - start_ts
                try:
                    text_trunc = getattr(response, 'text', '')[:300]
                except Exception:
                    text_trunc = ''
                logger.debug(
                    "Gemini generate_content attempt=%d elapsed=%.2fs has_candidates=%s text_trunc=%s",
                    attempt + 1,
                    elapsed,
                    bool(getattr(response, 'candidates', None)),
                    text_trunc
                )
                
                # Extract image data: search all candidates/parts and pick the best (largest) valid payload
                image_data = None
                image_candidates = []
                MIN_BYTES_THRESHOLD = 1024

                if hasattr(response, 'candidates') and response.candidates:
                    candidate_index = 0
                    for candidate in response.candidates:
                        content = getattr(candidate, 'content', None)
                        parts = getattr(content, 'parts', None) if content is not None else None
                        if not parts:
                            candidate_index += 1
                            continue
                        part_sizes = []
                        for part in parts:
                            inline = getattr(part, 'inline_data', None)
                            if inline is None:
                                part_sizes.append(0)
                                continue
                            data = getattr(inline, 'data', None)
                            if data is None:
                                part_sizes.append(0)
                                continue
                            try:
                                data_size = len(data)
                            except Exception:
                                data_size = 0
                            part_sizes.append(data_size)
                            # collect candidate for later selection (use the largest part)
                            image_candidates.append((data_size, data))
                        logger.debug("Candidate %d part_sizes=%s", candidate_index, part_sizes)
                        candidate_index += 1

                    # Log collected sizes summary
                    sizes_summary = [s for s, _ in image_candidates]
                    logger.debug("Collected image_candidates sizes=%s", sizes_summary)
                    # If all sizes are zero, persist a small dump for offline inspection
                    if sizes_summary and all(s == 0 for s in sizes_summary):
                        try:
                            dump = {
                                'attempt': attempt + 1,
                                'prompt_sample': (prompt[:300] if isinstance(prompt, str) else str(type(prompt))),
                                'sizes': sizes_summary,
                                'response_repr': repr(response)
                            }
                            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.json', prefix='gemini_dump_')
                            tmp.write(json.dumps(dump, ensure_ascii=False, default=str).encode('utf-8'))
                            tmp.close()
                            logger.warning("Anomaly detected: all payload sizes == 0 — dump saved: %s", tmp.name)
                        except Exception as e:
                            logger.warning("Failed to save Gemini dump: %s", str(e))

                # If we collected candidates, choose the largest one above threshold
                if image_candidates:
                    # sort descending by size
                    image_candidates.sort(key=lambda x: x[0], reverse=True)
                    best_size, best_data = image_candidates[0]
                    if best_size < MIN_BYTES_THRESHOLD:
                        logger.warning(f"        ⚠️  Melhor payload muito pequeno ({best_size} bytes)")
                        # for debugging, log the sizes we saw
                        sizes = [s for s, _ in image_candidates]
                        logger.debug(f"        🔍 Payload sizes seen: {sizes}")
                        image_data = None
                    else:
                        image_data = best_data
                
                if not image_data:
                    logger.warning(f"        ⚠️  Nenhum dado de imagem retornado")
                    continue
                
                # Save temporarily for validation
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png', mode='wb')
                temp_file.write(image_data)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_file.close()
                temp_path = temp_file.name
                
                # Validate it's a real image
                try:
                    test_img = PIL.Image.open(temp_path)
                    test_img.close()
                except Exception as img_err:
                    logger.warning(f"        ⚠️  Imagem inválida: {img_err}")
                    os.remove(temp_path)
                    continue
                
                # Validate quality with AI (if requested)
                if validate:
                    validation = client.validate_generated_image(
                        original_image,
                        temp_path,
                        angle_name
                    )
                    
                    if validation['approved'] and validation['confidence'] >= 70:
                        logger.info(f"        ✅ Validação aprovada (confiança: {validation['confidence']}%)")
                        os.remove(temp_path)
                        return (image_data, True)
                    else:
                        issues = ", ".join(validation.get('issues', ['Unknown']))
                        logger.warning(f"        ❌ Validação rejeitada (confiança: {validation['confidence']}%): {issues}")
                        os.remove(temp_path)
                        if attempt < max_retries - 1:
                            continue
                        else:
                            # Last attempt, use it anyway
                            logger.warning(f"        ⚠️  Usando imagem mesmo após rejeição (última tentativa)")
                            return (image_data, False)
                else:
                    # No validation requested, just return
                    os.remove(temp_path)
                    return (image_data, True)
                    
            except Exception as e:
                logger.error(f"        ❌ Erro na tentativa {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    return (None, False)
        
        return (None, False)
    
    # ========== STEP 1: Generate clean image with white background ==========
    logger.info(f"    → ETAPA 1: Removendo fundo e gerando imagem base...")
    
    step1_prompt = (
        "TASK: Generate a professional product shot. Isolate the MAIN PRODUCT and place it on a PURE WHITE BACKGROUND (#FFFFFF)."
        "INSTRUCTIONS:"
        "1. IDENTIFICATION: If the image is a photo of a box/packaging, EXTRACT the product depicted on the packaging artwork. Ignore the box itself."
        "2. ISOLATION: Remove all external elements: shelves, price tags, hands, barcodes, and the packaging material."
        "3. RECONSTRUCTION: Render the product as a 3D physical object. Ensure the surface textures reflect the actual product material (e.g., polished metal, ceramic) rather than the printed texture of the cardboard box."
        "4. CLEANING: Remove any temporary stickers or plastic wrap. Keep only the permanent product labels and logos."
        "5. OUTPUT: A single, centered, high-definition image of the product alone."
        ""
        "Return ONLY the generated image."
    )

    # Generate base image with retry and validation
    base_image_data, success = generate_with_retry(
        step1_prompt, 
        original_image, 
        "white background front view",
        validate=True,
        max_retries=3
    )
    
    if not base_image_data:
        logger.error(f"      ❌ Falha ao gerar imagem base após todas as tentativas")
        return {"public_urls": [], "num_generated": 0}
    
    # Save and upload base image
    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png', mode='wb')
        temp_file.write(base_image_data)
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()
        base_image_path = temp_file.name
        temp_files.append(base_image_path)
        
        data_size = len(base_image_data)
        logger.info(f"      ✓ Imagem base salva ({data_size} bytes): {os.path.basename(base_image_path)}")
        
        # Upload base image (front_view)
        folder_name = f"produto_{product_id}_{product_name.replace(' ', '_')}" if product_id else product_name.replace(' ', '_')
        destination_blob_name = f"products/{folder_name}/{timestamp}_front_view.png"
        url = storage_client.upload_image(base_image_path, destination_blob_name)
        public_urls.append(url)
        logger.info(f"      ✓ Imagem base enviada ao GCS: front_view")
        
        # Load the clean base image for next steps
        base_image = PIL.Image.open(base_image_path)
        logger.info(f"      ✓ Imagem base carregada para gerar variações")
        
    except Exception as e:
        logger.error(f"      ❌ Erro ao processar imagem base: {str(e)}")
        return {"public_urls": [], "num_generated": 0}
    
    # ========== STEP 2: Generate variations from clean base image ==========
    logger.info(f"    → ETAPA 2: Gerando 3 variações a partir da imagem limpa...")
    
    variations = [
        {
            "angle": "side_view",
            "angle_description": "45-degree side view",
            "prompt": "Show this SAME product from a 45-degree side view. Keep SAME packaging, SAME logos, SAME colors, SAME text. Do not change the product. White background. Return ONE PNG."
        },
        {
            "angle": "perspective_view",
            "angle_description": "3/4 perspective angle",
            "prompt": "Show this SAME product from a 3/4 perspective angle. Keep SAME packaging, SAME logos, SAME colors, SAME text. Do not change the product. White background. Return ONE PNG."
        },
        {
            "angle": "lifestyle",
            "angle_description": "lifestyle setting",
            "prompt":"Take the EXACT product from the provided image and place it in a realistic kitchen setting; DO NOT modify the product's shape, color, or branding; The product must be the protagonist on a clean countertop with natural lighting; Return ONLY the PNG."
        }
    ]
    
    for idx, variation in enumerate(variations):
        try:
            logger.info(f"      → Gerando: {variation['angle']}...")
            
            # Generate with retry and validation
            image_data, success = generate_with_retry(
                variation['prompt'],
                base_image,
                variation['angle_description'],
                validate=True,
                max_retries=3
            )
            
            if not image_data:
                logger.warning(f"        ⚠️  Falha ao gerar {variation['angle']} após todas as tentativas")
                continue
            
            # Save and upload
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png', mode='wb')
            temp_file.write(image_data)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()
            temp_files.append(temp_file.name)
            
            folder_name = f"produto_{product_id}_{product_name.replace(' ', '_')}" if product_id else product_name.replace(' ', '_')
            destination_blob_name = f"products/{folder_name}/{timestamp}_{variation['angle']}.png"
            
            url = storage_client.upload_image(temp_file.name, destination_blob_name)
            public_urls.append(url)
            
            data_size = len(image_data)
            status = "✅" if success else "⚠️"
            logger.info(f"        {status} {variation['angle']} enviada ({data_size} bytes)")
                
        except Exception as e:
            logger.error(f"        ❌ Erro ao gerar {variation['angle']}: {str(e)}")
            continue
    
    # Close base_image to release file handle
    if 'base_image' in locals():
        base_image.close()
    
    # Close original_image to release file handle
    if 'original_image' in locals():
        original_image.close()
    
    # Cleanup temporary files
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                logger.debug(f"🧹 Arquivo temporário removido: {temp_file}")
        except PermissionError:
            logger.warning(f"⚠️  Não foi possível deletar arquivo temporário: {temp_file}")
    
    logger.info(f"  ✅ Total: {len(public_urls)} imagem(ns) gerada(s) e enviada(s)")
    
    return {
        "public_urls": public_urls,
        "num_generated": len(public_urls)
    }
