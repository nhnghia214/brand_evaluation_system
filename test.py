from core.layer_a.message_mapper import MessageMapper
from core.dto.evaluation_result import EvaluationResult

evaluation = EvaluationResult(
    coverage_status="ENOUGH",
    freshness_status="FRESH",
    recommended_action="READY_FOR_ANALYSIS"
)

msg = MessageMapper.map(evaluation, "NO_CRAWL_REQUIRED")
print(msg)
