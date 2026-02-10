from typing import List
from fastapi import FastAPI, UploadFile, File, Form
from app.ocr import process_images, preprocess_image, extract_barcodes
from PIL import Image
from app.validation import send_to_gemini
import os
import tempfile
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI()

@app.post("/upload/")
async def upload_images(files: List[UploadFile] = File(...)):
    return [{"filename": file.filename, "content_type": file.content_type} for file in files]

@app.post("/process-ocr/")
async def process_ocr(files: List[UploadFile] = File(...)):
    results = await process_images(files)
    return {"results": results}

@app.post("/process-barcodes/")
async def process_barcodes(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        try:
            # Open the uploaded file as an image
            image = Image.open(file.file)
            
            # Preprocess the image
            preprocessed_image = preprocess_image(image)
            
            # Extract barcodes using pyzbar
            barcodes = extract_barcodes(preprocessed_image)
            
            # Append the result
            results.append({
                "filename": file.filename,
                "barcodes": barcodes
            })
        except Exception as e:
            # Log the error and continue with the next file
            results.append({
                "filename": file.filename,
                "error": str(e)
            })
    return {"results": results}

@app.post("/process-images/")
async def process_images_with_ai(files: List[UploadFile] = File(...)):
    results = []

    for idx, file in enumerate(files):
        try:
            # Salvar o arquivo temporariamente no sistema de arquivos
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1], mode="wb") as temp_file:
                temp_file.write(file.file.read())
                temp_file.flush()
                temp_file_path = temp_file.name

            # Verificar se o arquivo foi salvo corretamente
            if not os.path.exists(temp_file_path):
                raise FileNotFoundError(f"Arquivo temporário não encontrado: {temp_file_path}")

            # Abrir o arquivo salvo como imagem
            image = Image.open(temp_file_path)

            # Pré-processar a imagem
            preprocessed_image = preprocess_image(image)

            # Executar OCR
            ocr_results = await process_images([file])  # Corrigido para aguardar a coroutine
            ocr_text = ocr_results[0]  # Obter o primeiro resultado do OCR

            # Detectar códigos de barras
            barcodes = extract_barcodes(preprocessed_image)
            ean = barcodes[0] if barcodes else ""  # Pega o primeiro código de barras ou vazio

            # Obter metadados da imagem
            metadata = {
                "image_width": image.width,
                "image_height": image.height,
                "image_format": image.format
            }

            # Enviar para a API do Gemini
            gemini_response = send_to_gemini(temp_file_path, ocr_text, ean, metadata)

            # Adicionar o resultado ao array de resultados
            results.append({
                "product_id": idx + 1,  # Identificador único para cada produto
                "filename": file.filename,
                "gemini_response": gemini_response
            })

        except Exception as e:
            # Logar o erro e continuar com o próximo arquivo
            results.append({
                "product_id": idx + 1,
                "filename": file.filename,
                "error": str(e)
            })

        finally:
            # Remover o arquivo temporário
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return {"results": results}
