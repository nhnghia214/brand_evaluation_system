"""
data_freshness.py

Layer A – Data freshness & coverage evaluation
"""

from datetime import datetime
from typing import Optional

from core.dto.evaluation_result import EvaluationResult
from core.dto.brand_data_status import BrandDataStatus


class DataFreshnessEvaluator:
    MIN_REVIEWS = 30
    FRESHNESS_THRESHOLD_DAYS = 5  # Số ngày để coi là "mới" 

    def evaluate(
        self,
        status: Optional[BrandDataStatus]
    ) -> EvaluationResult:

        # ===============================
        # CASE 1: CHƯA CÓ BẤT KỲ DỮ LIỆU NÀO
        # ===============================
        if status is None or status.latest_review_time is None:
            return EvaluationResult(
                coverage_status="NOT_ENOUGH",
                freshness_status="STALE",
                recommended_action="NEED_FULL_CRAWL"
            )

        # ===============================
        # CASE 2: KIỂM TRA COVERAGE
        # ===============================
        coverage_status = (
            "ENOUGH"
            if (status.total_reviews or 0) >= self.MIN_REVIEWS
            else "NOT_ENOUGH"
        )

        # ===============================
        # CASE 3: KIỂM TRA ĐỘ CŨ
        # ===============================
        days_old = (datetime.now() - status.latest_review_time).days

        freshness_status = (
            "FRESH"
            if days_old <= self.FRESHNESS_THRESHOLD_DAYS
            else "STALE"
        )

        # ===============================
        # CASE 4: QUYẾT ĐỊNH
        # ===============================
        if freshness_status == "STALE":
            # ❗ DỮ LIỆU CŨ → BẮT BUỘC CRAWL LẠI
            return EvaluationResult(
                coverage_status=coverage_status,
                freshness_status="STALE",
                recommended_action="NEED_INCREMENTAL_CRAWL"
            )

        # Dữ liệu mới → cho phép phân tích
        return EvaluationResult(
            coverage_status=coverage_status,
            freshness_status="FRESH",
            recommended_action="READY_FOR_ANALYSIS"
        )
