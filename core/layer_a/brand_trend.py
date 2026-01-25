# trong danh mục A, thương hiệu B đang tốt lên hay xấu đi?
from crawler.db.db_connection import get_connection
from datetime import datetime, timedelta


def brand_trend_30d(brand_id: int, category_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now()
    d30 = now - timedelta(days=30)
    d60 = now - timedelta(days=60)

    # Avg rating last 30 days
    cursor.execute("""
        SELECT AVG(r.Rating)
        FROM Review r
        JOIN Product p ON r.ProductId = p.ProductId
        WHERE p.BrandId = ?
          AND p.CategoryId = ?
          AND r.ReviewTime >= ?
    """, brand_id, category_id, d30)

    avg_last_30 = cursor.fetchone()[0]

    # Avg rating previous 30 days
    cursor.execute("""
        SELECT AVG(r.Rating)
        FROM Review r
        JOIN Product p ON r.ProductId = p.ProductId
        WHERE p.BrandId = ?
          AND p.CategoryId = ?
          AND r.ReviewTime >= ?
          AND r.ReviewTime < ?
    """, brand_id, category_id, d60, d30)

    avg_prev_30 = cursor.fetchone()[0]

    conn.close()

    # xử lý thiếu dữ liệu
    if avg_last_30 is None or avg_prev_30 is None:
        return {
            "brandId": brand_id,
            "categoryId": category_id,
            "trend": "Insufficient data"
        }

    delta = round(avg_last_30 - avg_prev_30, 4)

    if delta > 0.05:
        trend = "Improving"
    elif delta < -0.05:
        trend = "Declining"
    else:
        trend = "Stable"

    return {
        "brandId": brand_id,
        "categoryId": category_id,
        "trend": trend,
        "windows": {
            "last_30_days": round(avg_last_30, 3),
            "previous_30_days": round(avg_prev_30, 3)
        },
        "delta": delta
    }
