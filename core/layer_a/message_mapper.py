"""
message_mapper.py

Layer A – System message mapping

Responsibility:
- Map evaluation result and crawl job status to user-facing system message
- Pure rule-based mapping (no AI, no DB, no presentation)
"""

from typing import Optional

from core.dto.evaluation_result import EvaluationResult
from core.dto.user_message import UserMessage


class MessageMapper:

    @staticmethod
    def map(
        evaluation: Optional[EvaluationResult],
        crawl_job_status: str
    ) -> UserMessage:
        # ===============================
        # GUARD: evaluation == None
        # (CASE: category = ALL)
        # ===============================
        if evaluation is None:
            return UserMessage(
                message_key="READY",
                severity="SUCCESS",
                message="Dữ liệu tổng hợp đã sẵn sàng để phân tích thương hiệu."
            )

        # ===============================
        # RULE 1: DATA READY
        # ===============================
        if evaluation.recommended_action == "READY_FOR_ANALYSIS":
            return UserMessage(
                message_key="READY",
                severity="SUCCESS",
                message="Dữ liệu đã sẵn sàng để phân tích thương hiệu."
            )

        # ===============================
        # RULE 2: JOB JUST CREATED
        # ===============================
        if (
            evaluation.recommended_action in (
                "NEED_FULL_CRAWL",
                "NEED_INCREMENTAL_CRAWL"
            )
            and crawl_job_status == "JOB_CREATED"
        ):
            return UserMessage(
                message_key="DATA_UPDATING",
                severity="INFO",
                message=(
                    "Dữ liệu hiện tại chưa đủ hoặc đã cũ. "
                    "Hệ thống đang tự động cập nhật thêm đánh giá mới."
                )
            )

        # ===============================
        # RULE 3: JOB ALREADY EXISTS
        # ===============================
        if (
            evaluation.recommended_action in (
                "NEED_FULL_CRAWL",
                "NEED_INCREMENTAL_CRAWL"
            )
            and crawl_job_status == "JOB_ALREADY_EXISTS"
        ):
            return UserMessage(
                message_key="DATA_PENDING",
                severity="INFO",
                message="Dữ liệu đang được cập nhật. Vui lòng quay lại sau."
            )

        # ===============================
        # RULE 4: DATA INSUFFICIENT
        # ===============================
        if (
            evaluation.coverage_status == "NOT_ENOUGH"
            and crawl_job_status == "NO_CRAWL_REQUIRED"
        ):
            return UserMessage(
                message_key="DATA_INSUFFICIENT",
                severity="WARNING",
                message="Dữ liệu hiện tại chưa đủ để thực hiện đánh giá."
            )

        # ===============================
        # RULE 5: INVALID TARGET
        # ===============================
        if crawl_job_status == "INVALID_TARGET":
            return UserMessage(
                message_key="INVALID_TARGET",
                severity="WARNING",
                message="Thương hiệu hoặc danh mục chưa tồn tại trong hệ thống."
            )

        # ===============================
        # FALLBACK
        # ===============================
        return UserMessage(
            message_key="SYSTEM_ERROR",
            severity="ERROR",
            message="Hệ thống đang gặp sự cố. Vui lòng thử lại sau."
        )
