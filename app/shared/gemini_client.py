import os
import logging
import tempfile
import PIL.Image
from typing import List, Tuple, Dict, Any
from pathlib import Path
from datetime import datetime
from google import genai

logger = logging.getLogger(__name__)

def convert_mpo_to_jpeg(image_path: str) -> Tuple[str, bool]:
    try:
        with PIL.Image.open(image_path) as img:
            if img.format == 'MPO' or Path(image_path).suffix.lower() == '.mpo':
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg', prefix='conv_')
                temp_path = temp_file.name
                temp_file.close()
                if img.mode != 'RGB': img = img.convert('RGB')
                img.save(temp_path, 'JPEG', quality=95)
                return temp_path, True
            return image_path, False
    except Exception as e:
        logger.warning(f"Erro conversão: {e}")
        return image_path, False

def generate_product_images_with_gemini(product_image_path: str, prompt: str, product_name: str = "product", **kwargs) -> Dict[str, Any]:
    from app.cloud import get_storage_client
    
    if not product_image_path or not os.path.exists(product_image_path):
        logger.error("❌ Caminho da imagem inválido no shared.")
        return {"public_urls": [], "num_generated": 0}

    storage_client = get_storage_client()
    temp_files = []

    try:
        with PIL.Image.open(product_image_path) as img:
            if img.mode in ('RGBA', 'P'): img = img.convert('RGB')

            # O modelo gemini-2.5-flash-image processa o seu prompt manual aqui
            model = genai.GenerativeModel('gemini-2.5-flash-image')
            response = model.generate_content([prompt, img])

            if not response.candidates or not response.candidates[0].content.parts:
                raise ValueError("Nenhuma imagem gerada pela IA.")

            # Extração do binário da imagem gerada
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                tmp.write(response.candidates[0].content.parts[0].inline_data.data)
                out_path = tmp.name
                temp_files.append(out_path)

        # Upload para GCS
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = product_name.replace(' ', '_').lower()
        blob_name = f"products/{folder}/{ts}_final.png"
        
        url = storage_client.upload_image(out_path, blob_name)
        return {"public_urls": [url], "num_generated": 1}

    except Exception as e:
        logger.error(f"Erro geração imagem: {e}", exc_info=True)
        return {"public_urls": [], "error": str(e)}
    finally:
        for f in temp_files:
            if os.path.exists(f): os.remove(f)