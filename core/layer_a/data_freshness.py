"""
data_freshness.py

Layer A – Data freshness & coverage evaluation
"""

from datetime import datetime
from typing import Optional

from core.dto.evaluation_result import EvaluationResult
from core.dto.brand_data_status import BrandDataStatus
from config import MAX_REVIEW_STALE_DAYS  # 30 ngày sẽ kích hoạt crawl lại (incremental)


class DataFreshnessEvaluator:
    MIN_REVIEWS = 30
    
    def evaluate(
        self,
        status: Optional[BrandDataStatus]
    ) -> EvaluationResult:

        # ===============================
        # CASE 1: CHƯA CÓ BẤT KỲ DỮ LIỆU NÀO
        # ===============================
        if status is None:
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
        # CASE 3: KIỂM TRA ĐỘ CŨ (SỬA LẠI THEO 30 NGÀY)
        # ===============================
        # Dùng last_evaluated_at (tương đương GeneratedAt) để xem lần cuối chấm điểm là khi nào
        last_eval = getattr(status, 'last_evaluated_at', None) 
        
        if not last_eval:
            freshness_status = "STALE"
        else:
            days_old = (datetime.now() - last_eval).days
            freshness_status = (
                "FRESH"
                if days_old <= MAX_REVIEW_STALE_DAYS  # 30 ngày
                else "STALE"
            )

        # ===============================
        # CASE 4: QUYẾT ĐỊNH
        # ===============================
        if freshness_status == "STALE":
            # ❗ DỮ LIỆU CŨ QUÁ 30 NGÀY → BẮT BUỘC KÍCH HOẠT CRAWL LẠI
            return EvaluationResult(
                coverage_status=coverage_status,
                freshness_status="STALE",
                recommended_action="NEED_INCREMENTAL_CRAWL"
            )

        # Dữ liệu mới (dưới 30 ngày) → cho phép dùng luôn để hiển thị
        return EvaluationResult(
            coverage_status=coverage_status,
            freshness_status="FRESH",
            recommended_action="READY_FOR_ANALYSIS"
        )