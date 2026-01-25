# core/layer_c/brand_narrator.py

def narrate_brand_evaluation(
    brand: str,
    category: str,
    score: float,
    avg_rating: float,
    positive_rate: float,
    negative_rate: float,
    total_reviews: int
) -> str:
    parts = []

    # 1️⃣ Đánh giá tổng quan
    if score >= 8:
        parts.append(
            f"{brand} là một thương hiệu có chất lượng tốt trong danh mục {category}, "
            f"với điểm đánh giá tổng hợp đạt {score:.2f}/10."
        )
    elif score >= 6:
        parts.append(
            f"{brand} có mức đánh giá khá trong danh mục {category}, "
            f"với điểm tổng hợp {score:.2f}/10."
        )
    else:
        parts.append(
            f"{brand} hiện có mức đánh giá chưa cao trong danh mục {category}, "
            f"với điểm tổng hợp {score:.2f}/10."
        )

    # 2️⃣ Phân tích cảm nhận người dùng
    parts.append(
        f"Điểm đánh giá trung bình của các sản phẩm thuộc thương hiệu này là {avg_rating:.2f}/5."
    )

    if positive_rate >= 0.8:
        parts.append(
            f"Phần lớn người dùng có trải nghiệm tích cực, với {positive_rate*100:.1f}% "
            f"đánh giá ở mức 4–5 sao."
        )
    elif positive_rate >= 0.6:
        parts.append(
            f"Tỷ lệ đánh giá tích cực đạt {positive_rate*100:.1f}%, cho thấy chất lượng nhìn chung ổn định."
        )
    else:
        parts.append(
            f"Tỷ lệ đánh giá tích cực chỉ đạt {positive_rate*100:.1f}%, "
            f"cho thấy trải nghiệm người dùng còn chưa đồng đều."
        )

    # 3️⃣ Độ tin cậy dữ liệu
    if total_reviews >= 100:
        parts.append(
            f"Kết quả này được tổng hợp từ {total_reviews} lượt đánh giá, "
            f"mang lại độ tin cậy cao."
        )
    elif total_reviews >= 30:
        parts.append(
            f"Dữ liệu dựa trên {total_reviews} lượt đánh giá, "
            f"đủ để phản ánh xu hướng chung."
        )
    else:
        parts.append(
            f"Tuy nhiên, số lượng đánh giá còn hạn chế ({total_reviews} lượt), "
            f"nên kết quả chỉ mang tính tham khảo."
        )

    return " ".join(parts)
