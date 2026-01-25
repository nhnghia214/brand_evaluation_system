from datetime import datetime, timedelta
from core.layer_a.data_freshness import DataFreshnessEvaluator
from core.dto.brand_data_status import BrandDataStatus

evaluator = DataFreshnessEvaluator()

status = BrandDataStatus(
    brand_id=1,
    category_id=1,
    total_reviews=120,
    latest_review_time=datetime.now() - timedelta(days=10),
    data_freshness_days=10,
    last_evaluated_at=datetime.now()
)

result = evaluator.evaluate(status)
print(result)
