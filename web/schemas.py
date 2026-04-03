# web/schemas.py

from pydantic import BaseModel
from typing import List, Optional


class EvaluateRequest(BaseModel):
    brand: str
    category: Optional[str] = None


class EvaluateResponse(BaseModel):
    brand: str
    category: Optional[str]
    score: Optional[float]
    message: str
    status: str

class AnalysisFormRequest(BaseModel):
    fullName: str
    address: Optional[str] = None
    phone: Optional[str] = None
    mode: str  # 'evaluate' hoặc 'compare'
    brands: List[str]
    category: Optional[str] = None