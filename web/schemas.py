# web/schemas.py

from pydantic import BaseModel
from typing import Optional


class EvaluateRequest(BaseModel):
    brand: str
    category: Optional[str] = None


class EvaluateResponse(BaseModel):
    brand: str
    category: Optional[str]
    score: Optional[float]
    message: str
    status: str
