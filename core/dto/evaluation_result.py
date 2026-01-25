from dataclasses import dataclass

@dataclass
class EvaluationResult:
    coverage_status: str       # ENOUGH | NOT_ENOUGH
    freshness_status: str      # FRESH | STALE
    recommended_action: str    # READY_FOR_ANALYSIS | NEED_INCREMENTAL_CRAWL | NEED_FULL_CRAWL
