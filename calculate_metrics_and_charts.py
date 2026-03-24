import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

def run_analysis():
    print("📊 BẮT ĐẦU PHÂN TÍCH METRIC HỌC THUẬT...")
    
    # 1. Đọc file CSV
    file_path = 'colorkey_final_experiment.csv'
    if not os.path.exists(file_path):
        print(f"❌ Không tìm thấy file {file_path}. Vui lòng kiểm tra lại!")
        return
        
    df = pd.read_csv(file_path)
    print(f"✅ Đã tải thành công {len(df)} dòng dữ liệu.")

    # ĐÃ SỬA: Tên các cột AI cho khớp chính xác 100% với file CSV
    models = ['VADER', 'ChatGPT', 'llama-3.3-70b-versatile', 'Llama-3']

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
    
    # ĐÃ SỬA: Tính điểm trung bình của bộ 3 AI (Bỏ VADER ra)
    df['AI_Average'] = df[['ChatGPT', 'llama-3.3-70b-versatile', 'Llama-3']].mean(axis=1)
    
    # Tính độ chênh lệch tuyệt đối giữa VADER (Rule-based) và trung bình AI
    df['Gap_Vader_vs_AI'] = abs(df['VADER'] - df['AI_Average'])
    
    # Lọc ra 15 bình luận có độ chênh lệch kinh khủng nhất để đưa vào Slide báo cáo
    top_differences = df.sort_values(by='Gap_Vader_vs_AI', ascending=False).head(15)
    
    # ĐÃ SỬA: Xuất ra file CSV riêng đúng tên cột
    columns_to_export = ['ReviewId', 'Comment', 'VADER', 'ChatGPT', 'llama-3.3-70b-versatile', 'Llama-3', 'AI_Average', 'Gap_Vader_vs_AI']
    top_differences[columns_to_export].to_csv('metric_case_studies.csv', index=False, encoding='utf-8-sig')

    # ==========================================
    # TỔNG KẾT
    # ==========================================
    print("\n🎉 HOÀN TẤT PHÂN TÍCH! CÁC TÀI SẢN ĐÃ ĐƯỢC LƯU:")
    print(" 📸 1. metric_correlation_heatmap.png")
    print(" 📸 2. metric_score_distribution.png")
    print(" 📑 3. metric_case_studies.csv")

if __name__ == "__main__":
    run_analysis()