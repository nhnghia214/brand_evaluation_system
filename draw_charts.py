import pandas as pd
import ast
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

def safe_parse_dict(dict_str):
    try:
        return ast.literal_eval(dict_str)
    except:
        return {'pos': [], 'neg': []}

def get_word_count(extracted_dict):
    pos_count = len(extracted_dict.get('pos', []))
    neg_count = len(extracted_dict.get('neg', []))
    total = pos_count + neg_count
    if total == 0: return 0.0
    return (pos_count - neg_count) / total

def main():
    print("Đang đọc file colorkey_llm_comparison_log.csv...")
    try:
        df = pd.read_csv('colorkey_llm_comparison_log.csv')
    except Exception as e:
        print(f"Lỗi đọc file: {e}. Vui lòng kiểm tra lại file CSV.")
        return

    # Chỉ phân tích những câu hợp lệ
    valid_df = df[df['Is_Valid'] == True].copy()
    print(f"Đã nạp {len(valid_df)} đánh giá hợp lệ.")

    # Tính điểm gốc (-1 đến 1) cho từng Agent để làm cơ sở so sánh
    valid_df['W1_Score'] = valid_df['Worker1_Llama8B'].apply(lambda x: get_word_count(safe_parse_dict(x)))
    valid_df['W2_Score'] = valid_df['Worker2_Llama70B'].apply(lambda x: get_word_count(safe_parse_dict(x)))
    valid_df['W3_Score'] = valid_df['Worker3_Mixtral'].apply(lambda x: get_word_count(safe_parse_dict(x))) # Hoặc Llama3B/Gemma
    valid_df['Ref_Score'] = valid_df['Referee_GPT4oMini'].apply(lambda x: get_word_count(safe_parse_dict(x)))

    # ====================================================
    # BIỂU ĐỒ 1: MA TRẬN TƯƠNG QUAN LLM (Thay thế Biểu đồ 1 cũ)
    # ====================================================
    scores_df = valid_df[['W1_Score', 'W2_Score', 'W3_Score', 'Ref_Score']]
    # Đổi tên cột cho đẹp trên biểu đồ
    scores_df.columns = ['Llama 8B', 'Llama 70B', 'Llama 8B (Backup)', 'GPT-4o-Mini (Referee)']
    
    corr_matrix = scores_df.corr()
    
    plt.figure(figsize=(10, 7))
    sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', vmin=0.5, vmax=1.0, 
                linewidths=.5, fmt=".3f", annot_kws={"size": 12})
    plt.title('Ma Trận Tương Quan Năng Lực Trích Xuất Cảm Xúc Giữa Các Tác Tử AI', pad=20, fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig('Chart_1_Correlation_Matrix.png', dpi=300)
    print("Đã lưu Biểu đồ 1: Chart_1_Correlation_Matrix.png")

    # ====================================================
    # BIỂU ĐỒ 2: ĐỘ ĐỒNG THUẬN CỦA HỘI ĐỒNG AI (Thay thế Biểu đồ 2 cũ)
    # ====================================================
    # Tính toán mức độ đồng thuận
    def check_consensus(row):
        s1, s2, s3 = round(row['W1_Score'], 2), round(row['W2_Score'], 2), round(row['W3_Score'], 2)
        if s1 == s2 == s3:
            return 'Đồng thuận Tuyệt đối (3/3)'
        elif s1 == s2 or s2 == s3 or s1 == s3:
            return 'Đồng thuận Đa số (2/3)'
        else:
            return 'Bất đồng Toàn tập (Cần Trọng tài)'

    valid_df['Consensus'] = valid_df.apply(check_consensus, axis=1)
    consensus_counts = valid_df['Consensus'].value_counts()

    plt.figure(figsize=(8, 8))
    colors = ['#2ca02c', '#f1c40f', '#d62728'] # Xanh, Vàng, Đỏ
    plt.pie(consensus_counts, labels=consensus_counts.index, autopct='%1.1f%%', 
            startangle=140, colors=colors, textprops={'fontsize': 12},
            wedgeprops={'edgecolor': 'black', 'linewidth': 1.5})
    plt.title('Tỷ lệ Đồng thuận của Nhóm Worker Đa tác tử\nTrên tập dữ liệu tiếng Việt thực tế', pad=20, fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig('Chart_2_Consensus_Pie.png', dpi=300)
    print("Đã lưu Biểu đồ 2: Chart_2_Consensus_Pie.png")

if __name__ == '__main__':
    main()