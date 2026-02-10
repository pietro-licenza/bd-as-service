"""
Gemini API client for product data extraction.
"""
import os
import json
import logging
from typing import List
import google.generativeai as genai
import PIL.Image

from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for interacting with Google Gemini API."""
    
    def __init__(self):
        """Initialize Gemini client with API key from settings."""
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_text = settings.GEMINI_MODEL_TEXT  # For text extraction
        self.model_multimodal = settings.GEMINI_MODEL_MULTIMODAL  # For image generation
    
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
        # Load all images
        images = [PIL.Image.open(path) for path in image_paths]
        
        # Build prompt
        prompt = self._build_extraction_prompt()
        
        # Prepare content (prompt + all images)
        contents = [prompt] + images
        
        # Send to Gemini API
        model = genai.GenerativeModel(self.model_text)
        response = model.generate_content(contents)
        
        # Parse response to find which image is the product
        try:
            response_json = json.loads(response.text.replace("```json", "").replace("```", "").strip())
            product_index = response_json.get("product_image_index", 2) - 1  # Convert to 0-based index
            product_image_path = image_paths[product_index] if 0 <= product_index < len(image_paths) else image_paths[-1]
        except:
            # Fallback: use last image
            product_image_path = image_paths[-1] if len(image_paths) >= 3 else image_paths[0]
        
        return {
            "gemini_response": response.text,
            "product_image_path": product_image_path
        }
    
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
            "- PRODUTO LIMPO: Foto do produto físico (pode ter papéis/etiquetas sobre ele) (OBRIGATÓRIA)\n\n"
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
            
            "DA FOTO DO PRODUTO LIMPO (SEMPRE PRESENTE):\n"
            "- Identifique qual é a imagem (número) para retornar no campo 'product_image_index'\n\n"
            
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
    
    # Load the original product image
    original_image = PIL.Image.open(product_image_path)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    public_urls = []
    temp_files = []
    
    logger.info(f"  🎨 Gerando imagens em 2 etapas...")
    
    # ========== STEP 1: Generate clean image with white background ==========
    logger.info(f"    → ETAPA 1: Removendo fundo e gerando imagem base...")
    
    step1_prompt = (
        "Remove the background from this product image. "
        "Replace it with pure white background (#FFFFFF). "
        "Remove any price tags, stickers, papers, or labels attached to the product. "
        "Keep the product itself exactly as it is - same color, shape, original product labels and branding. "
        "Do NOT change the product design. Only remove background and temporary stickers/tags. "
        "Return ONE clean PNG image with white background."
    )
    
    try:
        model1 = genai.GenerativeModel(client.model_multimodal)
        response1 = model1.generate_content([step1_prompt, original_image])
        
        # Save the clean base image
        base_image_path = None
        if hasattr(response1, 'candidates') and response1.candidates:
            for candidate in response1.candidates:
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data is not None:
                            if hasattr(part.inline_data, 'data') and part.inline_data.data is not None:
                                # Save base image temporarily
                                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                                temp_file.write(part.inline_data.data)
                                temp_file.close()
                                base_image_path = temp_file.name
                                temp_files.append(base_image_path)
                                
                                # Upload base image (front_view)
                                folder_name = f"produto_{product_id}_{product_name.replace(' ', '_')}" if product_id else product_name.replace(' ', '_')
                                destination_blob_name = f"products/{folder_name}/{timestamp}_front_view.png"
                                url = storage_client.upload_image(base_image_path, destination_blob_name)
                                public_urls.append(url)
                                logger.info(f"      ✓ Imagem base gerada e enviada: front_view")
                                break
                        break
                    break
        
        if not base_image_path:
            logger.error(f"      ❌ Falha ao gerar imagem base")
            return {"public_urls": [], "num_generated": 0}
        
        # Load the clean base image for next steps
        base_image = PIL.Image.open(base_image_path)
        
    except Exception as e:
        logger.error(f"      ❌ Erro na etapa 1: {str(e)}")
        return {"public_urls": [], "num_generated": 0}
    
    # ========== STEP 2: Generate variations from clean base image ==========
    logger.info(f"    → ETAPA 2: Gerando 3 variações a partir da imagem limpa...")
    
    variations = [
        {
            "angle": "side_view",
            "prompt": "Create a side view (45-degree angle) of this product. Keep white background. Keep product exactly as shown. Return ONE PNG image."
        },
        {
            "angle": "perspective_view",
            "prompt": "Create a 3/4 perspective view of this product. Keep white background. Keep product exactly as shown. Return ONE PNG image."
        },
        {
            "angle": "lifestyle",
            "prompt": "Place this EXACT product in a realistic room setting with natural lighting. For cleaning products use laundry/kitchen, for furniture use living room. Keep the product EXACTLY as shown. Return ONE photorealistic PNG image."
        }
    ]
    
    for idx, variation in enumerate(variations):
        try:
            logger.info(f"      → Gerando: {variation['angle']}...")
            
            model = genai.GenerativeModel(client.model_multimodal)
            response = model.generate_content([variation['prompt'], base_image])
            
            if hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data is not None:
                                if hasattr(part.inline_data, 'data') and part.inline_data.data is not None:
                                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                                    temp_file.write(part.inline_data.data)
                                    temp_file.close()
                                    temp_files.append(temp_file.name)
                                    
                                    folder_name = f"produto_{product_id}_{product_name.replace(' ', '_')}" if product_id else product_name.replace(' ', '_')
                                    destination_blob_name = f"products/{folder_name}/{timestamp}_{variation['angle']}.png"
                                    
                                    url = storage_client.upload_image(temp_file.name, destination_blob_name)
                                    public_urls.append(url)
                                    logger.info(f"        ✓ {variation['angle']} enviada")
                                    break
                            break
                        break
            else:
                logger.warning(f"        ⚠️  Nenhuma imagem gerada para {variation['angle']}")
                
        except Exception as e:
            logger.error(f"        ❌ Erro ao gerar {variation['angle']}: {str(e)}")
            continue
    
    # Close base_image to release file handle
    if 'base_image' in locals():
        base_image.close()
    
    # Cleanup temporary files
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except PermissionError:
            logger.warning(f"⚠️  Não foi possível deletar arquivo temporário: {temp_file}")
    
    logger.info(f"  ✅ Total: {len(public_urls)} imagem(ns) gerada(s) e enviada(s)")
    
    return {
        "public_urls": public_urls,
        "num_generated": len(public_urls)
    }
