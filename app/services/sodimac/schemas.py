"""
Pydantic schemas for Sodimac service request/response validation.
Inclui suporte para logs financeiros e metadados de lote (SDK 2026).
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class ProductUrlRequest(BaseModel):
    """Request model for product URL processing."""
    urls: List[str] = Field(..., description="Lista de URLs de produtos da Sodimac")

    class Config:
        json_schema_extra = {
            "example": {
                "urls": [
                    "https://www.sodimac.com.br/sodimac-br/product/123456/produto-exemplo/123456/",
                    "https://www.sodimac.com.br/sodimac-br/product/789012/outro-produto/789012/"
                ]
            }
        }


class ProductData(BaseModel):
    """Product data extracted from Sodimac with financial tracking."""
    titulo: Optional[str] = Field(None, description="Título do produto")
    preco: Optional[str] = Field(None, description="Preço extraído")
    marca: str = Field(default="", description="Marca do fabricante")
    ean: str = Field(default="", description="Código EAN")
    descricao: str = Field(default="", description="Descrição profissional gerada pela IA")
    image_urls: List[str] = Field(default_factory=list, description="Lista de URLs das imagens")
    url_original: str = Field(..., description="URL original do produto")
    
    # --- Campos de Log e Investimento ---
    input_tokens: int = Field(default=0, description="Tokens de entrada")
    output_tokens: int = Field(default=0, description="Tokens de saída")
    input_cost_brl: float = Field(default=0.0, description="Custo de entrada em R$")
    output_cost_brl: float = Field(default=0.0, description="Custo de saída em R$")
    total_cost_brl: float = Field(default=0.0, description="Custo total do item em R$")
    
    error: Optional[str] = Field(None, description="Mensagem de erro caso o processamento falhe")

    class Config:
        json_schema_extra = {
            "example": {
                "titulo": "Conjunto Estar Rattan Milan 4pcs",
                "preco": "R$ 1490,00",
                "marca": "Just Home Collection",
                "total_cost_brl": 0.0045,
                "url_original": "https://www.sodimac.com.br/..."
            }
        }


class BatchResponse(BaseModel):
    """Response model for Sodimac batch processing."""
    products: List[ProductData] = Field(..., description="Lista de produtos processados")
    total_products: int = Field(..., description="Total de itens no lote")
    excel_download_url: Optional[str] = Field(None, description="Caminho para download do Excel")
    total_cost_batch_brl: float = Field(default=0.0, description="Investimento total do lote em R$")

    class Config:
        json_schema_extra = {
            "example": {
                "products": [],
                "total_products": 2,
                "total_cost_batch_brl": 0.0090,
                "excel_download_url": "/exports/sodimac_produtos_2026.xlsx"
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Mensagem de erro")
    details: Optional[str] = Field(None, description="Detalhes adicionais do erro")