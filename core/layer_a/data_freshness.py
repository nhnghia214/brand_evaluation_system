"""
data_freshness.py

Layer A – Data freshness & coverage evaluation

Responsibility:
- Evaluate whether brand-category data is fresh and sufficient
- Decide recommended crawl action
- Pure decision logic (no crawl, no analysis, no DB write)
"""

from datetime import datetime
from typing import Optional

from core.dto.evaluation_result import EvaluationResult
from core.dto.brand_data_status import BrandDataStatus


class DataFreshnessEvaluator:
    # === CONSTANTS (MATCH LEGACY C#) ===
    MIN_REVIEWS = 30
    FRESHNESS_THRESHOLD_DAYS = 30

    def evaluate(
        self,
        status: Optional[BrandDataStatus]
    ) -> EvaluationResult:
        """
        Evaluate data freshness and coverage for a brand-category pair.

        :param status: BrandDataStatus or None if no data exists
        :return: EvaluationResult
        """

        # ===============================
        # CASE 1: NO DATA
        # ===============================
        if status is None:
            return EvaluationResult(
                coverage_status="NOT_ENOUGH",
                freshness_status="STALE",
                recommended_action="NEED_FULL_CRAWL"
            )

        # ===============================
        # CASE 2: COVERAGE
        # ===============================
        coverage_status = (
            "ENOUGH"
            if (status.total_reviews or 0) >= self.MIN_REVIEWS
            else "NOT_ENOUGH"
        )

        # ===============================
        # CASE 3: FRESHNESS
        # ===============================
        if status.latest_review_time is None:
            days_old = float("inf")
        else:
            days_old = (datetime.now() - status.latest_review_time).days

        freshness_status = (
            "FRESH"
            if days_old <= self.FRESHNESS_THRESHOLD_DAYS
            else "STALE"
        )

        # ===============================
        # CASE 4: DECISION
        # ===============================
        if coverage_status == "ENOUGH" and freshness_status == "FRESH":
            recommended_action = "READY_FOR_ANALYSIS"
        elif coverage_status == "ENOUGH" and freshness_status == "STALE":
            recommended_action = "NEED_INCREMENTAL_CRAWL"
        else:
            recommended_action = "NEED_FULL_CRAWL"

        return EvaluationResult(
            coverage_status=coverage_status,
            freshness_status=freshness_status,
            recommended_action=recommended_action
        )
