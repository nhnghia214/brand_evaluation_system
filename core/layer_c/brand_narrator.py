# core/layer_c/brand_narrator.py

def narrate_brand_evaluation(
    brand: str,
    category: str,
    score: float,
    avg_rating: float | None,
    positive_rate: float | None,
    negative_rate: float | None,
    total_reviews: int | None
) -> str:
    parts = []

    # 1️⃣ MỞ ĐẦU – KỂ CHUYỆN
    parts.append(
        f"Khi nhìn vào bức tranh tổng thể, {brand} là một thương hiệu "
        f"để lại nhiều dấu ấn trong phạm vi {category}."
    )

    # 2️⃣ ĐÁNH GIÁ CHẤT LƯỢNG
    if score >= 8:
        parts.append(
            f"Thương hiệu này đạt điểm đánh giá tổng hợp {score:.2f}/10, "
            f"cho thấy chất lượng sản phẩm được người dùng đánh giá rất cao."
        )
    elif score >= 6:
        parts.append(
            f"Với điểm đánh giá {score:.2f}/10, {brand} thể hiện mức chất lượng ổn định, "
            f"phù hợp với số đông người tiêu dùng."
        )
    else:
        parts.append(
            f"Tuy nhiên, điểm đánh giá {score:.2f}/10 cho thấy {brand} "
            f"vẫn còn nhiều phản hồi trái chiều từ người dùng."
        )

    # 3️⃣ CẢM NHẬN NGƯỜI DÙNG
    if avg_rating is not None:
        parts.append(
            f"Xét ở mức chi tiết hơn, điểm đánh giá trung bình của các sản phẩm "
            f"thuộc thương hiệu này là {avg_rating:.2f}/5."
        )

    if positive_rate is not None and negative_rate is not None:
        pos_pct = positive_rate * 100
        neg_pct = negative_rate * 100
        
        if positive_rate >= 0.8:
            parts.append(
                f"Xét trên góc độ ngôn từ đánh giá, khoảng {pos_pct:.1f}% nội dung "
                f"thể hiện cảm xúc tích cực, trong khi chỉ {neg_pct:.1f}% mang sắc thái tiêu cực. "
                f"Điều này cho thấy người dùng có xu hướng đánh giá rất tốt về thương hiệu."
            )
        elif positive_rate >= 0.6:
            parts.append(
                f"Về mặt cảm xúc trong đánh giá, tỷ lệ ngôn từ tích cực chiếm khoảng {pos_pct:.1f}%, "
                f"cao hơn đáng kể so với {neg_pct:.1f}% ngôn từ tiêu cực. "
                f"Nhìn chung, trải nghiệm người dùng ở mức khá tích cực."
            )
        else:
            parts.append(
                f"Tuy nhiên, phân tích ngôn từ cho thấy chỉ khoảng {pos_pct:.1f}% đánh giá mang sắc thái tích cực, "
                f"trong khi tỷ lệ tiêu cực lên tới {neg_pct:.1f}%. "
                f"Điều này phản ánh sự phân hóa rõ rệt trong trải nghiệm người dùng."
            )

    # 4️⃣ ĐỘ TIN CẬY DỮ LIỆU
    if total_reviews is not None:
        if total_reviews >= 1000:
            parts.append(
                f"Kết luận này được rút ra từ {total_reviews} lượt đánh giá, "
                f"mang lại độ tin cậy rất cao."
            )
        elif total_reviews >= 100:
            parts.append(
                f"Dữ liệu dựa trên {total_reviews} lượt đánh giá, "
                f"đủ để phản ánh xu hướng chung của thị trường."
            )
        else:
            parts.append(
                f"Tuy vậy, số lượng đánh giá còn hạn chế ({total_reviews} lượt), "
                f"nên kết quả chỉ mang tính tham khảo."
            )

    return " ".join(parts)
