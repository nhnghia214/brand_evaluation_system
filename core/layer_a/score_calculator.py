"""
score_calculator.py

Layer A – Brand evaluation logic

Responsibility:
- Calculate composite brand score from analysis metrics
- Pure function, no DB access
"""

def calculate(avg_rating: float, positive_rate: float, total_reviews: int) -> float:
    rating_norm = avg_rating / 5.0
    review_confidence = min(total_reviews / 1000.0, 1.0)

    score = (
        0.5 * rating_norm +
        0.3 * positive_rate +
        0.2 * review_confidence
    )

    return round(score * 10, 2)  # 0–10

print(calculate(4.5, 0.8, 1200))  # kiểm tra output
