# core/runners/run_brand_analysis_job.py

"""
Batch job runner for brand analysis.

Responsibility:
- Iterate through brand-category pairs
- Trigger Layer B analysis
- Evaluate data freshness via Layer A
- Create crawl jobs if needed
"""

from crawler.db.db_connection import get_connection

from core.layer_b.brand_analyzer import analyze_brand_category
from core.layer_a.data_freshness import DataFreshnessEvaluator
from core.layer_a.crawl_job_orchestrator import CrawlJobOrchestrator
from core.dto.brand_data_status import BrandDataStatus


def run():
    conn = get_connection()
    cursor = conn.cursor()

    # 1️⃣ Lấy danh sách Brand × Category cần xử lý
    cursor.execute("""
        SELECT DISTINCT BrandId, CategoryId
        FROM Product
    """)
    targets = cursor.fetchall()

    if not targets:
        print("[INFO] No brand-category target found.")
        return

    freshness_evaluator = DataFreshnessEvaluator()
    crawl_orchestrator = CrawlJobOrchestrator()

    for brand_id, category_id in targets:
        print(f"[RUN] Brand {brand_id} - Category {category_id}")

        # ===============================
        # STEP 1: Layer B – Analyze data
        # ===============================
        analyze_brand_category(brand_id, category_id)

        # ===============================
        # STEP 2: Load BrandDataStatus (FACT)
        # ===============================
        cursor.execute("""
            SELECT
                BrandId,
                CategoryId,
                TotalReviews,
                LatestReviewTime,
                DataFreshnessDays,
                LastEvaluatedAt
            FROM BrandDataStatus
            WHERE BrandId = ? AND CategoryId = ?
        """, (brand_id, category_id))

        row = cursor.fetchone()
        if not row:
            print("[WARN] No BrandDataStatus found after analysis.")
            continue

        status = BrandDataStatus(
            brand_id=row.BrandId,
            category_id=row.CategoryId,
            total_reviews=row.TotalReviews,
            latest_review_time=row.LatestReviewTime,
            data_freshness_days=row.DataFreshnessDays,
            last_evaluated_at=row.LastEvaluatedAt
        )

        # ===============================
        # STEP 3: Layer A – Evaluate freshness
        # ===============================
        evaluation = freshness_evaluator.evaluate(status)

        # ===============================
        # STEP 4: Layer A – Handle crawl decision
        # ===============================
        job_status = crawl_orchestrator.handle_decision(
            brand_id=brand_id,
            category_id=category_id,
            recommended_action=evaluation.recommended_action
        )

        print(
            f"[DECISION] {evaluation.recommended_action} "
            f"=> {job_status}"
        )

    conn.close()
