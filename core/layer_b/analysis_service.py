import time
import asyncio
from datetime import datetime, timedelta
import os
import csv

from crawler.db.db_connection import get_connection
from core.layer_a.score_calculator import calculate

# Import các Agent theo kiến trúc Dây chuyền mới
from core.layer_b.sentiment_agents.cleaner_agent import CleanerAgent
from core.layer_b.sentiment_agents.worker_agents import WorkerAgent
from core.layer_b.sentiment_agents.referee_agent import RefereeAgent
from core.layer_b.sentiment_agents.aggregator import SentimentPipelineOrchestrator


class AnalysisService:
    """
    Layer B – Brand analysis service (SELF-ORCHESTRATED)
    """

    SLEEP_SECONDS = 60
    QUOTA_LOCKED_UNTIL = None  

    def run(self):
        print("[Analysis] Service started")

        while True:
            # 0. NẾU ĐANG BỊ CẤM TÚC
            if self.__class__.QUOTA_LOCKED_UNTIL and datetime.now() < self.__class__.QUOTA_LOCKED_UNTIL:
                print(f"💤 [Analysis] Đang ngủ đông đến {self.__class__.QUOTA_LOCKED_UNTIL.strftime('%H:%M:%S')}. Crawler vẫn đang tự do hoạt động...")
                time.sleep(self.SLEEP_SECONDS)  
                continue
                
            if self.__class__.QUOTA_LOCKED_UNTIL and datetime.now() >= self.__class__.QUOTA_LOCKED_UNTIL:
                self.__class__.QUOTA_LOCKED_UNTIL = None

            # 1. ĐI TÌM VIỆC LÀM
            tasks = self._get_pending_analysis_tasks()

            if not tasks:
                time.sleep(self.SLEEP_SECONDS)
                continue

            for brand_id, category_id in tasks:
                try:
                    self._analyze_by_id(brand_id, category_id)
                except Exception as e:
                    print("[Analysis] Error:", e)
                    
    def _analyze_single(self, brand_id: int, category_id: int):
        return self._analyze_by_id(brand_id, category_id)

    def _get_pending_analysis_tasks(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT TOP 1 
                p.BrandId,
                p.CategoryId
            FROM Review r
            JOIN Product p ON r.ProductId = p.ProductId
            WHERE r.IsAnalyzed = 0
            ORDER BY p.BrandId ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [(r.BrandId, r.CategoryId) for r in rows]

    def _analyze_by_id(self, brand_id: int, category_id: int):
        if self.__class__.QUOTA_LOCKED_UNTIL and datetime.now() < self.__class__.QUOTA_LOCKED_UNTIL:
            return

        print(f"[Analysis] Analyzing brand={brand_id}, category={category_id}")

        conn = get_connection()
        cursor = conn.cursor()

        # 1. LOAD OLD DATA
        cursor.execute("""
            SELECT b.PositiveRate, s.TotalReviews
            FROM BrandAnalysisResult b
            JOIN BrandDataStatus s ON b.BrandId = s.BrandId AND b.CategoryId = s.CategoryId
            WHERE b.BrandId = ? AND b.CategoryId = ?
        """, (brand_id, category_id))
        old_data = cursor.fetchone()

        old_positive_rate = old_data[0] if old_data else 0.0
        old_total_evaluated = old_data[1] if old_data else 0

        # 2. TÌM NHỮNG BÌNH LUẬN CHƯA PHÂN TÍCH (LẤY TOP 25 THEO LÔ)
        cursor.execute("""
            SELECT TOP 25 r.ReviewId, r.Comment FROM Review r
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

        print(f"  -> Bốc lô {len(new_reviews_data)} bình luận MỚI để xử lý...")

        raw_batch = []
        processed_ids_for_empty = []

        for row in new_reviews_data:
            review_id, text = row.ReviewId, row.Comment

            # Lọc dữ liệu rỗng ngay tại Python để đỡ tốn API
            if not text or text.strip() == "":
                processed_ids_for_empty.append(review_id)
                continue
            
            raw_batch.append({"id": review_id, "text": text})

        # ==========================================================
        # 3. KHỞI TẠO DÂY CHUYỀN VỚI API KEYS TỪ FILE .ENV
        # ==========================================================
        # Đọc mảng 3 keys Groq từ config
        groq_keys_str = os.getenv("GROQ_API_KEYS", "")
        groq_keys = [k.strip() for k in groq_keys_str.split(",") if k.strip()]
        
        # Nếu không đủ 3 keys thì lấy key đầu tiên đắp vào cho khỏi lỗi
        key1 = groq_keys[0] if len(groq_keys) > 0 else os.getenv("GROQ_API_KEY")
        key2 = groq_keys[1] if len(groq_keys) > 1 else key1
        key3 = groq_keys[2] if len(groq_keys) > 2 else key1
        openai_key = os.getenv("OPENAI_API_KEY")

        cleaner = CleanerAgent(api_key=key1)
        workers = [
            WorkerAgent(agent_name="Worker_1_Llama8B", api_key=key1, model_name="llama-3.1-8b-instant"),
            WorkerAgent(agent_name="Worker_2_Llama70B", api_key=key2, model_name="llama-3.3-70b-versatile"),
            WorkerAgent(agent_name="Worker_3_Llama8B_Backup", api_key=key3, model_name="llama-3.1-8b-instant")
        ]
        referee = RefereeAgent(api_key=openai_key)
        
        orchestrator = SentimentPipelineOrchestrator(cleaner, workers, referee)

        # ==========================================================
        # 4. CHẠY PIPELINE (ASYNC)
        # ==========================================================
        processed_batch = []
        if raw_batch:
            print("  -> Bắt đầu chạy Dây chuyền Đa tác tử...")
            processed_batch = asyncio.run(orchestrator.run_pipeline(raw_batch))

        # ==========================================================
        # 5. XỬ LÝ LƯU AN TOÀN & CHẶN LỖI LỌT LƯỚI
        # ==========================================================
        # KIỂM TRA LỖI TOÀN CỤC NGAY LẬP TỨC: Nếu câu đầu bị lỗi -> Cả lô lỗi -> Hủy!
        if processed_batch and processed_batch[0].get("status") == "api_error":
            print(f"\n🚨 [Analysis] DÂY CHUYỀN BÁO LỖI API! Đang khóa 12h...")
            self.__class__.QUOTA_LOCKED_UNTIL = datetime.now() + timedelta(hours=12)
            # Dọn sạch mảng này để vòng lặp bên dưới không chạy, không lưu bậy bạ
            processed_batch = [] 
            
        successful_ids = processed_ids_for_empty.copy()
        new_positive_count = 0 
        new_valid_comments = 0

        for item in processed_batch:
            # Ghi nhận ID đã được xử lý (thành công)
            successful_ids.append(item["id"])
            
            # Nếu câu này là rác/spam, Cleaner loại bỏ (is_valid = False)
            if not item.get("is_valid", True):
                continue
                
            new_valid_comments += 1
            if item.get("final_score_0_to_1", 0.5) >= 0.6: 
                new_positive_count += 1

        if not successful_ids:
            print("  -> Không có câu nào xử lý thành công trong lô này. Dừng lại.")
            conn.close()
            return

        # ==================================================
        # 6. CHỐT SỔ AN TOÀN VÀO DATABASE
        # ==================================================
        placeholders = ','.join(['?'] * len(successful_ids))
        cursor.execute(f"UPDATE Review SET IsAnalyzed = 1 WHERE ReviewId IN ({placeholders})", successful_ids)

        old_pos_total = old_positive_rate * old_total_evaluated
        final_pos = old_pos_total + new_positive_count
        final_total = old_total_evaluated + new_valid_comments
        sentiment_ratio = final_pos / final_total if final_total > 0 else 0.5

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

        score = calculate(avg_rating=avg_rating, sentiment_ratio=sentiment_ratio, total_reviews=total_reviews)
        
        cursor.execute("""
            UPDATE BrandDataStatus 
            SET TotalReviews=?, LatestReviewTime=?, DataFreshnessDays=?, LastEvaluatedAt=GETDATE()
            WHERE BrandId=? AND CategoryId=?
            IF @@ROWCOUNT=0 
            INSERT INTO BrandDataStatus (BrandId, CategoryId, TotalReviews, LatestReviewTime, DataFreshnessDays, LastEvaluatedAt)
            VALUES (?, ?, ?, ?, ?, GETDATE())
        """, (total_reviews, latest_time, freshness, brand_id, category_id,
              brand_id, category_id, total_reviews, latest_time, freshness))

        cursor.execute("""
            UPDATE BrandAnalysisResult 
            SET AvgRating=?, PositiveRate=?, NegativeRate=?, Score=?, GeneratedAt=GETDATE()
            WHERE BrandId=? AND CategoryId=?
            IF @@ROWCOUNT=0 
            INSERT INTO BrandAnalysisResult (BrandId, CategoryId, AvgRating, PositiveRate, NegativeRate, Score, GeneratedAt)
            VALUES (?, ?, ?, ?, ?, ?, GETDATE())
        """, (avg_rating, sentiment_ratio, 1-sentiment_ratio, score, brand_id, category_id,
              brand_id, category_id, avg_rating, sentiment_ratio, 1-sentiment_ratio, score))
        
        # ==================================================
        # 7. XUẤT CSV CHO CASE STUDY (CHỈ CHO THƯƠNG HIỆU COLORKEY - ID: 13)
        # ==================================================
        if brand_id == 13 and processed_batch:
            csv_file = 'colorkey_llm_comparison_log.csv'
            file_exists = os.path.isfile(csv_file)
            
            with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Viết Header nếu file chưa tồn tại
                if not file_exists:
                    writer.writerow(['ReviewId', 'Is_Valid', 'Is_Seeding', 'Worker1_Llama8B', 'Worker2_Llama70B', 'Worker3_Mixtral', 'Referee_GPT4oMini', 'Final_Score'])
                
                # Ghi nối tiếp từng dòng thành công
                for item in processed_batch:
                    if item.get("status") == "api_error": continue
                    
                    # Rút trích danh sách từ vựng thành chuỗi để dễ nhìn trong Excel
                    w1 = str(item.get("worker_extractions", [{}])[0].get("data", {})) if len(item.get("worker_extractions", [])) > 0 else "{}"
                    w2 = str(item.get("worker_extractions", [{}])[1].get("data", {})) if len(item.get("worker_extractions", [])) > 1 else "{}"
                    w3 = str(item.get("worker_extractions", [{}])[2].get("data", {})) if len(item.get("worker_extractions", [])) > 2 else "{}"
                    ref = str(item.get("referee_final_words", {}))
                    
                    writer.writerow([
                        item["id"], 
                        item.get("is_valid", True), 
                        item.get("is_potential_seeding", False),
                        w1, w2, w3, ref,
                        item.get("final_score_0_to_1", 0.5)
                    ])
            print(f" 📊 Đã ghi nối tiếp {len(successful_ids)} dòng vào file CSV Colorkey.")

        conn.commit()
        conn.close()
        print(f"✅ Đã chốt sổ an toàn lô {len(successful_ids)} câu (gồm {new_valid_comments} câu hợp lệ) cho brand {brand_id}.")