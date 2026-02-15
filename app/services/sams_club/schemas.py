"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


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


class ProductPromptRequest(BaseModel):
    """Request for a single product with images and prompt."""
    product_id: str = Field(..., description="Product identifier in the batch")
    prompt: str = Field(..., description="Prompt livre para o produto")
    # Aqui pode ser uma lista de nomes de arquivos, ou base64, ou URLs temporários
    filenames: List[str] = Field(..., description="List of filenames")

class BatchProductResponse(BaseModel):
    product_id: str
    num_images: int
    filenames: List[str]
    prompt: str
    gemini_response: str
    generated_images_urls: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    
    # CAMPOS ESSENCIAIS PARA O CUSTO APARECER NO JS
    input_tokens: int = 0
    input_cost_brl: float = 0.0
    output_tokens: int = 0
    output_cost_brl: float = 0.0
    total_cost_brl: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class BatchResponse(BaseModel):
    products: List[BatchProductResponse]
    total_products: int
    excel_download_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class BatchProductResponse(BaseModel):
    """Response for a single product in batch processing."""
    product_id: str
    num_images: int
    filenames: List[str]
    prompt: str
    gemini_response: str
    generated_images_urls: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    
    # NOVAS COLUNAS PARA O FRONTEND
    input_tokens: Optional[int] = 0
    input_cost_brl: Optional[float] = 0.0
    output_tokens: Optional[int] = 0
    output_cost_brl: Optional[float] = 0.0
    total_cost_brl: Optional[float] = 0.0