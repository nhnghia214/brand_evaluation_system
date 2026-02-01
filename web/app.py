# web/app.py

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from fastapi import FastAPI
import threading

from web.ui import router as ui_router

from crawler.service import CrawlService
from crawler.db.db_connection import get_connection

from core.layer_a.brand_category_resolver import BrandCategoryResolver
from core.layer_a.data_freshness import DataFreshnessEvaluator
from core.layer_a.crawl_job_orchestrator import CrawlJobOrchestrator
from core.layer_b.analysis_service import AnalysisService
from core.layer_a.message_mapper import MessageMapper

from core.dto.brand_data_status import BrandDataStatus
from web.schemas import EvaluateRequest, EvaluateResponse
from core.layer_c.brand_narrator import narrate_brand_evaluation


app = FastAPI(title="Brand Evaluation API")
app.include_router(ui_router)


# ==================================================
# 🔥 BACKGROUND SERVICES
# ==================================================
@app.on_event("startup")
def start_background_services():
    # Crawl service
    crawler = CrawlService()
    threading.Thread(target=crawler.run, daemon=True).start()

    # 🔥 Analysis service 
    analysis = AnalysisService()
    threading.Thread(target=analysis.run, daemon=True).start()



# ==================================================
# 🔥 API: EVALUATE BRAND
# ==================================================
@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate_brand(req: EvaluateRequest):
    resolver = BrandCategoryResolver()
    freshness_evaluator = DataFreshnessEvaluator()
    crawl_orchestrator = CrawlJobOrchestrator()
    analysis_service = AnalysisService()

    # ===============================
    # STEP 1: Resolve brand/category
    # ===============================
    resolve_result = resolver.resolve(req.brand, req.category)
    if resolve_result.status != "VALID":
        return EvaluateResponse(
            brand=req.brand,
            category=req.category,
            score=None,
            message="Thương hiệu hoặc danh mục không hợp lệ.",
            status="INVALID"
        )

    brand_id = resolve_result.brand_id
    category_id = resolve_result.category_id

    # ==================================================
    # 🔥🔥🔥 STEP 2: FORCE SNAPSHOT REBUILD (KEY FIX)
    # ==================================================
    # 👉 BẤT KỂ job trạng thái gì
    # 👉 BẤT KỂ review có trùng hay không
    # 👉 Snapshot luôn được rebuild từ Review table
    print(
        f"[System] Rebuilding analysis snapshot "
        f"(brand={brand_id}, category={category_id})"
    )
    analysis_service._analyze_single(brand_id, category_id)

    # ===============================
    # STEP 3: Reload BrandDataStatus (AFTER SNAPSHOT)
    # ===============================
    conn = get_connection()
    cursor = conn.cursor()
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
    conn.close()

    status_obj = None
    if row:
        status_obj = BrandDataStatus(
            brand_id=row.BrandId,
            category_id=row.CategoryId,
            total_reviews=row.TotalReviews,
            latest_review_time=row.LatestReviewTime,
            data_freshness_days=row.DataFreshnessDays,
            last_evaluated_at=row.LastEvaluatedAt
        )

    # ===============================
    # STEP 4: Evaluate freshness (POST-SNAPSHOT)
    # ===============================
    evaluation = freshness_evaluator.evaluate(status_obj)

    # ===============================
    # STEP 5: Crawl decision (FUTURE DATA)
    # ===============================
    job_status = crawl_orchestrator.handle_decision(
        brand_id=brand_id,
        category_id=category_id,
        recommended_action=evaluation.recommended_action
    )

    # ===============================
    # STEP 6: Load analysis result
    # ===============================
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            AvgRating,
            PositiveRate,
            NegativeRate,
            GeneratedAt
        FROM BrandAnalysisResult
        WHERE BrandId = ? AND CategoryId = ?
    """, (brand_id, category_id))
    analysis_row = cursor.fetchone()
    conn.close()

    if analysis_row:
        score = analysis_row.AvgRating
        message_text = narrate_brand_evaluation(
            brand=req.brand,
            category=req.category,
            score=score,
            avg_rating=analysis_row.AvgRating,
            positive_rate=analysis_row.PositiveRate,
            negative_rate=analysis_row.NegativeRate,
            total_reviews=status_obj.total_reviews if status_obj else 0
        )
        status = "READY"
    else:
        user_message = MessageMapper.map(evaluation, job_status)
        score = None
        message_text = user_message.message
        status = user_message.severity

    return EvaluateResponse(
        brand=req.brand,
        category=req.category,
        score=score,
        message=message_text,
        status=status
    )
