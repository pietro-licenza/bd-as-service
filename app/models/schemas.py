"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Any
from datetime import datetime

# --- SCHEMAS EXISTENTES (PRODUTOS / IMAGENS / GEMINI) ---

class ProductResponse(BaseModel):
    """Response model for product processing."""
    num_images: int = Field(..., description="Number of images processed")
    filenames: List[str] = Field(..., description="List of processed filenames")
    gemini_response: str = Field(..., description="Raw response from Gemini API")
    
    class Config:
        json_schema_extra = {
            "example": {
                "num_images": 2,
                "filenames": ["image1.jpg", "image2.jpg"],
                "gemini_response": '{"nome_produto": "Product Name", "preco": "10.99", "ean": "123456789"}'
            }
        }

class ErrorResponse(BaseModel):
    """Error response model."""
    num_images: int = Field(..., description="Number of images attempted")
    filenames: List[str] = Field(..., description="List of filenames")
    error: str = Field(..., description="Error message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "num_images": 2,
                "filenames": ["image1.jpg", "image2.jpg"],
                "error": "Failed to process images"
            }
        }

class BarcodeResult(BaseModel):
    """Barcode detection result."""
    filename: str
    barcodes: List[dict]

class OCRResult(BaseModel):
    """OCR processing result."""
    filename: str
    text: str
    patterns: dict
    barcodes: List[dict]

class BatchProductResponse(BaseModel):
    """Response for a single product in batch processing."""
    product_id: int = Field(..., description="Product identifier in the batch")
    num_images: int = Field(..., description="Number of images for this product")
    filenames: List[str] = Field(..., description="List of filenames")
    gemini_response: str = Field(..., description="Raw response from Gemini API")
    error: Optional[str] = Field(None, description="Error message if processing failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_id": 1,
                "num_images": 3,
                "filenames": ["img1.jpg", "img2.jpg"],
                "gemini_response": '{"nome_produto": "...", "preco": "...", "ean": "..."}'
            }
        }

class BatchResponse(BaseModel):
    """Response for batch processing."""
    total_products: int = Field(..., description="Total number of products processed")
    total_images: int = Field(..., description="Total number of images processed")
    products: List[BatchProductResponse] = Field(..., description="Results for each product")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_products": 2,
                "total_images": 5,
                "products": [
                    {
                        "product_id": 1,
                        "num_images": 3,
                        "filenames": ["img1.jpg", "img2.jpg", "img3.jpg"],
                        "gemini_response": "{...}"
                    }
                ]
            }
        }

# --- SCHEMAS DE USUÁRIO (NECESSÁRIOS PARA AUTH) ---

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    loja_permissao: Optional[str] = "todas"

class UserResponse(UserBase):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

# --- NOVOS SCHEMAS: MONITORAMENTO DE ESTOQUE ---

class MonitoringTermBase(BaseModel):
    marketplace: str = Field(..., description="Marketplace para pesquisa (ex: leroy_merlin)")
    term: str = Field(..., description="Termo a ser pesquisado (ex: gazebo)")
    is_active: bool = Field(True, description="Status do monitoramento")

class MonitoringTermCreate(MonitoringTermBase):
    """Schema para criação de um termo de monitoramento"""
    pass

class MonitoringTermResponse(MonitoringTermBase):
    """Schema de resposta para termos de monitoramento"""
    id: int
    created_at: datetime
    last_run: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class StockHistoryResponse(BaseModel):
    """Schema para histórico de estoque"""
    id: int
    stock_count: int
    is_available: bool
    recorded_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class MonitoredProductResponse(BaseModel):
    """Schema para detalhes do produto monitorado e seu histórico"""
    id: int
    product_id: str
    marketplace: str
    name: str
    url: Optional[str] = None
    first_seen_at: datetime
    last_updated_at: Optional[datetime] = None
    history: List[StockHistoryResponse] = []
    
    model_config = ConfigDict(from_attributes=True)