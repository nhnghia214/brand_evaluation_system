# Layer B – phân tích

# analysis/brand_analyzer.py

from datetime import datetime
from db.db_connection import get_connection


def analyze_brand_category(brand_id: int, category_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    # 1️⃣ Lấy review theo brand + category
    cursor.execute("""
        SELECT r.Rating, r.ReviewTime
        FROM Review r
        JOIN Product p ON r.ProductId = p.ProductId
        WHERE p.BrandId = ? AND p.CategoryId = ?
    """, brand_id, category_id)

    rows = cursor.fetchall()
    if not rows:
        print(f"[SKIP] No review for Brand {brand_id} - Category {category_id}")
        return

    total = len(rows)
    positive = sum(1 for r in rows if r.Rating >= 4)
    negative = sum(1 for r in rows if r.Rating <= 2)

    avg_rating = sum(r.Rating for r in rows) / total
    positive_rate = round(positive / total, 4)
    negative_rate = round(negative / total, 4)

    latest_review_time = max(r.ReviewTime for r in rows)
    freshness_days = (datetime.now() - latest_review_time).days

    now = datetime.now()

    # 2️⃣ BrandDataStatus
    cursor.execute("""
        MERGE BrandDataStatus AS target
        USING (SELECT ? AS BrandId, ? AS CategoryId) AS src
        ON target.BrandId = src.BrandId AND target.CategoryId = src.CategoryId
        WHEN MATCHED THEN
            UPDATE SET
                TotalReviews = ?,
                LatestReviewTime = ?,
                DataFreshnessDays = ?,
                LastEvaluatedAt = ?
        WHEN NOT MATCHED THEN
            INSERT VALUES (?, ?, ?, ?, ?, ?);
    """,
        brand_id, category_id,
        total, latest_review_time, freshness_days, now,
        brand_id, category_id,
        total, latest_review_time, freshness_days, now
    )

    # 3️⃣ BrandAnalysisResult
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
    """,
        brand_id, category_id,
        avg_rating, positive_rate, negative_rate,
        "Auto-generated brand analysis",
        now,
        brand_id, category_id,
        avg_rating, positive_rate, negative_rate,
        "Auto-generated brand analysis",
        now
    )

    conn.commit()
    conn.close()

    print(f"[OK] Analyzed Brand {brand_id} - Category {category_id}")
