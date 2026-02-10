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
                "num_images": 2,
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
