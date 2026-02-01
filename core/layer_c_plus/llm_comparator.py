from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()


def compare_brands_with_llm(
    brand_summaries: list[dict],
    trend_info: dict,
    question: str
) -> str:

    content = "SO SÁNH TRỰC TIẾP (DỮ LIỆU THỐNG KÊ):\n\n"

    for b in brand_summaries:
        content += (
            f"- {b['brand']}: "
            f"Score {b['score']}, "
            f"Tổng đánh giá {b['total_reviews']}\n"
        )

    content += "\nXU HƯỚNG PHÁT TRIỂN:\n\n"
    for brand, info in trend_info.items():
        content += (
            f"- {brand}: "
            f"{info['category_count']} danh mục, "
            f"{info['total_reviews']} lượt đánh giá\n"
        )

    content += f"""
Câu hỏi:
"{question}"

Yêu cầu:
- Trả lời tiếng Việt
- Tối đa 180 từ
- Chia đúng 3 phần:

[SO SÁNH NHANH]
[KẾT LUẬN]
[XU HƯỚNG]

Không markdown.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Bạn là trợ lý tư vấn so sánh thương hiệu."},
            {"role": "user", "content": content}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content.strip()
