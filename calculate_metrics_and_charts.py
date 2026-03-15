import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

def run_analysis():
    print("📊 BẮT ĐẦU PHÂN TÍCH METRIC HỌC THUẬT...")
    
    # 1. Đọc file CSV (Sau khi bạn đã gộp 2 file lại thành 1 file hoàn chỉnh nhé)
    file_path = 'colorkey_experiment_results.csv'
    if not os.path.exists(file_path):
        print(f"❌ Không tìm thấy file {file_path}. Vui lòng kiểm tra lại!")
        return
        
    df = pd.read_csv(file_path)
    print(f"✅ Đã tải thành công {len(df)} dòng dữ liệu.")

    # Tên các cột model trong CSV (Ghi chú: Cột Gemini thực chất đang chứa điểm của model Groq Dynamic)
    models = ['VADER', 'GPT', 'Gemini', 'Llama']

    # ==========================================
    # METRIC 1: MA TRẬN TƯƠNG QUAN (CORRELATION)
    # ==========================================
    print("⏳ Đang vẽ Ma trận tương quan (Heatmap)...")
    corr_matrix = df[models].corr(method='pearson')
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', vmin=0, vmax=1, fmt=".2f")
    plt.title('Ma trận tương quan giữa các Mô hình chấm điểm', pad=15)
    plt.tight_layout()
    plt.savefig('metric_correlation_heatmap.png', dpi=300)
    plt.close()

    # ==========================================
    # METRIC 2: BIỂU ĐỒ PHÂN BỐ ĐIỂM SỐ (DISTRIBUTION)
    # ==========================================
    print("⏳ Đang vẽ Biểu đồ phân bố điểm số...")
    plt.figure(figsize=(10, 6))
    for model in models:
        # Dùng KDE plot để xem mật độ phân bổ điểm từ -1 đến 1
        sns.kdeplot(df[model], label=model, fill=True, alpha=0.2, linewidth=2)
        
    plt.title('Phân bố Điểm Cảm Xúc (Sentiment Distribution)', pad=15)
    plt.xlabel('Điểm số (-1.0 Rất tiêu cực -> 1.0 Rất tích cực)')
    plt.ylabel('Mật độ (Density)')
    plt.legend()
    plt.tight_layout()
    plt.savefig('metric_score_distribution.png', dpi=300)
    plt.close()

    # ==========================================
    # METRIC 3: TRÍCH XUẤT "BẰNG CHỨNG THÉP" (CASE STUDY)
    # ==========================================
    print("⏳ Đang lọc các bình luận VADER chấm sai nhưng AI chấm đúng...")
    
    # Tính điểm trung bình của bộ 3 AI
    df['AI_Average'] = df[['GPT', 'Gemini', 'Llama']].mean(axis=1)
    
    # Tính độ chênh lệch tuyệt đối giữa VADER (Rule-based) và trung bình AI
    df['Gap_Vader_vs_AI'] = abs(df['VADER'] - df['AI_Average'])
    
    # Lọc ra 15 bình luận có độ chênh lệch kinh khủng nhất để đưa vào Slide báo cáo
    top_differences = df.sort_values(by='Gap_Vader_vs_AI', ascending=False).head(15)
    
    # Xuất ra file CSV riêng để bạn dễ copy
    columns_to_export = ['ReviewId', 'Comment', 'VADER', 'GPT', 'Gemini', 'Llama', 'AI_Average', 'Gap_Vader_vs_AI']
    top_differences[columns_to_export].to_csv('metric_case_studies.csv', index=False, encoding='utf-8-sig')

    # ==========================================
    # TỔNG KẾT
    # ==========================================
    print("\n🎉 HOÀN TẤT PHÂN TÍCH! CÁC TÀI SẢN ĐÃ ĐƯỢC LƯU:")
    print(" 📸 1. metric_correlation_heatmap.png (Chèn vào Luận văn phần Đánh giá độ đồng thuận)")
    print(" 📸 2. metric_score_distribution.png  (Chèn vào Luận văn phần Phân tích phân phối)")
    print(" 📑 3. metric_case_studies.csv        (Lấy ví dụ chèn vào Slide thuyết trình)")

if __name__ == "__main__":
    run_analysis()