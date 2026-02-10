import httpx
import base64
import yaml
import os
from google import genai
from google.genai import types
import PIL.Image

# Carregar configurações do arquivo config.yaml
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../../config/config.yaml')
with open(CONFIG_PATH, 'r') as config_file:
    config = yaml.safe_load(config_file)

# Inicializa o cliente com a chave da API carregada do arquivo de configuração
client = genai.Client(api_key=config['gemini']['access_key'])

def send_to_gemini(image_path: str, ocr_text: str, ean: str, metadata: dict):
    """
    Envia os dados processados para a API do Gemini usando a biblioteca google.generativeai.

    :param image_path: Caminho para a imagem original.
    :param ocr_text: Texto extraído pelo OCR.
    :param ean: Código de barras detectado (ou vazio).
    :param metadata: Metadados da imagem (dimensões, formato, etc.).
    :return: Resposta da API do Gemini.
    """
    # Carregar a imagem como uma instância de PIL.Image
    img = PIL.Image.open(image_path)

    # Definir o prompt para extração
    prompt = (
        "Extraia todos os dados desta etiqueta de preço em formato JSON, "
        "A nossa prioridade é de extrair estes dados: Nome do Produto, Preço do produto e o código EAN que fica no código de barras."
        "Mando juntamente com a imagem, a prévia extraída pela nossa OCR e o código de barras detectado (se houver)."
        f"Texto OCR: {ocr_text}. Código de barras: {ean}."
    )

    # Enviar para a API usando o cliente configurado
    response = client.models.generate_content(
        model='gemini-2.5-flash-lite',
        contents=[prompt, img]
    )

    # Retornar a resposta da API
    return response.text
