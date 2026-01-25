# core/layer_c/brand_presenter.py

"""
Layer C – Brand presentation

Responsibility:
- Convert structured evaluation result into user-facing text
- No business logic
- No database access
"""

from typing import Optional

from core.dto.user_message import UserMessage
from core.layer_c import templates


class BrandPresenter:

    @staticmethod
    def present(
        user_message: UserMessage,
        brand_name: str,
        category_name: Optional[str],
        score: Optional[float] = None
    ) -> str:
        category = category_name or "tất cả danh mục"

        if user_message.message_key == "READY":
            return templates.READY_TEMPLATE.format(
                brand=brand_name,
                category=category,
                score=score if score is not None else "N/A"
            )

        if user_message.message_key in ("DATA_UPDATING", "DATA_PENDING"):
            return templates.DATA_UPDATING_TEMPLATE.format(
                brand=brand_name,
                category=category
            )

        if user_message.message_key == "DATA_INSUFFICIENT":
            return templates.DATA_INSUFFICIENT_TEMPLATE.format(
                brand=brand_name,
                category=category
            )

        return templates.SYSTEM_ERROR_TEMPLATE
