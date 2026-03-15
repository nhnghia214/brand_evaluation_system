# web/ui.py

import os
from dotenv import load_dotenv

from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import jwt
from datetime import datetime, timedelta

from agent.intent_parser import IntentParser
from crawler.db.db_connection import get_connection

from core.layer_c.brand_narrator import narrate_brand_evaluation
from core.layer_c_plus.llm_comparator import compare_brands_with_llm

from core.layer_a.brand_category_registrar import BrandCategoryRegistrar
from core.layer_a.crawl_job_orchestrator import CrawlJobOrchestrator
from core.layer_a.brand_category_resolver import BrandCategoryResolver

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load các biến môi trường từ file .env
load_dotenv()

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

# ==========================================
# CẤU HÌNH BẢO MẬT (Đọc từ .env)
# ==========================================
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")


# ==========================================
# CẤU HÌNH GOOGLE OAUTH2
# ==========================================
config = Config('.env') # Tự động đọc file .env
oauth = OAuth(config)
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

def send_evaluation_email(to_email: str, brand_name: str, evaluation_result: str):
    """Gửi email kết quả phân tích cho User"""
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    
    # Chỉ gửi nếu có email hợp lệ
    if not to_email or "@" not in to_email or not sender_email or not sender_password:
        return

    msg = MIMEMultipart()
    msg['From'] = f"AI Brand Evaluator <{sender_email}>"
    msg['To'] = to_email
    msg['Subject'] = f"📊 Báo cáo phân tích thương hiệu: {brand_name}"

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <h2 style="color: #4F46E5;">Báo cáo từ AI Brand Evaluator</h2>
            <p>Xin chào,</p>
            <p>Hệ thống đã hoàn tất phân tích cho yêu cầu đánh giá thương hiệu <b>{brand_name}</b> của bạn. Dưới đây là kết quả từ hệ thống Multi-Agent:</p>
            <div style="background-color: #f3f4f6; padding: 15px; border-left: 4px solid #8B5CF6; border-radius: 4px; white-space: pre-line;">
                {evaluation_result}
            </div>
            <p style="margin-top: 20px; font-size: 12px; color: #666;">
                Đây là email tự động từ hệ thống. Vui lòng không trả lời.
            </p>
        </body>
    </html>
    """
    msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"[Email] Đã gửi báo cáo cho {to_email} thành công!")
    except Exception as e:
        print(f"[Email Lỗi] Không thể gửi email: {e}")

def create_access_token(data: dict):
    """Tạo JWT Token có hạn 1 ngày"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=1)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request):
    """Lấy thông tin User từ Cookie của Request"""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload # Trả về dict: {"sub": "id", "role": "user/admin", "name": "..."}
    except jwt.PyJWTError:
        return None

