# core/runners/run_brand_analysis_job.py
# Job chạy phân tích brand × category (Task Scheduler)

from pathlib import Path
import sys
import os
import traceback
from datetime import datetime

# =========================
# 1. Setup BASE_DIR + cwd
# =========================
BASE_DIR = Path(__file__).resolve().parents[2]   # brand_evaluation_system
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)

# =========================
# 2. Logging
# =========================
LOG_FILE = BASE_DIR / "task_brand_analysis.log"

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

log("\n" + "=" * 60)
log(f"JOB START: {datetime.now()}")

# =========================
# 3. Import project modules
# =========================
try:
    from crawler.db.db_connection import get_connection
    from core.layer_b.brand_analyzer import analyze_brand_category
except Exception:
    log("[FATAL] Import error")
    log(traceback.format_exc())
    raise

# =========================
# 4. Job logic
# =========================
def run_brand_analysis_job():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT p.BrandId, p.CategoryId
            FROM Product p
            JOIN Review r ON p.ProductId = r.ProductId
        """)

        pairs = cursor.fetchall()
        cursor.close()
        conn.close()

        log(f"[JOB] Found {len(pairs)} brand-category pairs")

        for brand_id, category_id in pairs:
            try:
                log(f"[RUN] Brand {brand_id} - Category {category_id}")
                analyze_brand_category(brand_id, category_id)
            except Exception:
                log(f"[ERROR] Brand {brand_id} - Category {category_id}")
                log(traceback.format_exc())

        log("[JOB] DONE SUCCESSFULLY")

    except Exception:
        log("[FATAL JOB ERROR]")
        log(traceback.format_exc())
        raise


# =========================
# 5. Entry point
# =========================
if __name__ == "__main__":
    run_brand_analysis_job()
