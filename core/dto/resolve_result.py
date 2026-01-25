from dataclasses import dataclass
from typing import Optional

@dataclass
class ResolveResult:
    status: str               # VALID | INVALID_BRAND | INVALID_CATEGORY
    brand_id: Optional[int]
    category_id: Optional[int]
