from pydantic import BaseModel
from typing import Optional

class CBNotification(BaseModel):
    eventDate: str
    sellerId: int        # ID numérico da sua loja
    eventType: str       # New, Approved, Canceled, etc.
    resourceType: str    # Sempre "Orders"
    resourceId: int      # ID do pedido (numérico longo)
    uriResource: str     # Caminho para consulta detalhada (ex: /orders/{id})
    # O payload completo da notificação pode ser armazenado em 'raw_data' na tabela