"""
Pydantic schemas for Decathlon service request/response validation.
"""
from pydantic import BaseModel, Field
from typing import List, Optional

class ProductUrlRequest(BaseModel):
    """Modelo para receber as URLs enviadas pelo utilizador"""
    urls: List[str] = Field(..., description="Lista de URLs da Decathlon")

class ProductData(BaseModel):
    """Modelo de cada produto processado (compatível com o seu dashboard)"""
    titulo: Optional[str] = None
    preco: Optional[str] = None
    marca: Optional[str] = None
    ean: Optional[str] = None
    descricao: Optional[str] = None
    image_urls: List[str] = []
    url_original: str
    
    # Campos financeiros e de tokens
    input_tokens: int = 0
    output_tokens: int = 0
    input_cost_brl: float = 0.0
    output_cost_brl: float = 0.0
    total_cost_brl: float = 0.0
    error: Optional[str] = None

class BatchResponse(BaseModel):
    """Modelo de resposta final do lote de processamento"""
    products: List[ProductData]
    total_products: int
    excel_download_url: Optional[str] = None
    total_cost_batch_brl: float = 0.0