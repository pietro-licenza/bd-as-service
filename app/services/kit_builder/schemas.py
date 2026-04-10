"""
Pydantic schemas for Kit Builder service request/response validation.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class KitBuildRequest(BaseModel):
    """Request model para montagem de kit com múltiplas URLs de marketplaces."""
    urls: List[str] = Field(..., min_length=2, description="2 ou mais URLs de produtos de qualquer marketplace suportado")
    quantities: List[int] = Field(default=[], description="Quantidade de cada produto (índice corresponde à URL). Default: 1 para todos.")
    produto_central_index: int = Field(default=0, description="Índice (0-based) da URL que é o produto central/base do kit.")

    class Config:
        json_schema_extra = {
            "example": {
                "urls": [
                    "https://www.leroymerlin.com.br/mesa-exemplo_123456",
                    "https://www.sodimac.com.br/sodimac-br/product/789012/cadeira-exemplo/789012/"
                ],
                "quantities": [1, 6],
                "produto_central_index": 0
            }
        }


class IndividualProductData(BaseModel):
    """Dados de um produto individual extraído antes da unificação."""
    titulo: Optional[str] = None
    preco: Optional[str] = None
    preco_total: Optional[str] = None  # preco × quantidade
    marca: Optional[str] = None
    ean: Optional[str] = None
    modelo: Optional[str] = None
    marketplace: str
    url_original: str
    quantidade: int = 1
    is_produto_central: bool = False
    largura_cm: Optional[str] = None
    comprimento_cm: Optional[str] = None
    altura_cm: Optional[str] = None
    peso_kg: Optional[str] = None
    image_urls: List[str] = []
    error: Optional[str] = None


class KitProductData(BaseModel):
    """Produto unificado (o kit resultante)."""
    titulo: Optional[str] = None
    preco: Optional[str] = None
    marca: str = "Brazil Home Living"
    modelo: str = "Kit"
    ean: str = ""
    descricao: Optional[str] = None
    image_urls: List[str] = []
    url_original: str = ""

    # Dimensões máximas do kit (maior dimensão entre os produtos)
    largura_cm: Optional[str] = None
    comprimento_cm: Optional[str] = None
    altura_cm: Optional[str] = None
    dimensoes_lca: Optional[str] = None
    peso_kg: Optional[str] = None

    # Imagens geradas pelo Gemini (até 3: frontal, ângulo, lifestyle)
    generated_image_urls: List[str] = []
    image_generation_cost_brl: float = 0.0

    # Custo Gemini (texto)
    input_tokens: int = 0
    output_tokens: int = 0
    input_cost_brl: float = 0.0
    output_cost_brl: float = 0.0
    total_cost_brl: float = 0.0
    error: Optional[str] = None


class KitBuildResponse(BaseModel):
    """Response completo da montagem do kit."""
    kit: KitProductData
    individual_products: List[IndividualProductData]
    excel_download_url: Optional[str] = None
    total_cost_batch_brl: float = 0.0

    class Config:
        json_schema_extra = {
            "example": {
                "kit": {
                    "titulo": "Kit Mesa de Jantar + 2 Cadeiras - Brazil Home Living",
                    "preco": "R$ 1.499,90",
                    "marca": "Brazil Home Living",
                    "modelo": "Kit"
                },
                "individual_products": [],
                "excel_download_url": "/exports/kit_produtos_20260409_143022.xlsx"
            }
        }
