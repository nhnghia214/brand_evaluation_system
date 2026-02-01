# core/layer_b/analysis_service.py

import time
from datetime import datetime

from crawler.db.db_connection import get_connection
from core.layer_a.score_calculator import calculate
from core.layer_b.sentiment_token_analyzer import SentimentTokenAnalyzer


class AnalysisService:
    """
    Layer B – Brand analysis service (SELF-ORCHESTRATED)

    Responsibility:
    - Detect brand-category pairs that need re-analysis
    - Aggregate review data (single source of truth: Review table)
    - Compute heuristic scores
    - Update BrandAnalysisResult & BrandDataStatus
    """

    SLEEP_SECONDS = 60

    def run(self):
        print("[Analysis] Service started")

        while True:
            tasks = self._get_pending_analysis_tasks()

            if not tasks:
                time.sleep(self.SLEEP_SECONDS)
                continue

            for brand_id, category_id in tasks:
                try:
                    self._analyze_by_id(brand_id, category_id)
                except Exception as e:
                    print("[Analysis] Error:", e)

    # ===============================
    # FIND TASKS NEED ANALYSIS
    # (SOURCE OF TRUTH = REVIEW)
    # ===============================
    def _get_pending_analysis_tasks(self):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT
                p.BrandId,
                p.CategoryId
            FROM Review r
            JOIN Product p ON r.ProductId = p.ProductId
            LEFT JOIN BrandDataStatus s
              ON s.BrandId = p.BrandId
             AND s.CategoryId = p.CategoryId
            WHERE
                s.LastEvaluatedAt IS NULL
                OR r.CollectedAt > s.LastEvaluatedAt
        """)

        rows = cursor.fetchall()
        conn.close()

        return [(r.BrandId, r.CategoryId) for r in rows]

    # ===============================
    # RUN ANALYSIS FOR 1 PAIR
    # ===============================
    def _analyze_by_id(self, brand_id: int, category_id: int):
        print(f"[Analysis] Analyzing brand={brand_id}, category={category_id}")

        conn = get_connection()
        cursor = conn.cursor()

        # ==================================================
        # 1️⃣ LOAD REVIEW TEXT
        # ==================================================
        cursor.execute("""
            SELECT r.Comment
            FROM Review r
            JOIN Product p ON r.ProductId = p.ProductId
            WHERE p.BrandId = ? AND p.CategoryId = ?
            AND r.Comment IS NOT NULL
        """, (brand_id, category_id))

        review_texts = [r.Comment for r in cursor.fetchall()]

        if not review_texts:
            conn.close()
            return

        # ==================================================
        # 2️⃣ SENTIMENT TOKEN ANALYSIS
        # ==================================================
        analyzer = SentimentTokenAnalyzer()
        positive_tokens, negative_tokens = analyzer.analyze_reviews(review_texts)

        if positive_tokens + negative_tokens == 0:
            sentiment_ratio = 0.5
        else:
            sentiment_ratio = positive_tokens / (positive_tokens + negative_tokens)

        positive_rate = sentiment_ratio
        negative_rate = 1 - sentiment_ratio

        # ==================================================
        # 3️⃣ AGGREGATE NUMERIC METRICS
        # ==================================================
        cursor.execute("""
            SELECT
                COUNT(*) AS TotalReviews,
                MAX(r.ReviewTime) AS LatestReviewTime,
                AVG(CAST(r.Rating AS FLOAT)) AS AvgRating
            FROM Review r
            JOIN Product p ON r.ProductId = p.ProductId
            WHERE p.BrandId = ? AND p.CategoryId = ?
        """, (brand_id, category_id))

        agg = cursor.fetchone()
        if not agg or agg.TotalReviews == 0:
            conn.close()
            return

        total_reviews = agg.TotalReviews
        latest_review_time = agg.LatestReviewTime
        avg_rating = float(agg.AvgRating)

        data_freshness_days = (
            (datetime.now() - latest_review_time).days
            if latest_review_time else None
        )

        # ==================================================
        # 4️⃣ UPDATE BrandDataStatus
        # ==================================================
        cursor.execute("""
            IF EXISTS (
                SELECT 1 FROM BrandDataStatus
                WHERE BrandId = ? AND CategoryId = ?
            )
            UPDATE BrandDataStatus
            SET
                TotalReviews = ?,
                LatestReviewTime = ?,
                DataFreshnessDays = ?,
                LastEvaluatedAt = GETDATE()
            WHERE BrandId = ? AND CategoryId = ?
            ELSE
            INSERT INTO BrandDataStatus (
                BrandId, CategoryId,
                TotalReviews, LatestReviewTime,
                DataFreshnessDays, LastEvaluatedAt
            )
            VALUES (?, ?, ?, ?, ?, GETDATE())
        """, (
            brand_id, category_id,
            total_reviews, latest_review_time, data_freshness_days,
            brand_id, category_id,
            brand_id, category_id,
            total_reviews, latest_review_time, data_freshness_days
        ))

        # ==================================================
        # 5️⃣ COMPUTE SCORE
        # ==================================================
        score = calculate(
            avg_rating=avg_rating,
            sentiment_ratio=sentiment_ratio,
            total_reviews=total_reviews
        )

        # ==================================================
        # 6️⃣ UPSERT BrandAnalysisResult
        # ==================================================
        cursor.execute("""
            IF EXISTS (
                SELECT 1 FROM BrandAnalysisResult
                WHERE BrandId = ? AND CategoryId = ?
            )
            UPDATE BrandAnalysisResult
            SET
                AvgRating = ?,
                PositiveRate = ?,
                NegativeRate = ?,
                Score = ?,
                GeneratedAt = GETDATE()
            WHERE BrandId = ? AND CategoryId = ?
            ELSE
            INSERT INTO BrandAnalysisResult (
                BrandId, CategoryId,
                AvgRating, PositiveRate, NegativeRate,
                Score, GeneratedAt
            )
            VALUES (?, ?, ?, ?, ?, ?, GETDATE())
        """, (
            brand_id, category_id,
            avg_rating, positive_rate, negative_rate, score,
            brand_id, category_id,
            brand_id, category_id,
            avg_rating, positive_rate, negative_rate, score
        ))

        conn.commit()
        conn.close()

        print(
            f"[Analysis] Done brand={brand_id}, category={category_id} | "
            f"sentiment={sentiment_ratio:.2f}, score={score}"
        )



