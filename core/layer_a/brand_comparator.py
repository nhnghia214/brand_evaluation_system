# so sánh các thương hiệu cùng danh mục
from crawler.db.db_connection import get_connection
import math


def _calc_score(r, max_reviews):
    volume_score = math.log10(r.TotalReviews + 1) / math.log10(max_reviews + 1)
    return (
        (r.AvgRating / 5.0) * 0.4
        + r.PositiveRate * 0.3
        - r.NegativeRate * 0.2
        + volume_score * 0.1
    )


def compare_brands(category_id: int, brand_id_a: int, brand_id_b: int):
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
          AND a.BrandId IN (?, ?)
    """, category_id, brand_id_a, brand_id_b)

    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 2:
        return None

    max_reviews = max(r.TotalReviews for r in rows)

    data = {}
    for r in rows:
        data[r.BrandId] = {
            "brandId": r.BrandId,
            "brandName": r.BrandName,
            "avgRating": r.AvgRating,
            "positiveRate": r.PositiveRate,
            "negativeRate": r.NegativeRate,
            "totalReviews": r.TotalReviews,
            "score": round(_calc_score(r, max_reviews), 4)
        }

    A = data[brand_id_a]
    B = data[brand_id_b]

    def cmp(higher_is_better=True, a=A, b=B, key=None):
        if higher_is_better:
            return "A higher" if a[key] > b[key] else "B higher"
        else:
            return "A lower" if a[key] < b[key] else "B lower"

    comparison = {
        "avgRating": cmp(True, key="avgRating"),
        "positiveRate": cmp(True, key="positiveRate"),
        "negativeRate": cmp(False, key="negativeRate"),
        "totalReviews": cmp(True, key="totalReviews"),
    }

    winner = A["brandName"] if A["score"] >= B["score"] else B["brandName"]

    return {
        "categoryId": category_id,
        "brandA": A,
        "brandB": B,
        "comparison": comparison,
        "winner": winner
    }
