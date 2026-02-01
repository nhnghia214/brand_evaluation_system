from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from agent.intent_parser import IntentParser

from crawler.db.db_connection import get_connection

from core.layer_c.brand_narrator import narrate_brand_evaluation
from core.layer_c_plus.llm_comparator import compare_brands_with_llm

from core.layer_a.brand_category_registrar import BrandCategoryRegistrar
from core.layer_a.crawl_job_orchestrator import CrawlJobOrchestrator
from core.layer_a.brand_category_resolver import BrandCategoryResolver

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.jinja2",
        {
            "request": request,
            "question": "",
            "answer": None,
            "chart_data": None,
            "debug_intent": None
        }
    )


@router.post("/ask", response_class=HTMLResponse)
def ask(request: Request, question: str = Form(...)):
    intent_data = IntentParser.parse(question)
    debug_intent = intent_data
    
    registrar = BrandCategoryRegistrar()
    orchestrator = CrawlJobOrchestrator()
    resolver = BrandCategoryResolver()

    # ======================================================
    # CASE 1 — EVALUATE BRAND
    # ======================================================
    if intent_data["intent"] == "EVALUATE_BRAND":
        brand = intent_data.get("brand")
        category = intent_data.get("category")

        if not brand:
            return templates.TemplateResponse(
                "index.jinja2",
                {
                    "request": request,
                    "question": question,
                    "answer": (
                        "❓ Bạn muốn đánh giá **thương hiệu nào**? "
                        "Vui lòng nêu rõ tên thương hiệu."
                    ),
                    "chart_data": None,
                    "debug_intent": debug_intent
                }
            )

        # 🔥 ALWAYS register brand/category (cold-start safe)
        brand_id = registrar.get_or_create_brand(brand)
        category_id = (
            registrar.get_or_create_category(category)
            if category is not None
            else None
        )

        # 🔥 Check data availability
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT Score
            FROM BrandAnalysisResult
            WHERE BrandId = ? AND (? IS NULL OR CategoryId = ?)
        """, (brand_id, category_id, category_id))

        rows = cursor.fetchall()

        cursor.execute("""
            SELECT SUM(TotalReviews) AS TotalReviews
            FROM BrandDataStatus
            WHERE BrandId = ? AND (? IS NULL OR CategoryId = ?)
        """, (brand_id, category_id, category_id))

        status_row = cursor.fetchone()
        conn.close()

        scores = [r.Score for r in rows if r.Score is not None]

        # ===============================
        # NO DATA → CREATE / ENSURE CRAWL
        # ===============================
        if not scores:
            orchestrator.handle_decision(
                brand_id=brand_id,
                category_id=category_id,
                recommended_action="NEED_FULL_CRAWL"
            )

            answer = (
                "🛠️ Hệ thống đang thu thập dữ liệu cho thương hiệu này. "
                "Vui lòng quay lại sau để xem kết quả đánh giá."
            )

        else:
            avg_score = round(sum(scores) / len(scores), 2)
            answer = narrate_brand_evaluation(
                brand=brand,
                category=category or "toàn bộ danh mục",
                score=avg_score,
                avg_rating=None,
                positive_rate=None,
                negative_rate=None,
                total_reviews=status_row.TotalReviews or 0
            )

        return templates.TemplateResponse(
            "index.jinja2",
            {
                "request": request,
                "question": question,
                "answer": answer,
                "chart_data": None,
                "debug_intent": debug_intent
            }
        )

    # ======================================================
    # CASE 2 — COMPARE BRANDS
    # ======================================================
    if intent_data["intent"] == "COMPARE_BRANDS":
        brands = intent_data.get("brands", [])

        brand_id_map = {}
        for b in brands:
            r = resolver.resolve(b, None)
            if r.status == "VALID":
                brand_id_map[b] = r.brand_id

        if len(brand_id_map) < 2:
            return templates.TemplateResponse(
                "index.jinja2",
                {
                    "request": request,
                    "question": question,
                    "answer": "Không đủ thương hiệu hợp lệ để so sánh.",
                    "chart_data": None,
                    "debug_intent": debug_intent
                }
            )

        common_category_names = resolver.get_common_categories(
            list(brand_id_map.values())
        )

        if not common_category_names:
            return templates.TemplateResponse(
                "index.jinja2",
                {
                    "request": request,
                    "question": question,
                    "answer": "Hai thương hiệu không có danh mục chung để so sánh.",
                    "chart_data": None,
                    "debug_intent": debug_intent
                }
            )

        brand_summaries = []
        trend_info = {}

        for brand, brand_id in brand_id_map.items():
            scores = []
            total_reviews_sum = 0

            for category_name in common_category_names:
                category_id = resolver.get_category_id_by_name(
                    brand_id, category_name
                )
                if not category_id:
                    continue

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT Score
                    FROM BrandAnalysisResult
                    WHERE BrandId = ? AND CategoryId = ?
                """, (brand_id, category_id))
                analysis = cursor.fetchone()

                cursor.execute("""
                    SELECT TotalReviews
                    FROM BrandDataStatus
                    WHERE BrandId = ? AND CategoryId = ?
                """, (brand_id, category_id))
                status = cursor.fetchone()

                conn.close()

                if not analysis or analysis.Score is None or not status:
                    continue

                scores.append(analysis.Score)
                total_reviews_sum += status.TotalReviews

            if not scores:
                continue

            avg_score = round(sum(scores) / len(scores), 2)

            brand_summaries.append({
                "brand": brand,
                "score": avg_score,
                "total_reviews": total_reviews_sum
            })

            trend_info[brand] = {
                "category_count": len(
                    resolver.get_categories_of_brand(brand_id)
                ),
                "total_reviews": total_reviews_sum
            }

        if len(brand_summaries) < 2:
            answer = "Không đủ dữ liệu để so sánh các thương hiệu."
            chart_data = None
        else:
            answer = compare_brands_with_llm(
                brand_summaries=brand_summaries,
                trend_info=trend_info,
                question=question
            )

            chart_data = {
                "labels": [b["brand"] for b in brand_summaries],
                "scores": [b["score"] for b in brand_summaries],
                "total_reviews": [b["total_reviews"] for b in brand_summaries]
            }

        return templates.TemplateResponse(
            "index.jinja2",
            {
                "request": request,
                "question": question,
                "answer": answer,
                "chart_data": chart_data,
                "debug_intent": debug_intent
            }
        )

    # ======================================================
    # FALLBACK
    # ======================================================
    return templates.TemplateResponse(
        "index.jinja2",
        {
            "request": request,
            "question": question,
            "answer": "Không hiểu được câu hỏi.",
            "chart_data": None,
            "debug_intent": debug_intent
        }
    )
