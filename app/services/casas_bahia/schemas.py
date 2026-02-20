from pydantic import BaseModel
from typing import List, Optional

class CBOrderNotification(BaseModel):
    order_id: str
    status: str
    total_amount: float
    seller_id: Optional[str] = None
    # Adicione outros campos conforme a documentação deles