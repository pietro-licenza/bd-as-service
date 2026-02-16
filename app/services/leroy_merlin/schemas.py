"""
Pydantic schemas for Leroy Merlin service request/response validation.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional


class ProductUrlRequest(BaseModel):
    """Request model for product URL processing."""
    urls: List[str] = Field(..., description="List of Leroy Merlin product URLs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "urls": [
                    "https://www.leroymerlin.com.br/produto-exemplo_123456",
                    "https://www.leroymerlin.com.br/outro-produto_789012"
                ]
            }
        }


class ProductData(BaseModel):
    """Modelo completo com campos financeiros para o dashboard."""
    titulo: Optional[str] = None
    preco: Optional[str] = None
    marca: Optional[str] = None
    ean: Optional[str] = None
    descricao: Optional[str] = None
    image_urls: List[str] = []
    url_original: str
    # Novos campos que o FastAPI precisa permitir a passagem:
    input_tokens: int = 0
    output_tokens: int = 0
    input_cost_brl: float = 0.0
    output_cost_brl: float = 0.0
    total_cost_brl: float = 0.0
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "titulo": "Mangueira com Enrolador de Plástico Parede 12m WAP",
                "preco": "R$ 199,90",
                "marca": "WAP",
                "ean": "7898152416549",
                "descricao": "Esta mangueira com enrolador de parede oferece praticidade e organização para o seu jardim...",
                "image_urls": [
                    "https://cdn.leroymerlin.com.br/products/..._1800x1800.jpg"
                ],
                "url_original": "https://www.leroymerlin.com.br/produto_123456"
            }
        }


class BatchResponse(BaseModel):
    """Response model for batch processing."""
    products: List[ProductData]
    total_products: int
    excel_download_url: Optional[str] = None
    total_cost_batch_brl: float = 0.0
    
    class Config:
        json_schema_extra = {
            "example": {
                "products": [],
                "total_products": 2,
                "excel_download_url": "/exports/leroy_produtos_20260206_143022.xlsx"
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Additional error details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Failed to process URLs",
                "details": "Invalid URL format"
            }
        }