# ==========================================
# ROUTES: AUTHENTICATION (XÁC THỰC)
# ==========================================
@router.get("/auth/login")
async def login_google(request: Request):
    """Chuyển hướng người dùng sang trang Đăng nhập của Google"""
    redirect_uri = request.url_for('auth_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri, prompt='select_account')

@router.get("/auth/callback")
async def auth_callback(request: Request):
    """Xử lý kết quả trả về từ Google sau khi đăng nhập thành công"""
    try:
        # Lấy token và thông tin người dùng từ Google
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        if not user_info:
            return RedirectResponse(url="/")
            
        email = user_info.get("email")
        name = user_info.get("name")
        
        # CHỈ ĐỊNH QUYỀN ADMIN DUY NHẤT
        role = "admin" if email == "nhoangnghia2104@gmail.com" else "user"
        
        # Tạo JWT Token nội bộ cho hệ thống của bạn
        user_data = {
            "sub": email, 
            "name": name,
            "role": role,
            "email": email
        }
        
        jwt_token = create_access_token(user_data)
        redirect_url = "/admin" if role == "admin" else "/dashboard"
        
        # Gắn Cookie và điều hướng
        response = RedirectResponse(url=redirect_url, status_code=303)
        response.set_cookie(key="access_token", value=jwt_token, httponly=True, max_age=86400)
        return response
        
    except Exception as e:
        print(f"[OAuth2 Error] Lỗi đăng nhập Google: {e}")
        return RedirectResponse(url="/")

@router.get("/auth/logout", response_class=RedirectResponse)
def logout():
    """Đăng xuất, xóa Cookie và về trang chủ"""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    return response


# ==========================================
# ROUTES: GIAO DIỆN CHÍNH (PAGES)
# ==========================================
@router.get("/", response_class=HTMLResponse)
def landing_page(request: Request):
    """Trang chủ (Không cần đăng nhập)"""
    user = get_current_user(request)
    # Nếu đã đăng nhập, đẩy thẳng vào Dashboard, không bắt xem lại Landing
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("landing.jinja2", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
def user_dashboard(request: Request):
    """Giao diện User (BẮT BUỘC ĐĂNG NHẬP)"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303) # Chưa login -> đuổi về Landing

    return templates.TemplateResponse(
        "dashboard.jinja2",
        {
            "request": request,
            "user": user, # Truyền thông tin user ra UI
            "question": "",
            "answer": None,
            "chart_data": None,
            "debug_intent": None
        }
    )


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, tab: str = "overview"):
    """Giao diện Admin (LẤY DỮ LIỆU THẬT - HỖ TRỢ MULTI-TAB)"""
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        return RedirectResponse(url="/", status_code=303)

    conn = get_connection()
    cursor = conn.cursor()

    # Khởi tạo bộ dữ liệu context cơ bản gửi ra giao diện
    context = {
        "request": request, 
        "user": user,
        "tab": tab
    }

    try:
        # ==================================================
        # TAB 1: THỐNG KÊ CHUNG (Giữ nguyên logic cũ của bạn + Biểu đồ)
        # ==================================================
        if tab == "overview":
            # 1. Đếm tổng số thương hiệu đang quản lý
            cursor.execute("SELECT COUNT(*) AS TotalBrands FROM Brand")
            context["total_brands"] = f"{cursor.fetchone().TotalBrands:,}"

            # 2. Đếm tổng số lượng Review đã cào được
            cursor.execute("SELECT COUNT(*) AS TotalReviews FROM Review")
            context["total_reviews"] = f"{cursor.fetchone().TotalReviews:,}"

            # 3. Đếm số lượng Job đang chạy hoặc chờ
            cursor.execute("SELECT COUNT(*) AS ActiveJobs FROM CrawlJob WHERE JobStatus IN ('PENDING', 'RUNNING')")
            context["active_jobs"] = cursor.fetchone().ActiveJobs

            # 4. Lấy danh sách 10 Job Crawl gần đây nhất
            cursor.execute("""
                SELECT TOP 10 
                    c.JobId, 
                    b.BrandName, 
                    cat.CategoryName, 
                    c.JobStatus, 
                    c.CreatedAt 
                FROM CrawlJob c
                LEFT JOIN Brand b ON c.BrandId = b.BrandId
                LEFT JOIN Category cat ON c.CategoryId = cat.CategoryId
                ORDER BY c.CreatedAt DESC
            """)
            recent_jobs_raw = cursor.fetchall()
            
            # Format lại data để đẩy ra HTML dễ dàng hơn
            recent_jobs = []
            for job in recent_jobs_raw:
                recent_jobs.append({
                    "job_id": job.JobId,
                    "brand": job.BrandName or "N/A",
                    "category": job.CategoryName or "N/A",
                    "status": job.JobStatus,
                    "time": job.CreatedAt.strftime("%d/%m/%Y %H:%M") if job.CreatedAt else "N/A"
                })
            context["recent_jobs"] = recent_jobs

            # 5. DỮ LIỆU BIỂU ĐỒ: Đếm số Review thu thập được theo 7 ngày gần nhất
            cursor.execute("""
                SELECT TOP 7 
                    CAST(CollectedAt AS DATE) as CrawlDate, 
                    COUNT(ReviewId) as DailyReviews
                FROM Review
                WHERE CollectedAt IS NOT NULL
                GROUP BY CAST(CollectedAt AS DATE)
                ORDER BY CrawlDate ASC
            """)
            chart_raw = cursor.fetchall()
            
            # Tách ra 2 mảng (nhãn ngày và số liệu) cho Chart.js
            context["chart_labels"] = [row.CrawlDate.strftime("%d/%m") for row in chart_raw] if chart_raw else []
            context["chart_data"] = [row.DailyReviews for row in chart_raw] if chart_raw else []

        # ==================================================
        # TAB 2: QUẢN LÝ JOB CRAWL (Lấy toàn bộ danh sách)
        # ==================================================
        elif tab == "jobs":
            cursor.execute("""
                SELECT c.JobId, b.BrandName, cat.CategoryName, c.JobStatus, c.CreatedAt
                FROM CrawlJob c
                LEFT JOIN Brand b ON c.BrandId = b.BrandId
                LEFT JOIN Category cat ON c.CategoryId = cat.CategoryId
                ORDER BY c.CreatedAt DESC
            """)
            context["all_jobs"] = cursor.fetchall()

        # ==================================================
        # TAB 3: LOGS HỆ THỐNG (Lấy từ DeepCrawlState)
        # ==================================================
        elif tab == "logs":
            cursor.execute("""
                SELECT TOP 50 DeepCrawlId, ProductId, ReviewTier, BatchIndex, BatchStatus, ReviewsCollected, UpdatedAt, CreatedAt
                FROM DeepCrawlState
                ORDER BY ISNULL(UpdatedAt, CreatedAt) DESC
            """)
            context["system_logs"] = cursor.fetchall()

        # ==================================================
        # TAB 4: QUẢN LÝ THƯƠNG HIỆU (BRANDS)
        # ==================================================
        elif tab == "brands":
            # Lấy danh sách Danh mục cho Combobox
            cursor.execute("SELECT CategoryId, CategoryName FROM Category ORDER BY CategoryName")
            context["categories"] = cursor.fetchall()

            # Lấy danh sách Thương hiệu
            cursor.execute("SELECT BrandId, BrandName, CreatedAt FROM Brand ORDER BY BrandId DESC")
            context["all_brands"] = cursor.fetchall()

    except Exception as e:
        print(f"Lỗi truy vấn Admin: {e}")
        # Gán giá trị rỗng để tránh lỗi sập UI
        if tab == "overview":
            context.update({"total_brands": "0", "total_reviews": "0", "active_jobs": 0, "recent_jobs": [], "chart_labels": [], "chart_data": []})
        elif tab == "jobs":
            context["all_jobs"] = []
        elif tab == "logs":
            context["system_logs"] = []
            
    finally:
        conn.close()

    return templates.TemplateResponse("admin.jinja2", context)


# ==========================================
# ADMIN ACTIONS: ĐỔI TRẠNG THÁI JOB
# ==========================================
@router.post("/admin/job/{job_id}/action", response_class=RedirectResponse)
def admin_job_action(request: Request, job_id: int, action: str = Form(...)):
    """API để Admin Tạm dừng, Tiếp tục hoặc Hủy Job"""
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        return RedirectResponse(url="/", status_code=303)

    # Map từ 'action' của UI sang 'JobStatus' của Database
    status_map = {
        "pause": "PAUSED",
        "resume": "PENDING", # Đưa về PENDING để Scheduler tự động nhặt lại lên RUNNING
        "cancel": "FAILED"   # Hoặc thêm trạng thái CANCELED nếu DB bạn hỗ trợ
    }

    new_status = status_map.get(action)
    if new_status:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Cập nhật trạng thái Job trong Database
            cursor.execute("""
                UPDATE CrawlJob 
                SET JobStatus = ? 
                WHERE JobId = ?
            """, (new_status, job_id))
            conn.commit()
            print(f"[Admin Action] Đã chuyển Job #{job_id} sang trạng thái {new_status}")
        except Exception as e:
            print(f"[Admin Action Error] Lỗi cập nhật Job: {e}")
        finally:
            conn.close()

    # Làm xong thì hất người dùng quay lại Tab Jobs
    return RedirectResponse(url="/admin?tab=jobs", status_code=303)


# ==========================================
# CORE LOGIC: XỬ LÝ CÂU HỎI (BẮT BUỘC ĐĂNG NHẬP)
# ==========================================
@router.post("/ask", response_class=HTMLResponse)
def ask(request: Request, question: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

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
            return templates.TemplateResponse("dashboard.jinja2", {
                "request": request, "user": user, "question": question,
                "answer": "❓ Bạn muốn đánh giá **thương hiệu nào**? Vui lòng nêu rõ tên thương hiệu.",
                "chart_data": None, "debug_intent": debug_intent
            })

        brand_id, is_new_brand = registrar.get_or_create_brand_with_flag(brand)
        category_id = registrar.get_or_create_category(category) if category is not None else None

        if is_new_brand:
            orchestrator.handle_decision(brand_id=brand_id, category_id=category_id, recommended_action="NEED_FULL_CRAWL")
            return templates.TemplateResponse("dashboard.jinja2", {
                "request": request, "user": user, "question": question,
                "answer": "🛠️ Hệ thống đang thu thập dữ liệu cho thương hiệu này. Vui lòng quay lại sau để xem kết quả.",
                "chart_data": None, "debug_intent": debug_intent
            })

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Score, PositiveRate, NegativeRate FROM BrandAnalysisResult
            WHERE BrandId = ? AND (? IS NULL OR CategoryId = ?)
        """, (brand_id, category_id, category_id))
        rows = cursor.fetchall()

        cursor.execute("""
            SELECT SUM(TotalReviews) AS TotalReviews FROM BrandDataStatus
            WHERE BrandId = ? AND (? IS NULL OR CategoryId = ?)
        """, (brand_id, category_id, category_id))
        status_row = cursor.fetchone()
        conn.close()

        scores = [r.Score for r in rows if r.Score is not None]
        pos_rates = [r.PositiveRate for r in rows if r.PositiveRate is not None]
        neg_rates = [r.NegativeRate for r in rows if r.NegativeRate is not None]

        if not scores:
            orchestrator.handle_decision(brand_id=brand_id, category_id=category_id, recommended_action="NEED_FULL_CRAWL")
            answer = "🛠️ Hệ thống đang thu thập dữ liệu cho thương hiệu này. Vui lòng quay lại sau để xem kết quả."
        else:
            avg_score = round(sum(scores) / len(scores), 2)
            avg_pos = sum(pos_rates) / len(pos_rates) if pos_rates else None
            avg_neg = sum(neg_rates) / len(neg_rates) if neg_rates else None

            answer = narrate_brand_evaluation(
                brand=brand, category=category or "toàn bộ danh mục", score=avg_score,
                avg_rating=None, positive_rate=avg_pos, negative_rate=avg_neg,
                total_reviews=status_row.TotalReviews or 0
            )

            if user and user.get("email"):
                send_evaluation_email(user["email"], brand, answer)

        return templates.TemplateResponse("dashboard.jinja2", {
            "request": request, "user": user, "question": question, "answer": answer, "chart_data": None, "debug_intent": debug_intent
        })

    # ======================================================
    # CASE 2 — COMPARE BRANDS (Giữ nguyên logic cũ, chỉ thêm "user": user)
    # ======================================================
    if intent_data["intent"] == "COMPARE_BRANDS":
        brands = intent_data.get("brands", [])
        brand_id_map = {}
        for b in brands:
            r = resolver.resolve(b, None)
            if r.status == "VALID": brand_id_map[b] = r.brand_id

        if len(brand_id_map) < 2:
            return templates.TemplateResponse("dashboard.jinja2", {"request": request, "user": user, "question": question, "answer": "Không đủ thương hiệu hợp lệ để so sánh.", "chart_data": None, "debug_intent": debug_intent})

        common_category_names = resolver.get_common_categories(list(brand_id_map.values()))

        if not common_category_names:
            return templates.TemplateResponse("dashboard.jinja2", {"request": request, "user": user, "question": question, "answer": "Hai thương hiệu không có danh mục chung để so sánh.", "chart_data": None, "debug_intent": debug_intent})

        brand_summaries, trend_info = [], {}
        for brand, brand_id in brand_id_map.items():
            scores, total_reviews_sum = [], 0
            for category_name in common_category_names:
                category_id = resolver.get_category_id_by_name(brand_id, category_name)
                if not category_id: continue

                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT Score FROM BrandAnalysisResult WHERE BrandId = ? AND CategoryId = ?", (brand_id, category_id))
                analysis = cursor.fetchone()
                cursor.execute("SELECT TotalReviews FROM BrandDataStatus WHERE BrandId = ? AND CategoryId = ?", (brand_id, category_id))
                status = cursor.fetchone()
                conn.close()

                if not analysis or analysis.Score is None or not status: continue
                scores.append(analysis.Score)
                total_reviews_sum += status.TotalReviews

            if not scores: continue
            avg_score = round(sum(scores) / len(scores), 2)
            brand_summaries.append({"brand": brand, "score": avg_score, "total_reviews": total_reviews_sum})
            trend_info[brand] = {"category_count": len(resolver.get_categories_of_brand(brand_id)), "total_reviews": total_reviews_sum}

        if len(brand_summaries) < 2:
            answer, chart_data = "Không đủ dữ liệu để so sánh các thương hiệu.", None
        else:
            answer = compare_brands_with_llm(brand_summaries=brand_summaries, trend_info=trend_info, question=question)

            if user and user.get("email"):
                send_evaluation_email(user["email"], brand, answer)

            chart_data = {
                "labels": [b["brand"] for b in brand_summaries],
                "scores": [b["score"] for b in brand_summaries],
                "total_reviews": [b["total_reviews"] for b in brand_summaries]
            }

        return templates.TemplateResponse("dashboard.jinja2", {"request": request, "user": user, "question": question, "answer": answer, "chart_data": chart_data, "debug_intent": debug_intent})

    return templates.TemplateResponse("dashboard.jinja2", {"request": request, "user": user, "question": question, "answer": "Không hiểu được câu hỏi.", "chart_data": None, "debug_intent": debug_intent})