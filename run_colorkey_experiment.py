import os
import csv
import time
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

from crawler.db.db_connection import get_connection
from core.layer_b.sentiment_token_analyzer import SentimentTokenAnalyzer
from core.layer_b.sentiment_agents.gpt_agent import GPTSentimentAgent
from core.layer_b.sentiment_agents.locked_groq_agent import LockedGroqAgent # <-- Dùng Đặc vụ mới
from core.layer_b.sentiment_agents.llama_agent import LlamaSentimentAgent
from core.layer_b.sentiment_agents.aggregator import WeightedSentimentAggregator
from core.layer_a.score_calculator import calculate

BRAND_NAME = "Colorkey"

def run_experiment():
    print(f"🚀 BẮT ĐẦU CHIẾN DỊCH THỰC NGHIỆM CHO BRAND: {BRAND_NAME}")
    
    vader_analyzer = SentimentTokenAnalyzer()
    # Sử dụng LockedGroqAgent thay cho DynamicGroqAgent
    agents = [GPTSentimentAgent(), LockedGroqAgent(), LlamaSentimentAgent()]
    weights = [0.25, 0.25, 0.25, 0.25]
    aggregator = WeightedSentimentAggregator(agents, weights)

    model1_name = agents[0].agent_name
    model2_name = agents[1].agent_name 
    model3_name = agents[2].agent_name

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT BrandId FROM Brand WHERE BrandName = ?", (BRAND_NAME,))
    brand_id = cursor.fetchone()[0]
    cursor.execute("SELECT TOP 1 CategoryId FROM Product WHERE BrandId = ?", (brand_id,))
    category_id = cursor.fetchone()[0]

    print("⏳ Đang tải dữ liệu Review từ Database...")
    cursor.execute("""
        SELECT r.ReviewId, r.Comment, r.Rating
        FROM Review r
        JOIN Product p ON r.ProductId = p.ProductId
        WHERE p.BrandId = ? AND r.Comment IS NOT NULL
    """, (brand_id,))
    reviews = cursor.fetchall()
    total_reviews = len(reviews)

    csv_filename = "colorkey_final_experiment.csv"
    start_index = 0

    # KIỂM TRA TỰ ĐỘNG CHẠY NỐI TIẾP (AUTO-RESUME)
    if os.path.exists(csv_filename):
        df_existing = pd.read_csv(csv_filename)
        start_index = len(df_existing)
        print(f"📂 Đã tìm thấy file CSV cũ với {start_index} dòng.")
        if start_index >= total_reviews:
            print("✅ Dữ liệu đã được xử lý xong toàn bộ 100%. Không cần chạy thêm!")
            return
        print(f"▶️ Sẽ chạy nối tiếp từ dòng {start_index + 1}...")
        file_mode = 'a' # Mở file ở chế độ Append (Ghi nối tiếp)
    else:
        print(f"🆕 Tạo file CSV mới. Sẽ xử lý toàn bộ {total_reviews} bình luận.")
        file_mode = 'w' # Mở file ở chế độ Write (Ghi mới)

    # BẮT ĐẦU CHẤM ĐIỂM
    try:
        with open(csv_filename, mode=file_mode, newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            
            # Chỉ ghi Header nếu là file mới tạo
            if file_mode == 'w':
                writer.writerow(["ReviewId", "Comment", "VADER", model1_name, model2_name, model3_name, "Aggregated_Ratio"])

            # Vòng lặp chỉ chạy những review chưa được xử lý
            for i, row in enumerate(reviews[start_index:]):
                current_index = start_index + i + 1
                review_id = row.ReviewId
                comment = row.Comment
                
                # Phân tích
                pos, neg = vader_analyzer.analyze_reviews([comment])
                vader_ratio = 0.5 if pos + neg == 0 else pos / (pos + neg)
                vader_score_minus1_to_1 = (vader_ratio * 2) - 1
                
                score_1 = agents[0].analyze_sentiment(comment)
                score_2 = agents[1].analyze_sentiment(comment) # NẾU GẶP LỖI 429 SẼ VĂNG RA NGAY
                score_3 = agents[2].analyze_sentiment(comment)
                
                all_scores = [vader_score_minus1_to_1, score_1, score_2, score_3]
                final_minus1_to_1 = sum(s * w for s, w in zip(all_scores, weights))
                sentiment_ratio = (final_minus1_to_1 + 1.0) / 2.0
                
                # Ghi vào CSV
                writer.writerow([review_id, comment, vader_score_minus1_to_1, score_1, score_2, score_3, sentiment_ratio])
                file.flush() # Bắt buộc ghi ngay xuống ổ cứng để chống mất data
                
                print(f"🔄 Đã xử lý {current_index}/{total_reviews} bình luận...")
                time.sleep(6)
                
    except Exception as e:
        if str(e) == "RATE_LIMIT_REACHED":
            print("\n" + "="*50)
            print("🛑 TẠM DỪNG HỆ THỐNG: Đã hết hạn mức gọi API trong ngày của Groq!")
            print("💾 Tiến trình đã được lưu lại an toàn. Ngày mai bạn hãy chạy lại lệnh cũ để tiếp tục.")
            print("="*50 + "\n")
            return # Dừng toàn bộ chương trình, không chạy xuống phần Update DB
        else:
            print(f"❌ Lỗi hệ thống nghiêm trọng: {e}")
            return

    # NẾU CHẠY XONG 100% THÌ MỚI UPDATE DATABASE
    print("✅ Đã xử lý 100% dữ liệu. Đang tính điểm tổng và cập nhật Database...")
    
    # Tính lại tổng điểm từ file CSV cho chính xác
    df_final = pd.read_csv(csv_filename)
    avg_sentiment_ratio = df_final['Aggregated_Ratio'].mean()
    
    # Lấy Avg_Rating từ Database
    cursor.execute("""
        SELECT AVG(CAST(r.Rating AS FLOAT))
        FROM Review r
        JOIN Product p ON r.ProductId = p.ProductId
        WHERE p.BrandId = ? AND r.Comment IS NOT NULL
    """, (brand_id,))
    avg_rating = cursor.fetchone()[0] or 0.0
    
    final_score = calculate(avg_rating=avg_rating, sentiment_ratio=avg_sentiment_ratio, total_reviews=total_reviews)

    cursor.execute("""
        UPDATE BrandAnalysisResult
        SET AvgRating = ?, PositiveRate = ?, NegativeRate = ?, Score = ?, GeneratedAt = GETDATE()
        WHERE BrandId = ? AND CategoryId = ?
    """, (avg_rating, avg_sentiment_ratio, 1 - avg_sentiment_ratio, final_score, brand_id, category_id))
    
    conn.commit()
    conn.close()
    
    print("🎉 HOÀN TẤT CHIẾN DỊCH VÀ ĐÃ CẬP NHẬT DATABASE THÀNH CÔNG!")

if __name__ == "__main__":
    run_experiment()