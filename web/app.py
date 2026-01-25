# web/app.py
from web.ui import router as ui_router

from fastapi import FastAPI, HTTPException

from crawler.db.db_connection import get_connection

from core.layer_a.brand_category_resolver import BrandCategoryResolver
from core.layer_a.data_freshness import DataFreshnessEvaluator
from core.layer_a.crawl_job_orchestrator import CrawlJobOrchestrator
from core.layer_a.score_calculator import calculate
from core.layer_a.message_mapper import MessageMapper

from core.layer_c.brand_presenter import BrandPresenter
from core.dto.brand_data_status import BrandDataStatus
from core.dto.user_message import UserMessage
from web.schemas import EvaluateRequest, EvaluateResponse
from core.layer_c.brand_narrator import narrate_brand_evaluation


app = FastAPI(title="Brand Evaluation API")
app.include_router(ui_router)


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate_brand(req: EvaluateRequest):
    resolver = BrandCategoryResolver()
    freshness_evaluator = DataFreshnessEvaluator()
    crawl_orchestrator = CrawlJobOrchestrator()

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

    # ===============================
    # STEP 2: Load BrandDataStatus
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
    # STEP 3: Evaluate freshness
    # ===============================
    evaluation = freshness_evaluator.evaluate(status_obj)

    # ===============================
    # STEP 4: Handle crawl decision
    # ===============================
    job_status = crawl_orchestrator.handle_decision(
        brand_id=brand_id,
        category_id=category_id,
        recommended_action=evaluation.recommended_action
    )

    # ===============================
    # STEP 5: Load analysis result
    # ===============================
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT AvgRating, PositiveRate, NegativeRate
        FROM BrandAnalysisResult
        WHERE BrandId = ? AND CategoryId = ?
    """, (brand_id, category_id))

    analysis_row = cursor.fetchone()
    conn.close()

    score = None
    if analysis_row:
        score = calculate(
            avg_rating=analysis_row.AvgRating,
            positive_rate=analysis_row.PositiveRate,
            total_reviews=status_obj.total_reviews if status_obj else 0
        )

    # ===============================
    # STEP 6: Message mapping + present
    # ===============================
    user_message = MessageMapper.map(evaluation, job_status)

    message_text = narrate_brand_evaluation(
        brand=req.brand,
        category=req.category,
        score=score if score is not None else 0,
        avg_rating=analysis_row.AvgRating if analysis_row else 0,
        positive_rate=analysis_row.PositiveRate if analysis_row else 0,
        negative_rate=analysis_row.NegativeRate if analysis_row else 0,
        total_reviews=status_obj.total_reviews if status_obj else 0
    )

    return EvaluateResponse(
        brand=req.brand,
        category=req.category,
        score=score,
        message=message_text,
        status=user_message.severity
    )
