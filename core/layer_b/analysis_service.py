# core/layer_b/analysis_service.py

import time
from datetime import datetime, timedelta

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
    QUOTA_LOCKED_UNTIL = None  # Biến lưu trữ "Thẻ cấm túc" dùng chung cho toàn hệ thống

    def run(self):
        print("[Analysis] Service started")

        while True:
            # ==========================================================
            # 0. NẾU ĐANG BỊ CẤM TÚC -> NGỦ 60 GIÂY RỒI KIỂM TRA LẠI
            # ==========================================================
            if self.__class__.QUOTA_LOCKED_UNTIL and datetime.now() < self.__class__.QUOTA_LOCKED_UNTIL:
                # In 1 dòng duy nhất mỗi phút cho đỡ rác Terminal
                print(f"💤 [Analysis] Đang ngủ đông đến {self.__class__.QUOTA_LOCKED_UNTIL.strftime('%H:%M:%S')}. Crawler vẫn đang tự do hoạt động...")
                time.sleep(self.SLEEP_SECONDS)  # Ngủ 60 giây
                continue
                
            # Xóa cờ khóa nếu đã hết giờ phạt
            if self.__class__.QUOTA_LOCKED_UNTIL and datetime.now() >= self.__class__.QUOTA_LOCKED_UNTIL:
                self.__class__.QUOTA_LOCKED_UNTIL = None

            # ==========================================================
            # 1. NẾU KHÔNG BỊ KHÓA -> ĐI TÌM VIỆC LÀM
            # ==========================================================
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

        # THAY ĐỔI LỚN: Chỉ cần tìm xem có bất kỳ Review nào có IsAnalyzed = 0 là hốt Brand đó ra làm
        cursor.execute("""
            SELECT DISTINCT
                p.BrandId,
                p.CategoryId
            FROM Review r
            JOIN Product p ON r.ProductId = p.ProductId
            WHERE r.IsAnalyzed = 0
        """)

        rows = cursor.fetchall()
        conn.close()

        return [(r.BrandId, r.CategoryId) for r in rows]

    # ===============================
    # RUN ANALYSIS FOR 1 PAIR
    # ===============================
    def _analyze_by_id(self, brand_id: int, category_id: int):
        # 0. KIỂM TRA LỆNH CẤM TÚC
        if self.__class__.QUOTA_LOCKED_UNTIL and datetime.now() < self.__class__.QUOTA_LOCKED_UNTIL:
            return

        print(f"[Analysis] Analyzing brand={brand_id}, category={category_id}")

        conn = get_connection()
        cursor = conn.cursor()

        # 1. LOAD OLD DATA (Chỉ lấy điểm và tổng số câu đã chốt trong DB)
        cursor.execute("""
            SELECT b.PositiveRate, s.TotalReviews
            FROM BrandAnalysisResult b
            JOIN BrandDataStatus s ON b.BrandId = s.BrandId AND b.CategoryId = s.CategoryId
            WHERE b.BrandId = ? AND b.CategoryId = ?
        """, (brand_id, category_id))
        old_data = cursor.fetchone()

        old_positive_rate = old_data[0] if old_data else 0.0
        old_total_evaluated = old_data[1] if old_data else 0

        # TÌM NHỮNG BÌNH LUẬN CHƯA PHÂN TÍCH (IsAnalyzed = 0)
        cursor.execute("""
            SELECT r.ReviewId, r.Comment FROM Review r
            JOIN Product p ON r.ProductId = p.ProductId
            WHERE p.BrandId = ? AND p.CategoryId = ?
            AND r.Comment IS NOT NULL
            AND r.IsAnalyzed = 0
        """, (brand_id, category_id))
        
        new_reviews_data = cursor.fetchall()
        if not new_reviews_data:
            print("  -> Không có bình luận mới nào cần phân tích. Bỏ qua.")
            conn.close()
            return

        print(f"  -> Tìm thấy {len(new_reviews_data)} bình luận MỚI chưa phân tích.")

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
        processed_ids = []

        for row in new_reviews_data:
            review_id, text = row.ReviewId, row.Comment
            
            # 1. VADER
            pos, neg = vader_analyzer.analyze_reviews([text])
            vader_ratio = 0.5 if (pos + neg) == 0 else pos / (pos + neg)
            vader_score_minus1_to_1 = (vader_ratio * 2) - 1

            try:
                score_ratio = aggregator.aggregate(text, vader_score_minus1_to_1)
            except Exception as e:
                if "QUOTA_EXCEEDED" in str(e) or "RATE_LIMIT" in str(e).upper():
                    print(f"\n🚨 [Analysis] HẾT REQUEST! Đang khóa 12h. Lưu lại {new_valid_comments} câu đã xong...")
                    self.__class__.QUOTA_LOCKED_UNTIL = datetime.now() + timedelta(hours=12)
                    break 
                score_ratio = 0.5
            
            if score_ratio >= 0.6: 
                new_positive_count += 1
            new_valid_comments += 1
            processed_ids.append(review_id)
            
            print(f"    + Đã xử lý {new_valid_comments}/{len(new_reviews_data)}")
            time.sleep(2.5)

        if not processed_ids:
            conn.close()
            return

        # ==================================================
        # CHỐT SỔ AN TOÀN
        # ==================================================
        # 1. Đánh dấu đã xong trong bảng Review
        placeholders = ','.join(['?'] * len(processed_ids))
        cursor.execute(f"UPDATE Review SET IsAnalyzed = 1 WHERE ReviewId IN ({placeholders})", processed_ids)

        # 2. Tính toán cộng dồn (Incremental Math)
        old_pos_total = old_positive_rate * old_total_evaluated
        final_pos = old_pos_total + new_positive_count
        final_total = old_total_evaluated + new_valid_comments
        sentiment_ratio = final_pos / final_total if final_total > 0 else 0.5

        # 3. Lấy thông tin tổng hợp mới nhất
        cursor.execute("""
            SELECT COUNT(*) AS Total, MAX(r.ReviewTime) AS MaxTime, AVG(CAST(r.Rating AS FLOAT)) AS AvgR
            FROM Review r JOIN Product p ON r.ProductId = p.ProductId
            WHERE p.BrandId = ? AND p.CategoryId = ? AND r.IsAnalyzed = 1
        """, (brand_id, category_id))
        agg = cursor.fetchone()
        
        total_reviews = agg[0]
        avg_rating = float(agg[2] or 0)
        latest_time = agg[1]
        freshness = (datetime.now() - latest_time).days if latest_time else None

        # 4. Update Status & Result (Sửa lỗi IF @@ROWCOUNT)
        score = calculate(avg_rating=avg_rating, sentiment_ratio=sentiment_ratio, total_reviews=total_reviews)
        
        # Update Status
        cursor.execute("""
            UPDATE BrandDataStatus 
            SET TotalReviews=?, LatestReviewTime=?, DataFreshnessDays=?, LastEvaluatedAt=GETDATE()
            WHERE BrandId=? AND CategoryId=?
            IF @@ROWCOUNT=0 
            INSERT INTO BrandDataStatus (BrandId, CategoryId, TotalReviews, LatestReviewTime, DataFreshnessDays, LastEvaluatedAt)
            VALUES (?, ?, ?, ?, ?, GETDATE())
        """, (total_reviews, latest_time, freshness, brand_id, category_id,
              brand_id, category_id, total_reviews, latest_time, freshness))

        # Update Result
        cursor.execute("""
            UPDATE BrandAnalysisResult 
            SET AvgRating=?, PositiveRate=?, NegativeRate=?, Score=?, GeneratedAt=GETDATE()
            WHERE BrandId=? AND CategoryId=?
            IF @@ROWCOUNT=0 
            INSERT INTO BrandAnalysisResult (BrandId, CategoryId, AvgRating, PositiveRate, NegativeRate, Score, GeneratedAt)
            VALUES (?, ?, ?, ?, ?, ?, GETDATE())
        """, (avg_rating, sentiment_ratio, 1-sentiment_ratio, score, brand_id, category_id,
              brand_id, category_id, avg_rating, sentiment_ratio, 1-sentiment_ratio, score))

        conn.commit()
        conn.close()
        print(f"✅ Đã chốt sổ an toàn {new_valid_comments} câu cho brand {brand_id}.")