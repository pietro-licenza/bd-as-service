"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field
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
    """Response for a single product in batch processing."""
    product_id: str = Field(..., description="Product identifier in the batch")
    num_images: int = Field(..., description="Number of images for this product")
    filenames: List[str] = Field(..., description="List of filenames")
    prompt: str = Field(..., description="Prompt livre enviado para o produto")
    gemini_response: str = Field(..., description="Raw response from Gemini API")
    generated_images_urls: List[str] = Field(default_factory=list, description="URLs of generated product images in cloud")
    error: Optional[str] = Field(None, description="Error message if processing failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "product1",
                "num_images": 2,
                "filenames": ["img1.jpg", "img2.jpg"],
                "gemini_response": '{"nome_produto": "...", "preco": "...", "ean": "..."}',
                "generated_images_urls": [
                    "https://storage.googleapis.com/bucket/products/produto_1/image1.png",
                    "https://storage.googleapis.com/bucket/products/produto_1/image2.png"
                ]
            }
        }


class BatchResponse(BaseModel):
    """Response for batch processing."""
    products: List[BatchProductResponse] = Field(..., description="Results for each product")
    total_products: int = Field(..., description="Total number of products processed")
    excel_download_url: Optional[str] = Field(None, description="URL to download Excel report")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_products": 2,
                "products": [
                    {
                        "product_id": "product1",
                        "num_images": 3,
                        "filenames": ["img1.jpg", "img2.jpg", "img3.jpg"],
                        "gemini_response": "{...}"
                    }
                ],
                "excel_download_url": "/exports/produtos_20260205_143022.xlsx"
            }
        }
