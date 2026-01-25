# core/layer_c/templates.py

READY_TEMPLATE = (
    "Thương hiệu {brand} trong danh mục {category} "
    "đang có mức đánh giá tốt với điểm tổng hợp {score}/10."
)

DATA_UPDATING_TEMPLATE = (
    "Dữ liệu của thương hiệu {brand} trong danh mục {category} "
    "đang được cập nhật. Vui lòng quay lại sau."
)

DATA_INSUFFICIENT_TEMPLATE = (
    "Hiện tại chưa có đủ dữ liệu để đánh giá "
    "thương hiệu {brand} trong danh mục {category}."
)

SYSTEM_ERROR_TEMPLATE = (
    "Hệ thống đang gặp sự cố khi xử lý yêu cầu. "
    "Vui lòng thử lại sau."
)
