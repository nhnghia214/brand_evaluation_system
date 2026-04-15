# web/app.py

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
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

from pathlib import Path
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Brand Evaluation API")
app.add_middleware(SessionMiddleware, secret_key="luan_van_ai_brand_evaluator_secret")

BASE_DIR = Path(__file__).resolve().parent

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)
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

    # LƯU Ý: ĐÃ XÓA LỆNH FORCE SNAPSHOT REBUILD Ở ĐÂY ĐỂ TRÁNH TREO WEB

    # ===============================
    # STEP 2: Lấy BrandDataStatus hiện tại từ DB
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
    # STEP 3: Đánh giá độ mới (Kiểm tra mốc 30 ngày)
    # ===============================
    evaluation = freshness_evaluator.evaluate(status_obj)

    # ===============================
    # STEP 4: Quyết định Cào dữ liệu hay Hiển thị
    # ===============================
    if evaluation.recommended_action in ["NEED_FULL_CRAWL", "NEED_INCREMENTAL_CRAWL"]:
        # Tình huống: Chưa có dữ liệu HOẶC dữ liệu đã quá 30 ngày -> Tạo Job cào mới
        job_status = crawl_orchestrator.handle_decision(
            brand_id=brand_id,
            category_id=category_id,
            recommended_action=evaluation.recommended_action
        )
        
        user_message = MessageMapper.map(evaluation, job_status)
        return EvaluateResponse(
            brand=req.brand,
            category=req.category,
            score=None,
            message=user_message.message,
            status=user_message.severity
        )
    
    # Tình huống: Dữ liệu vẫn MỚI (Dưới 30 ngày) -> Hiển thị kết quả luôn
    # ===============================
    # STEP 5: Load analysis result
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
        score = analysis_row.AvgRating # (Hoặc có thể map với cột Score nếu bạn lưu vào BrandAnalysisResult)
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
        # Fallback an toàn
        status = "PROCESSING"
        message_text = "Hệ thống đang tổng hợp điểm số, vui lòng đợi giây lát..."
        score = None

    return EvaluateResponse(
        brand=req.brand,
        category=req.category,
        score=score,
        message=message_text,
        status=status
    )

