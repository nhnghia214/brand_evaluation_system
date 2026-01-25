# core/layer_b/brand_analyzer.py

"""
Layer B – Brand data analysis

Responsibility:
- Aggregate raw review data
- Compute analysis metrics
- Persist FACTS to database
"""

from datetime import datetime
from crawler.db.db_connection import get_connection


def analyze_brand_category(brand_id: int, category_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    # 1️⃣ Fetch raw reviews
    cursor.execute("""
        SELECT r.Rating, r.ReviewTime
        FROM Review r
        JOIN Product p ON r.ProductId = p.ProductId
        WHERE p.BrandId = ? AND p.CategoryId = ?
    """, (brand_id, category_id))

    rows = cursor.fetchall()
    if not rows:
        print(f"[SKIP] No review for Brand {brand_id} - Category {category_id}")
        return

    total_reviews = len(rows)
    positive = sum(1 for r in rows if r.Rating >= 4)
    negative = sum(1 for r in rows if r.Rating <= 2)

    avg_rating = sum(r.Rating for r in rows) / total_reviews
    positive_rate = round(positive / total_reviews, 4)
    negative_rate = round(negative / total_reviews, 4)

    latest_review_time = max(r.ReviewTime for r in rows)
    now = datetime.now()

    # 2️⃣ Persist BrandDataStatus (FACTS ONLY)
    cursor.execute("""
        MERGE BrandDataStatus AS target
        USING (SELECT ? AS BrandId, ? AS CategoryId) AS src
        ON target.BrandId = src.BrandId AND target.CategoryId = src.CategoryId
        WHEN MATCHED THEN
            UPDATE SET
                TotalReviews = ?,
                LatestReviewTime = ?,
                LastEvaluatedAt = ?
        WHEN NOT MATCHED THEN
            INSERT VALUES (?, ?, ?, ?, NULL, ?);
    """, (
        brand_id, category_id,
        total_reviews, latest_review_time, now,
        brand_id, category_id,
        total_reviews, latest_review_time, now
    ))

    # 3️⃣ Persist BrandAnalysisResult
    cursor.execute("""
        MERGE BrandAnalysisResult AS target
        USING (SELECT ? AS BrandId, ? AS CategoryId) AS src
        ON target.BrandId = src.BrandId AND target.CategoryId = src.CategoryId
        WHEN MATCHED THEN
            UPDATE SET
                AvgRating = ?,
                PositiveRate = ?,
                NegativeRate = ?,
                Summary = ?,
                GeneratedAt = ?
        WHEN NOT MATCHED THEN
            INSERT VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (
        brand_id, category_id,
        avg_rating, positive_rate, negative_rate,
        "Auto-generated brand analysis",
        now,
        brand_id, category_id,
        avg_rating, positive_rate, negative_rate,
        "Auto-generated brand analysis",
        now
    ))

    conn.commit()
    conn.close()

    print(f"[OK] Layer B analyzed Brand {brand_id} - Category {category_id}")
