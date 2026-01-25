# analysis/run_brand_analysis_job.py
# Job chạy phân tích (Task Scheduler gọi)
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from db.db_connection import get_connection
from analysis.brand_analyzer import analyze_brand_category


def run_brand_analysis_job():
    conn = get_connection()
    cursor = conn.cursor()

    # 1️⃣ Lấy danh sách Brand × Category có review
    cursor.execute("""
        SELECT DISTINCT p.BrandId, p.CategoryId
        FROM Product p
        JOIN Review r ON p.ProductId = r.ProductId
    """)

    pairs = cursor.fetchall()
    conn.close()

    print(f"[JOB] Found {len(pairs)} brand-category pairs")

    # 2️⃣ Chạy phân tích
    for brand_id, category_id in pairs:
        try:
            analyze_brand_category(brand_id, category_id)
        except Exception as e:
            print(f"[ERROR] Brand {brand_id} - Category {category_id}: {e}")


if __name__ == "__main__":
    run_brand_analysis_job()
