from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class BrandDataStatus:
    brand_id: int
    category_id: int
    total_reviews: Optional[int]
    latest_review_time: Optional[datetime]
    data_freshness_days: Optional[int]
    last_evaluated_at: Optional[datetime]
