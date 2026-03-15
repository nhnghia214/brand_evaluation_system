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
    # ALIAS FOR BACKWARD COMPATIBILITY
    # ===============================
    def _analyze_single(self, brand_id: int, category_id: int):
        return self._analyze_by_id(brand_id, category_id)

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
        # 1️⃣ LOAD OLD DATA & NEW REVIEW TEXT (INCREMENTAL UPDATE)
        # ==================================================
        # Lấy Trạng thái cũ (Điểm cũ và Tổng số review cũ)
        cursor.execute("""
            SELECT b.PositiveRate, s.TotalReviews, s.LastEvaluatedAt
            FROM BrandAnalysisResult b
            JOIN BrandDataStatus s ON b.BrandId = s.BrandId AND b.CategoryId = s.CategoryId
            WHERE b.BrandId = ? AND b.CategoryId = ?
        """, (brand_id, category_id))
        old_data = cursor.fetchone()

        old_positive_rate = old_data.PositiveRate if old_data else 0.0
        old_total_evaluated = old_data.TotalReviews if old_data else 0
        last_evaluated_at = old_data.LastEvaluatedAt if old_data else None

        # Chỉ lấy NHỮNG BÌNH LUẬN MỚI chưa từng được phân tích
        if last_evaluated_at:
            cursor.execute("""
                SELECT r.Comment FROM Review r
                JOIN Product p ON r.ProductId = p.ProductId
                WHERE p.BrandId = ? AND p.CategoryId = ?
                AND r.Comment IS NOT NULL
                AND r.CollectedAt > ? 
            """, (brand_id, category_id, last_evaluated_at))
            print(f"  -> [Incremental] Đã có dữ liệu cũ. Lấy các review mới sau ngày {last_evaluated_at}")
        else:
            cursor.execute("""
                SELECT r.Comment FROM Review r
                JOIN Product p ON r.ProductId = p.ProductId
                WHERE p.BrandId = ? AND p.CategoryId = ?
                AND r.Comment IS NOT NULL
            """, (brand_id, category_id))
            print("  -> [First Run] Phân tích lần đầu toàn bộ review.")

        new_reviews = [r.Comment for r in cursor.fetchall()]

        if not new_reviews:
            print("  -> Không có bình luận mới nào cần phân tích. Bỏ qua.")
            conn.close()
            return

        # ==================================================
        # 2️⃣ SENTIMENT TOKEN ANALYSIS (MULTI-AGENT CHO DATA MỚI)
        # ==================================================
        from core.layer_b.sentiment_token_analyzer import SentimentTokenAnalyzer
        from core.layer_b.sentiment_agents.gpt_agent import GPTSentimentAgent
        from core.layer_b.sentiment_agents.locked_groq_agent import LockedGroqAgent
        from core.layer_b.sentiment_agents.llama_agent import LlamaSentimentAgent
        from core.layer_b.sentiment_agents.aggregator import WeightedSentimentAggregator

        vader_analyzer = SentimentTokenAnalyzer()
        agents = [GPTSentimentAgent(), LockedGroqAgent(), LlamaSentimentAgent()]
        weights = [0.25, 0.25, 0.25, 0.25]
        aggregator = WeightedSentimentAggregator(agents, weights)

        new_positive_count = 0 
        new_valid_comments = 0

        print(f"  -> Đang dùng Multi-Agent phân tích {len(new_reviews)} bình luận MỚI...")

        for text in new_reviews:
            if not text:
                continue
            
            # 1. VADER
            pos, neg = vader_analyzer.analyze_reviews([text])
            vader_ratio = 0.5 if (pos + neg) == 0 else pos / (pos + neg)
            vader_score_minus1_to_1 = (vader_ratio * 2) - 1

            # 2. LLMs Multi-Agent
            try:
                score_ratio = aggregator.aggregate(text, vader_score_minus1_to_1)
            except Exception as e:
                print(f"[Analysis] Lỗi Agent, bỏ qua: {e}")
                score_ratio = 0.5 

            if score_ratio >= 0.6:
                new_positive_count += 1
                
            new_valid_comments += 1
            print(f"    + Đã xử lý {new_valid_comments}/{len(new_reviews)}")
            time.sleep(2) # Chống Rate Limit

        # ==================================================
        # TÍNH TOÁN CÔNG THỨC HÒA TRỘN (INCREMENTAL MATH)
        # ==================================================
        if old_total_evaluated == 0:
            # Nếu là lần chạy đầu tiên
            sentiment_ratio = new_positive_count / new_valid_comments if new_valid_comments > 0 else 0.5
        else:
            # THUẬT TOÁN HÒA TRỘN ĐIỂM SỐ
            old_positive_count = old_positive_rate * old_total_evaluated
            final_positive_count = old_positive_count + new_positive_count
            final_total_comments = old_total_evaluated + new_valid_comments
            
            sentiment_ratio = final_positive_count / final_total_comments

        positive_rate = sentiment_ratio
        negative_rate = 1 - sentiment_ratio
        
        print(f"  -> [Toán học] Trộn điểm: Cũ({old_total_evaluated}) + Mới({new_valid_comments}) -> Tỷ lệ mới: {positive_rate:.4f}")

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



