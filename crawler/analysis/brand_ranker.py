# Layer A

from db.db_connection import get_connection
import math


def rank_brands_by_category(category_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            b.BrandId,
            b.BrandName,
            a.AvgRating,
            a.PositiveRate,
            a.NegativeRate,
            s.TotalReviews
        FROM BrandAnalysisResult a
        JOIN BrandDataStatus s 
            ON a.BrandId = s.BrandId AND a.CategoryId = s.CategoryId
        JOIN Brand b 
            ON a.BrandId = b.BrandId
        WHERE a.CategoryId = ?
    """, category_id)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    max_reviews = max(r.TotalReviews for r in rows)

    ranked = []
    for r in rows:
        volume_score = math.log10(r.TotalReviews + 1) / math.log10(max_reviews + 1)

        score = (
            (r.AvgRating / 5.0) * 0.4
            + r.PositiveRate * 0.3
            - r.NegativeRate * 0.2
            + volume_score * 0.1
        )

        ranked.append({
            "brandId": r.BrandId,
            "brandName": r.BrandName,
            "categoryId": category_id,
            "score": round(score, 4),
            "metrics": {
                "avgRating": r.AvgRating,
                "positiveRate": r.PositiveRate,
                "negativeRate": r.NegativeRate,
                "totalReviews": r.TotalReviews
            }
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)

    # gán rank
    for i, item in enumerate(ranked):
        item["rank"] = i + 1

    return ranked
