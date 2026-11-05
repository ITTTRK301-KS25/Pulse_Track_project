from pydantic import BaseModel
from typing import Optional, Any

class ResponseCreate(BaseModel):
    status_code: int
    message: str
    data: Optional[Any]
    error: Optional[Any]
    timestamp: str
    path: str