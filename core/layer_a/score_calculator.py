"""
score_calculator.py

Layer A – Brand evaluation logic

Responsibility:
- Calculate composite brand score
- Pure function (NO DB)
"""

def calculate(
    avg_rating: float,
    sentiment_ratio: float,
    total_reviews: int
) -> float:
    """
    avg_rating: 0–5
    sentiment_ratio: 0–1 (từ sentiment token analyzer)
    total_reviews: số review
    """

    rating_norm = avg_rating / 5.0
    review_confidence = min(total_reviews / 1000.0, 1.0)

    score = (
        0.45 * rating_norm +
        0.35 * sentiment_ratio +
        0.20 * review_confidence
    )

    return round(score * 10, 2)  # 0–10
