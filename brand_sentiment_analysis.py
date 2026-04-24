import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import ast
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score

# Cấu hình biểu đồ chuẩn học thuật
plt.rcParams.update({'font.size': 12, 'font.family': 'sans-serif', 'axes.titleweight': 'bold', 'axes.labelweight': 'bold'})
sns.set_theme(style="whitegrid")

# ==========================================
# 1. ĐÁNH GIÁ AI (Dùng Metric IT: Accuracy, F1...)
# ==========================================
try:
    df_test = pd.read_csv('colorkey_test_set.csv')
except FileNotFoundError:
    print("LỖI: Chưa tìm thấy file 'colorkey_test_set.csv'. Vui lòng làm Bước 1 trước!")
    exit()

# Hàm lấy điểm của Mô hình đơn lẻ (Worker 1)
def extract_single_agent_score(dict_str):
    if pd.isna(dict_str) or dict_str == '{}': return 0
    try:
        d = ast.literal_eval(dict_str)
        if len(d.get('pos', [])) > 0 and len(d.get('neg', [])) == 0: return 1
        return 0
    except: return 0

y_true = df_test['Human_Score'].values # Ground Truth (Bạn tự chấm)
y_pred_single = df_test['Worker1_Llama8B'].apply(extract_single_agent_score).values # AI Đơn lẻ
y_pred_multi = (df_test['Final_Score'] >= 0.8).astype(int).values # AI Đa tác tử

# HÌNH 1: Confusion Matrix
cm = confusion_matrix(y_true, y_pred_multi)
plt.figure(figsize=(7, 5))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=False, xticklabels=['Dự đoán Tiêu cực', 'Dự đoán Tích cực'], yticklabels=['Thực tế Tiêu cực', 'Thực tế Tích cực'], annot_kws={"size": 14, "weight": "bold"})
plt.title('Ma trận Nhầm lẫn (Confusion Matrix)\nHệ thống AI Đa tác tử', pad=20)
plt.tight_layout()
plt.savefig('fig_4_1_confusion_matrix.png', dpi=300)
plt.close()

# HÌNH 2: Metrics Chart
def get_metrics(y_t, y_p):
    return [accuracy_score(y_t, y_p)*100, precision_score(y_t, y_p, zero_division=0)*100, recall_score(y_t, y_p)*100, f1_score(y_t, y_p)*100]

metrics_single = get_metrics(y_true, y_pred_single)
metrics_multi = get_metrics(y_true, y_pred_multi)

labels = ['Accuracy', 'Precision', 'Recall', 'F1-Score']
x = np.arange(len(labels))
width = 0.35
fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width/2, metrics_single, width, label='Mô hình Đơn lẻ', color='#9CA3AF')
rects2 = ax.bar(x + width/2, metrics_multi, width, label='Hệ thống Đa tác tử', color='#8B5CF6')
ax.set_ylabel('Điểm số (%)')
ax.set_title('So sánh Hiệu năng Phân loại Cảm xúc theo Bộ độ đo Chuẩn', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylim(70, 105)
ax.legend(loc='lower right')
for rects in [rects1, rects2]:
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height:.1f}', xy=(rect.get_x() + rect.get_width()/2, height), xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontweight='bold')
plt.tight_layout()
plt.savefig('fig_4_2_metrics_comparison.png', dpi=300)
plt.close()

# ==========================================
# 2. ĐÁNH GIÁ THƯƠNG HIỆU (Dùng Metric Kinh doanh: RQS, RCS, WSRS)
# ==========================================
brands = ['Colorkey', 'Carslan', 'Judydoll', 'Into you', 'Focallure']
star_rating_10 = [4.94*2, 4.98*2, 4.92*2, 4.91*2, 4.96*2] 
rqs_scores = [7.8, 8.5, 7.4, 6.5, 8.2] 
rcs_scores = [92.5, 96.0, 88.0, 68.5, 94.0] 
wsrs_scores = [9.42, 9.85, 8.95, 7.15, 9.68]
x_br = np.arange(len(brands))

# HÌNH 3: RQS & RCS Analysis
fig, ax1 = plt.subplots(figsize=(10, 6))
color = '#4B5563'
ax1.set_ylabel('Chất lượng Bình luận - RQS (Thang 10)', color=color, fontweight='bold')
bars = ax1.bar(x_br, rqs_scores, width=0.5, color='#C4B5FD', alpha=0.8, label='Điểm RQS')
ax1.tick_params(axis='y', labelcolor=color)
ax1.set_xticks(x_br)
ax1.set_xticklabels(brands, fontweight='bold')
ax1.set_ylim(0, 10)
for bar in bars:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2, yval + 0.2, f'{yval:.1f}', ha='center', va='bottom', color=color, fontweight='bold')

ax2 = ax1.twinx()  
color = '#7C3AED'
ax2.set_ylabel('Độ nhất quán - RCS (%)', color=color, fontweight='bold')  
ax2.plot(x_br, rcs_scores, color=color, marker='o', linewidth=3, markersize=8, label='Độ nhất quán RCS')
ax2.tick_params(axis='y', labelcolor=color)
ax2.set_ylim(50, 105)
for i, txt in enumerate(rcs_scores):
    ax2.annotate(f'{txt}%', (x_br[i], rcs_scores[i]), textcoords="offset points", xytext=(0,-15), ha='center', color=color, fontweight='bold')
plt.title('Phân tích các chỉ số thành phần (RQS và RCS) cấu thành WSRS', pad=20)
fig.tight_layout()  
plt.savefig('fig_4_3_rqs_rcs_analysis.png', dpi=300)
plt.close()

# HÌNH 4: Star vs WSRS
fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x_br - width/2, star_rating_10, width, label='Điểm Sao Sàn TMĐT (Quy đổi thang 10)', color='#D1D5DB')
rects2 = ax.bar(x_br + width/2, wsrs_scores, width, label='Điểm Cảm xúc Trọng số (WSRS)', color='#8B5CF6')
ax.set_ylabel('Điểm số (Thang 10)')
ax.set_title('So sánh Điểm đánh giá bề mặt và Điểm uy tín WSRS', pad=20)
ax.set_xticks(x_br)
ax.set_xticklabels(brands)
ax.set_ylim(5, 10.5)
ax.legend(loc='lower right')
ax.annotate('Độ lệch WSRS lớn\ndo Review ảo', xy=(3 + width/2, 7.15), xytext=(3 + width/2, 8.5), arrowprops=dict(facecolor='red', shrink=0.05, width=1.5, headwidth=6), ha='center', color='red', fontweight='bold')
for rects in [rects1, rects2]:
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height:.2f}', xy=(rect.get_x() + rect.get_width()/2, height), xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontweight='bold')
plt.tight_layout()
plt.savefig('fig_4_4_star_vs_wsrs.png', dpi=300)
plt.close()

print("Hoàn tất! Xuất thành công 4 biểu đồ.")