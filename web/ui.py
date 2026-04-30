# web/ui.py

import os
import uuid
from dotenv import load_dotenv
import json
from openai import AsyncOpenAI
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from fastapi import APIRouter, Request, Form, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import jwt
from datetime import datetime, timedelta

import resend # Thư viện gửi mail lách luật DigitalOcean qua cổng 443

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
from web.schemas import AnalysisFormRequest

import time
from payos import PayOS
from payos.type import ItemData, PaymentData
from pydantic import BaseModel


# Load các biến môi trường từ file .env
load_dotenv()

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

# ==========================================
# CẤU HÌNH BẢO MẬT (Đọc từ .env)
# ==========================================
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# Khởi tạo PayOS Client
payos_client = PayOS(
    client_id=os.getenv("PAYOS_CLIENT_ID", ""),
    api_key=os.getenv("PAYOS_API_KEY", ""),
    checksum_key=os.getenv("PAYOS_CHECKSUM_KEY", "")
)


def mask_sensitive_data(text: str, mask_type: str = "text") -> str:
    """Che giấu một phần thông tin cá nhân"""
    if not text: return ""
    if mask_type == "email":
        parts = text.split('@')
        if len(parts) == 2:
            name, domain = parts
            return f"{name[:3]}***@{domain}"
        return "***"
    elif mask_type == "phone":
        return f"{text[:3]}****{text[-3:]}" if len(text) >= 9 else "***"
    else:
        return f"{text[:4]}***" if len(text) > 4 else "***"

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

def send_evaluation_email(to_email: str, full_name: str, brand_list: list, report_id: str):
    """Gửi email chứa Link báo cáo cho User"""
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")

    if not to_email or "@" not in to_email or not sender_email or not sender_password:
        return

    brands_str = ", ".join(brand_list)
    mode_text = "So sánh" if len(brand_list) > 1 else "Đánh giá"
    
    msg = MIMEMultipart()
    msg['From'] = f"Tiên Phong Tech <{sender_email}>"
    msg['To'] = to_email
    msg['Subject'] = f"📊 Báo cáo {mode_text} thương hiệu: {brands_str}"
    
    # Link dẫn tới trang báo cáo (sẽ làm ở Bước 4)
    report_link = f"http://127.0.0.1:8000/report/{report_id}"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #4F46E5;">Báo cáo Phân tích Thương hiệu</h2>
        <p>Dear <b>{full_name}</b>,</p>
        <p>Chúng tôi đã nhận được yêu cầu <b>{mode_text}</b> của bạn cho (các) thương hiệu: <b>{brands_str}</b>.</p>
        <p>Hệ thống AI Đa tác tử của Công ty TNHH MTV Công nghệ Kỹ thuật Tiên Phong đã hoàn tất quá trình cào dữ liệu, làm sạch và phân tích cảm xúc chuyên sâu từ hàng ngàn bình luận thực tế trên các sàn TMĐT.</p>
        <p>Để xem chi tiết Báo cáo tổng hợp, điểm số xếp hạng và các biểu đồ phân tích kỹ thuật, vui lòng truy cập vào liên kết bảo mật dưới đây:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{report_link}" style="background-color: #3498db; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Xem Báo Cáo Chi Tiết</a>
        </div>

        <p>Nếu có bất kỳ thắc mắc nào, xin vui lòng liên hệ với chúng tôi.</p>
        <hr style="border: none; border-top: 1px solid #eee;">
        <p style="font-size: 12px; color: #777;">
            Trân trọng,<br>
            <b>Đội ngũ Phân tích Dữ liệu</b><br>
            Công ty TNHH MTV Công nghệ Kỹ thuật Tiên Phong
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
    """Lấy thông tin User từ Cookie và đối chiếu Database để lấy Token/Tier"""
    token = request.cookies.get("access_token")
    if not token: return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # 🚀 ĐỌC DB ĐỂ LẤY SỐ DƯ TOKEN VÀ GÓI VIP THỰC TẾ
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT Goi_DichVu, So_Token, Ngay_HetHan FROM NguoiDung WHERE Email = ?", (payload["email"],))
        db_info = cursor.fetchone()
        
        if db_info:
            tier = db_info.Goi_DichVu
            # Nếu VIP hết hạn -> Tự động rớt xuống BASIC
            if tier == 'VIP' and db_info.Ngay_HetHan and datetime.now() > db_info.Ngay_HetHan:
                tier = 'BASIC'
                
            payload["tier"] = tier
            payload["token"] = db_info.So_Token or 0
            
            # Ghi đè vô hạn cho Admin
            if payload["email"] == "nhoangnghia2104@gmail.com":
                payload["tier"] = 'VIP'
                payload["token"] = 9999
        conn.close()
        return payload
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

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT Da_Khoa FROM NguoiDung WHERE Email = ?", (email,))
        user_db = cursor.fetchone()
        conn.close()

        if user_db and user_db.Da_Khoa:
            # Nếu bị khóa, trả về trang Lỗi luôn, không cấp Token
            return HTMLResponse(f"""
            <div style="background-color: #0B0F19; height: 100vh; display: flex; align-items: center; justify-content: center; font-family: sans-serif; color: white;">
                <div style="background-color: #1F2937; padding: 40px; border-radius: 10px; text-align: center; border-top: 4px solid #EF4444; max-width: 500px;">
                    <h2 style="color: #EF4444; margin-bottom: 15px;">🚫 TÀI KHOẢN BỊ TẠM KHÓA</h2>
                    <p style="color: #D1D5DB; line-height: 1.6;">Tài khoản <b>{email}</b> đã bị khóa do vi phạm chính sách nội dung nhiều lần.</p>
                    <p style="color: #D1D5DB; line-height: 1.6; margin-bottom: 25px;">Vui lòng kiểm tra hộp thư email của bạn để lấy liên kết khiếu nại.</p>
                    <a href="/" style="background-color: #374151; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none;">Quay lại Trang chủ</a>
                </div>
            </div>
            """)

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
        # ĐẾM SỐ ĐƠN KHIẾU NẠI CHỜ XỬ LÝ (Gửi ra mọi Tab để hiện chuông đỏ)
        cursor.execute("SELECT COUNT(*) AS PendingAppeals FROM Don_KhieuNai WHERE TrangThai_GiaiQuyet = N'Chờ xử lý'")
        context["pending_appeals"] = cursor.fetchone().PendingAppeals

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
                WITH RecentData AS (
                    SELECT TOP 7 
                        CAST(CollectedAt AS DATE) as CrawlDate, 
                        COUNT(ReviewId) as DailyReviews
                    FROM Review
                    WHERE CollectedAt IS NOT NULL
                      AND CAST(CollectedAt AS DATE) <= CAST(GETDATE() AS DATE)
                    GROUP BY CAST(CollectedAt AS DATE)
                    ORDER BY CAST(CollectedAt AS DATE) DESC
                )
                SELECT CrawlDate, DailyReviews 
                FROM RecentData 
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

        # ==================================================
        # TAB 5: QUẢN LÝ YÊU CẦU TỪ NGƯỜI DÙNG (REQUESTS)
        # ==================================================
        elif tab == "requests":
            # Lấy tham số tìm kiếm
            search = request.query_params.get("search", "").strip()
            date_from = request.query_params.get("date_from", "")
            date_to = request.query_params.get("date_to", "")

            # Xây dựng Query linh hoạt
            query = """
                SELECT r.Ma_YeuCau, u.HoTen, r.Email, r.SoDienThoai, r.DiaChi, r.CheDo, r.ThuongHieu, r.TrangThai_AI, r.NgayGui
                FROM NhatKy_YeuCau r
                JOIN NguoiDung u ON r.Email = u.Email
                WHERE u.Da_Khoa = 0  -- Chỉ hiện tài khoản đang hoạt động
            """
            params = []

            if search:
                query += " AND (u.HoTen LIKE ? OR r.Email LIKE ? OR r.ThuongHieu LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
            
            if date_from:
                query += " AND CAST(r.NgayGui AS DATE) >= ?"
                params.append(date_from)
                
            if date_to:
                query += " AND CAST(r.NgayGui AS DATE) <= ?"
                params.append(date_to)
            # Nếu có date_from mà không có date_to, query vẫn lấy từ ngày đó trở đi. 
            # Nếu muốn chọn 1 ngày thì gửi date_from và date_to giống nhau.

            query += " ORDER BY r.NgayGui DESC"
            cursor.execute(query, tuple(params))
            raw_requests = cursor.fetchall()

            # Che giấu dữ liệu trước khi gửi ra UI
            processed_requests = []
            for req_row in raw_requests:
                processed_requests.append({
                    "id": req_row.Ma_YeuCau,
                    "name": req_row.HoTen,
                    "masked_email": mask_sensitive_data(req_row.Email, "email"),
                    "masked_phone": mask_sensitive_data(req_row.SoDienThoai, "phone"),
                    "masked_address": mask_sensitive_data(req_row.DiaChi, "text"),
                    "full_email": req_row.Email,
                    "full_phone": req_row.SoDienThoai,
                    "full_address": req_row.DiaChi,
                    "mode": req_row.CheDo,
                    "brands": req_row.ThuongHieu,
                    "status": req_row.TrangThai_AI,
                    "date": req_row.NgayGui.strftime("%d/%m/%Y %H:%M") if req_row.NgayGui else ""
                })
            context["active_requests"] = processed_requests
            context["search_params"] = {"search": search, "date_from": date_from, "date_to": date_to}

            # Lấy danh sách Tài Khoản Đã Khóa (Blacklist)
            cursor.execute("""
                SELECT Email, HoTen, NgayTao 
                FROM NguoiDung 
                WHERE Da_Khoa = 1
            """)
            context["locked_users"] = cursor.fetchall()

            # Lấy lịch sử vi phạm của những tài khoản đã khóa
            locked_history = {}
            if context["locked_users"]:
                locked_emails = [u.Email for u in context["locked_users"]]
                placeholders = ','.join(['?'] * len(locked_emails))
                cursor.execute(f"""
                    SELECT Ma_YeuCau, Email, ThuongHieu, TrangThai_AI, NgayGui 
                    FROM NhatKy_YeuCau 
                    WHERE Email IN ({placeholders}) AND TrangThai_AI = N'Vi phạm'
                    ORDER BY NgayGui DESC
                """, tuple(locked_emails))
                for row in cursor.fetchall():
                    if row.Email not in locked_history:
                        locked_history[row.Email] = []
                    locked_history[row.Email].append(row)
            context["locked_history"] = locked_history

            # Lấy danh sách Khiếu nại chờ xử lý
            cursor.execute("""
                SELECT k.Ma_KhieuNai, k.Email, u.HoTen, k.NoiDung_KhieuNai, k.NgayGhiNhan 
                FROM Don_KhieuNai k
                JOIN NguoiDung u ON k.Email = u.Email
                WHERE k.TrangThai_GiaiQuyet = N'Chờ xử lý'
                ORDER BY k.NgayGhiNhan ASC
            """)
            context["appeals"] = cursor.fetchall()

        # ==================================================
        # TAB 6: THỐNG KÊ & BÁO CÁO TÀI CHÍNH
        # ==================================================
        elif tab == "revenue":
            # 1. Thống kê tổng quan
            cursor.execute("SELECT SUM(SoTien) AS Total, COUNT(*) AS Count FROM DonHang WHERE TrangThai = 'SUCCESS'")
            summary = cursor.fetchone()
            context["total_revenue"] = f"{summary.Total or 0:,} đ"
            context["total_orders"] = summary.Count

            # 2. Biến động doanh thu 7 ngày gần nhất
            cursor.execute("""
                SELECT CAST(NgayTao AS DATE) as Date, SUM(SoTien) as DailyTotal
                FROM DonHang WHERE TrangThai = 'SUCCESS'
                AND NgayTao >= CAST(DATEADD(day, -7, GETDATE()) AS DATE)
                GROUP BY CAST(NgayTao AS DATE) ORDER BY Date ASC
            """)
            chart_raw = cursor.fetchall()
            context["rev_labels"] = [r.Date.strftime("%d/%m") for r in chart_raw]
            context["rev_data"] = [int(r.DailyTotal) for r in chart_raw]

            # 3. Phân bổ theo gói dịch vụ (Pie Chart)
            # Khởi tạo mặc định 4 gói chuẩn để luôn xuất hiện trên biểu đồ (kể cả khi số lượng = 0)
            stats_dict = {
                "Gói VIP": 0,
                "50 Token": 0,
                "120 Token": 0,
                "280 Token": 0
            }
            
            cursor.execute("""
                SELECT Goi_DichVu, COUNT(*) as Qty FROM DonHang 
                WHERE TrangThai = 'SUCCESS' GROUP BY Goi_DichVu
            """)
            
            for r in cursor.fetchall():
                code = str(r.Goi_DichVu).upper()
                if "TOKEN_50" in code:
                    stats_dict["50 Token"] += r.Qty
                elif "TOKEN_120" in code:
                    stats_dict["120 Token"] += r.Qty
                elif "TOKEN_280" in code:
                    stats_dict["280 Token"] += r.Qty
                elif "VIP" in code:
                    stats_dict["Gói VIP"] += r.Qty
                elif "BASIC" in code:
                    # Gom các đơn BASIC cũ trong quá trình test
                    stats_dict["Cơ bản (Cũ)"] = stats_dict.get("Cơ bản (Cũ)", 0) + r.Qty
                else:
                    stats_dict[code] = stats_dict.get(code, 0) + r.Qty

            # Trả về List các Dictionary để Jinja2 / Chart.js parse sang JSON
            context["package_stats"] = [{"Goi_DichVu": k, "Qty": v} for k, v in stats_dict.items()]
            
            # Ép kiểu Row thành Dictionary để Jinja2 có thể parse sang JSON
            context["package_stats"] = [{"Goi_DichVu": r.Goi_DichVu, "Qty": r.Qty} for r in cursor.fetchall()]

            # 4. Danh sách giao dịch để lọc/xuất báo cáo
            cursor.execute("SELECT * FROM DonHang ORDER BY NgayTao DESC")
            context["all_transactions"] = cursor.fetchall() 

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


# ==========================================
# GỬI MAIL KHÓA TÀI KHOẢN KHIẾU NẠI
# ==========================================
def send_lock_email(to_email: str, full_name: str):
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    if not to_email or not sender_email: return

    msg = MIMEMultipart()
    msg['From'] = f"Tiên Phong Tech <{sender_email}>"
    msg['To'] = to_email
    msg['Subject'] = "🚨 Thông báo Tạm khóa tài khoản truy cập hệ thống AI"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #EF4444;">Thông báo Tạm khóa Tài khoản</h2>
        <p>Kính gửi <b>{full_name}</b>,</p>
        <p>Hệ thống Trí tuệ Nhân tạo Gác cổng (Moderator Agent) của chúng tôi nhận thấy tài khoản của bạn đã có từ 3 lần trở lên gửi yêu cầu phân tích chứa nội dung không phù hợp (Spam, câu hỏi không liên quan, hoặc từ ngữ vi phạm tiêu chuẩn).</p>
        <p>Để bảo vệ tài nguyên hệ thống, quyền truy cập của bạn đã bị <b>TẠM KHÓA</b>.</p>
        <p>Nếu bạn cho rằng AI của chúng tôi đã đánh giá nhầm, xin vui lòng gửi yêu cầu xem xét lại thông qua Liên kết khiếu nại dưới đây:</p>
        <a href="http://127.0.0.1:8000/appeal?email={to_email}" style="display:inline-block; padding: 10px 20px; background-color: #F97316; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 10px;">Gửi Đơn Khiếu Nại</a>
    </div>
    """
    msg.attach(MIMEText(html_content, 'html'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"[Email Lỗi] Không thể gửi email khóa: {e}")

# ==========================================
# AGENT KIỂM DUYỆT ĐẦU VÀO (MODERATOR)
# ==========================================
async def check_request_validity(brands: list) -> tuple[bool, str]:
    """Sử dụng GPT-4o-mini để kiểm duyệt đầu vào từ form"""
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = f"""
    Bạn là một Moderator kiểm duyệt dữ liệu. Người dùng yêu cầu hệ thống phân tích các từ khóa sau để tìm thương hiệu/sản phẩm: {brands}.
    Quy tắc:
    1. Nếu từ khóa là tên thương hiệu/sản phẩm thật (VD: Samsung, Colorkey, Mac, Asus, giày dép, son môi...), hoặc danh mục hợp lý -> Hợp lệ.
    2. NẾU từ khóa là câu hỏi giao tiếp (VD: "thời tiết hôm nay thế nào", "xin chào"), spam chữ vô nghĩa ("asdfg"), hoặc từ ngữ thô tục -> KHÔNG hợp lệ.
    Trả về ĐÚNG định dạng JSON:
    {{"is_valid": true/false, "reason": "Lý do ngắn gọn nếu false"}}
    """
    try:
        res = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=150,
            temperature=0.0
        )
        data = json.loads(res.choices[0].message.content)
        return data.get("is_valid", True), data.get("reason", "")
    except Exception as e:
        print(f"Lỗi Moderator: {e}")
        return True, "Bỏ qua kiểm duyệt do lỗi AI"

# ==========================================
# API NHẬN REQUEST: ĐÃ TÍCH HỢP DB VÀ MODERATOR
# ==========================================
REPORT_CACHE = {}

@router.post("/api/submit-request")
async def submit_analysis_request(req: AnalysisFormRequest, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập")

    email = user["email"]
    full_name = req.fullName
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. LẤY THÔNG TIN USER (THÊM SỐ TOKEN)
        cursor.execute("SELECT Da_Khoa, Goi_DichVu, Ngay_HetHan, So_Token FROM NguoiDung WHERE Email = ?", (email,))
        user_db = cursor.fetchone()
        is_admin = (email == "nhoangnghia2104@gmail.com")

        if not user_db:
            # QUÀ TÂN THỦ: 20 Token + VIP 2 Ngày
            ngay_tao = datetime.now()
            if is_admin:
                goi_dich_vu, tokens, ngay_het_han = 'VIP', 9999, None
            else:
                goi_dich_vu, tokens, ngay_het_han = 'VIP', 20, ngay_tao + timedelta(days=2)
                
            cursor.execute("""
                INSERT INTO NguoiDung (Email, HoTen, Da_Khoa, NgayTao, Goi_DichVu, Ngay_KichHoat, Ngay_HetHan, So_Token) 
                VALUES (?, ?, 0, ?, ?, ?, ?, ?)
            """, (email, full_name, ngay_tao, ngay_tao, goi_dich_vu, ngay_tao, ngay_het_han, tokens))
            conn.commit()
            is_locked, user_tier = False, goi_dich_vu
        else:
            is_locked = bool(user_db.Da_Khoa)
            user_tier = 'VIP' if is_admin else user_db.Goi_DichVu
            tokens = 9999 if is_admin else (user_db.So_Token or 0)
            
            # Xử lý rớt hạng VIP
            if not is_admin and user_tier == 'VIP' and user_db.Ngay_HetHan and datetime.now() > user_db.Ngay_HetHan:
                user_tier = 'BASIC'

        # 2. CHẶN KHÓA TÀI KHOẢN (Giữ nguyên)
        if is_locked:
            return {"status": "error", "message": "Tài khoản của bạn đã bị khóa do vi phạm nhiều lần."}

        # 3. TÍNH TOÁN VÀ TRỪ TOKEN (1 Thương hiệu = 10 Token)
        tokens_needed = len(req.brands) * 10
        if tokens < tokens_needed:
            return {
                "status": "out_of_token", 
                "message": f"Nhiệm vụ này cần {tokens_needed} Token. Số dư của bạn là {tokens}. Vui lòng nạp thêm năng lượng!"
            }
        
        # Gọi Moderator Kiểm duyệt (Giữ nguyên)
        is_valid, reason = await check_request_validity(req.brands)
        ai_status = "Hợp lệ" if is_valid else "Vi phạm"

        # 5. LƯU YÊU CẦU VÀO NHẬT KÝ
        brands_str = ", ".join(req.brands)
        cursor.execute("""
            INSERT INTO NhatKy_YeuCau (Email, SoDienThoai, DiaChi, CheDo, ThuongHieu, TrangThai_AI)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (email, req.phone, req.address, req.mode, brands_str, ai_status))
        conn.commit()

        # 6. XỬ LÝ NẾU VI PHẠM
        if not is_valid:
            cursor.execute("SELECT COUNT(*) AS SpamCount FROM NhatKy_YeuCau WHERE Email = ? AND TrangThai_AI = N'Vi phạm'", (email,))
            spam_count = cursor.fetchone().SpamCount
            
            if spam_count >= 3:
                cursor.execute("UPDATE NguoiDung SET Da_Khoa = 1 WHERE Email = ?", (email,))
                conn.commit()
                send_lock_email(to_email=email, full_name=full_name)
                return {"status": "error", "message": f"Yêu cầu chứa nội dung không hợp lệ. Tài khoản đã bị khóa do vi phạm {spam_count} lần."}
            
            return {"status": "error", "message": f"Yêu cầu bị từ chối (Lý do: {reason}). Cảnh báo vi phạm lần {spam_count}/3."}
        
        # 7. TRỪ TOKEN NẾU HỢP LỆ VÀ ĐI TIẾP
        if not is_admin and is_valid:
            cursor.execute("UPDATE NguoiDung SET So_Token = So_Token - ? WHERE Email = ?", (tokens_needed, email))
            conn.commit()

    except Exception as e:
        print(f"Lỗi DB ở Submit Request: {e}")
        return {"status": "error", "message": "Hệ thống đang quá tải hoặc lỗi cơ sở dữ liệu. Vui lòng thử lại sau!"}
    finally:
        conn.close()

    # ========================================================
    # NẾU VƯỢT QUA KIỂM DUYỆT -> TIẾN HÀNH PHÂN TÍCH
    # ========================================================
    report_id = f"REP-{str(uuid.uuid4())[:6].upper()}"
    
    registrar = BrandCategoryRegistrar()
    orchestrator = CrawlJobOrchestrator()
    resolver = BrandCategoryResolver()
    
    ai_narrative = ""
    chart_data = None
    similar_chart_data = None # 🚀 BIẾN LƯU DỮ LIỆU ĐỐI THỦ
    is_ready = False 
    
    # ----------------------------------------------------
    # CHẾ ĐỘ 1: ĐÁNH GIÁ 1 THƯƠNG HIỆU
    # ----------------------------------------------------
    if req.mode == "evaluate":
        brand = req.brands[0]
        category = req.category if hasattr(req, 'category') and req.category else None

        brand_id, is_new_brand = registrar.get_or_create_brand_with_flag(brand)
        category_id = registrar.get_or_create_category(category) if category else None

        if is_new_brand:
            orchestrator.handle_decision(brand_id=brand_id, category_id=category_id, recommended_action="NEED_FULL_CRAWL")
            ai_narrative = f"Hệ thống đang khởi tạo tiến trình thu thập dữ liệu đa nền tảng cho thương hiệu mới: **{brand}**.\n\nQuá trình này yêu cầu xử lý hàng ngàn bình luận và có thể mất từ 24h - 48h."
        else:
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
                ai_narrative = f"Dữ liệu của **{brand}** đang trong hàng đợi xử lý của các Agent. Vui lòng truy cập lại liên kết này sau ít giờ."
            else:
                is_ready = True 
                avg_score = round(sum(scores) / len(scores), 2)
                avg_pos = sum(pos_rates) / len(pos_rates) if pos_rates else None
                avg_neg = sum(neg_rates) / len(neg_rates) if neg_rates else None

                ai_narrative = narrate_brand_evaluation(
                    brand=brand, category=category or "toàn bộ danh mục", score=avg_score,
                    avg_rating=None, positive_rate=avg_pos, negative_rate=avg_neg,
                    total_reviews=status_row.TotalReviews or 0
                )
                
                # 🚀 LẤY TOP 3 ĐỐI THỦ ĐỂ VẼ BIỂU ĐỒ (Chỉ lấy khi đủ dữ liệu)
                if category_id:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT TOP 3 b.BrandName, r.Score 
                        FROM BrandAnalysisResult r 
                        JOIN Brand b ON r.BrandId = b.BrandId 
                        WHERE r.CategoryId = ? AND r.BrandId != ? 
                        ORDER BY r.Score DESC
                    """, (category_id, brand_id))
                    similar_brands = cursor.fetchall()
                    conn.close()
                    
                    if similar_brands:
                        similar_chart_data = {
                            "labels": [brand] + [b.BrandName for b in similar_brands],
                            "scores": [avg_score] + [b.Score for b in similar_brands]
                        }

    # ----------------------------------------------------
    # CHẾ ĐỘ 2: SO SÁNH NHIỀU THƯƠNG HIỆU
    # ----------------------------------------------------
    else:
        brand_id_map = {}
        for b in req.brands:
            b_id, is_new = registrar.get_or_create_brand_with_flag(b)
            brand_id_map[b] = b_id
            if is_new:
                orchestrator.handle_decision(brand_id=b_id, category_id=None, recommended_action="NEED_FULL_CRAWL")

        common_category_names = resolver.get_common_categories(list(brand_id_map.values()))

        if not common_category_names:
            ai_narrative = f"Hiện tại các thương hiệu bạn chọn ({', '.join(req.brands)}) chưa có chung danh mục sản phẩm nào đã được phân tích. Hệ thống đang kích hoạt Crawler."
        else:
            brand_summaries, trend_info = [], {}
            for b_name, b_id in brand_id_map.items():
                scores, total_reviews_sum = [], 0
                for cat_name in common_category_names:
                    cat_id = resolver.get_category_id_by_name(b_id, cat_name)
                    if not cat_id: continue

                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT Score FROM BrandAnalysisResult WHERE BrandId = ? AND CategoryId = ?", (b_id, cat_id))
                    analysis = cursor.fetchone()
                    cursor.execute("SELECT TotalReviews FROM BrandDataStatus WHERE BrandId = ? AND CategoryId = ?", (b_id, cat_id))
                    status_db = cursor.fetchone()
                    conn.close()

                    if not analysis or analysis.Score is None or not status_db: continue
                    scores.append(analysis.Score)
                    total_reviews_sum += status_db.TotalReviews

                if scores:
                    avg_score = round(sum(scores) / len(scores), 2)
                    brand_summaries.append({"brand": b_name, "score": avg_score, "total_reviews": total_reviews_sum})
                    trend_info[b_name] = {"category_count": len(resolver.get_categories_of_brand(b_id)), "total_reviews": total_reviews_sum}

            if len(brand_summaries) < 2:
                ai_narrative = "Một số thương hiệu trong danh sách đang thiếu dữ liệu. Crawler đang ưu tiên xử lý. Vui lòng xem lại báo cáo này sau."
            else:
                is_ready = True
                fake_question = f"So sánh {', '.join(req.brands)}"
                ai_narrative = compare_brands_with_llm(brand_summaries=brand_summaries, trend_info=trend_info, question=fake_question)

                chart_data = {
                    "labels": [b["brand"] for b in brand_summaries],
                    "scores": [b["score"] for b in brand_summaries],
                    "total_reviews": [b["total_reviews"] for b in brand_summaries]
                }

    # LƯU VÀO CACHE: THÊM TIER VÀ DỮ LIỆU ĐỐI THỦ
    REPORT_CACHE[report_id] = {
        "ai_narrative": ai_narrative,
        "brands": req.brands,
        "mode": req.mode,
        "chart_data": chart_data,
        "similar_chart_data": similar_chart_data,
        "is_ready": is_ready,
        "tier": user_tier 
    }

    send_evaluation_email(
        to_email=email, 
        full_name=full_name, 
        brand_list=req.brands, 
        report_id=report_id
    )

    return {"status": "success", "message": "Yêu cầu đã được hệ thống tiếp nhận và lưu thành công."}


@router.get("/report/{report_id}", response_class=HTMLResponse)
def view_report(request: Request, report_id: str):
    """Trang hiển thị Báo cáo Phân tích"""

    report_data = REPORT_CACHE.get(report_id)

    if not report_data:
        ai_narrative = "Báo cáo này đang được cập nhật hoặc phiên bản lưu trữ đã hết hạn. Vui lòng tạo yêu cầu mới tại trang chủ."
        chart_data = None
        similar_chart_data = None
        is_ready = False
        tier = "GUEST"
    else:
        ai_narrative = report_data["ai_narrative"]
        chart_data = report_data.get("chart_data")
        similar_chart_data = report_data.get("similar_chart_data") # Lấy dữ liệu đối thủ
        is_ready = report_data.get("is_ready", False)
        tier = report_data.get("tier", "BASIC") # Lấy gói dịch vụ

    context = {
        "request": request,
        "report_id": report_id,
        "generated_date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "ai_narrative": ai_narrative,
        "chart_data": chart_data,
        "similar_chart_data": similar_chart_data,
        "is_ready": is_ready,
        "tier": tier
    }

    return templates.TemplateResponse("report.jinja2", context)


# ==========================================
# CÁC API MỚI CHO QUẢN LÝ YÊU CẦU
# ==========================================
@router.post("/admin/request/unmark-spam")
def unmark_spam(request: Request, request_id: int = Form(...), email: str = Form(...)):
    """Đánh dấu Yêu cầu là Hợp lệ, kiểm tra và mở khóa tài khoản nếu đủ điều kiện"""
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        return RedirectResponse(url="/", status_code=303)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Chuyển trạng thái về Hợp lệ
        cursor.execute("UPDATE NhatKy_YeuCau SET TrangThai_AI = N'Hợp lệ' WHERE Ma_YeuCau = ?", (request_id,))
        
        # Đếm lại số lần vi phạm của Email này
        cursor.execute("SELECT COUNT(*) AS SpamCount FROM NhatKy_YeuCau WHERE Email = ? AND TrangThai_AI = N'Vi phạm'", (email,))
        spam_count = cursor.fetchone().SpamCount

        # Nếu số lần vi phạm <= 2, tiến hành Hồi sinh (Mở khóa)
        if spam_count <= 2:
            cursor.execute("UPDATE NguoiDung SET Da_Khoa = 0 WHERE Email = ?", (email,))
        
        conn.commit()
    except Exception as e:
        print(f"Lỗi Unmark Spam: {e}")
    finally:
        conn.close()
    
    return RedirectResponse(url="/admin?tab=requests", status_code=303)

@router.post("/admin/appeal/resolve")
def resolve_appeal(request: Request, appeal_id: int = Form(...)):
    """Đánh dấu Đơn khiếu nại đã giải quyết"""
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        return RedirectResponse(url="/", status_code=303)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Don_KhieuNai SET TrangThai_GiaiQuyet = N'Đã giải quyết' WHERE Ma_KhieuNai = ?", (appeal_id,))
        conn.commit()
    except Exception as e:
        print(f"Lỗi xử lý khiếu nại: {e}")
    finally:
        conn.close()
    
    return RedirectResponse(url="/admin?tab=requests", status_code=303)


# ==========================================
# GIAO DIỆN & API: KHIẾU NẠI TÀI KHOẢN
# ==========================================
from pydantic import BaseModel

class AppealSubmit(BaseModel):
    email: str
    phone: str
    content: str

@router.get("/appeal", response_class=HTMLResponse)
def appeal_page(request: Request, email: str = ""):
    """Trang hiển thị Biểu mẫu Khiếu nại"""
    return templates.TemplateResponse("appeal.jinja2", {"request": request, "email": email})

@router.post("/api/submit-appeal")
def submit_appeal_api(req: AppealSubmit):
    """API lưu Đơn khiếu nại vào Database"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Kiểm tra xem người dùng đã gửi đơn nào đang chờ xử lý chưa (chống spam đơn)
        cursor.execute("SELECT COUNT(*) AS Cnt FROM Don_KhieuNai WHERE Email = ? AND TrangThai_GiaiQuyet = N'Chờ xử lý'", (req.email,))
        if cursor.fetchone().Cnt > 0:
            return {"status": "error", "message": "Bạn đã gửi một đơn khiếu nại đang chờ xử lý. Vui lòng kiên nhẫn đợi Ban quản trị phản hồi."}

        # Lưu đơn khiếu nại mới
        cursor.execute("""
            INSERT INTO Don_KhieuNai (Email, SoDienThoai_LienHe, NoiDung_KhieuNai, TrangThai_GiaiQuyet)
            VALUES (?, ?, ?, N'Chờ xử lý')
        """, (req.email, req.phone, req.content))
        conn.commit()
        return {"status": "success", "message": "Gửi đơn khiếu nại thành công! Ban quản trị sẽ xem xét trong thời gian sớm nhất."}
    except Exception as e:
        print(f"Lỗi DB submit appeal: {e}")
        return {"status": "error", "message": "Có lỗi hệ thống, vui lòng thử lại sau."}
    finally:
        conn.close()


# ==========================================
# GIAO DIỆN & API: THANH TOÁN (PAYOS) & HÓA ĐƠN
# ==========================================

@router.get("/checkout", response_class=HTMLResponse)
def checkout_page(request: Request):
    """Trang chọn gói và thanh toán"""
    user = get_current_user(request)

    # if not user: Comment để KHÁCH ĐƯỢC VÀO XEM BẢNG GIÁ
    #     return RedirectResponse(url="/", status_code=303)
    
    # Tính ngày bắt đầu và kết thúc để hiển thị
    start_date = datetime.now()
    end_date = start_date + timedelta(days=30)
    
    return templates.TemplateResponse("checkout.jinja2", {
        "request": request, 
        "user": user,
        "start_date": start_date.strftime("%d/%m/%Y"),
        "end_date": end_date.strftime("%d/%m/%Y")
    })

class CheckoutRequest(BaseModel):
    plan: str # 'BASIC' hoặc 'VIP'

def shorten_name(name):
    # Rút gọn: "Nguyễn Hoàng Nghĩa" -> "Hoàng Nghĩa"
    parts = name.split()
    if len(parts) > 2:
        return f"{parts[-2]} {parts[-1]}" # Lấy tên đệm và tên chính
    return name

@router.post("/api/create-payment-link")
def create_payment_link(req: CheckoutRequest, request: Request):
    """Tạo link thanh toán PayOS"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # 🚀 1. ĐỊNH GIÁ GÓI CƯỚC THEO MÔ HÌNH MỚI (TOKEN & VIP)
    if req.plan == 'TOKEN_50':
        amount = 50000
        plan_name = "Nap 50 Token"
        desc_plan = "T50"
    elif req.plan == 'TOKEN_120':
        amount = 100000
        plan_name = "Nap 120 Token"
        desc_plan = "T120"
    elif req.plan == 'TOKEN_280':
        amount = 200000
        plan_name = "Nap 280 Token"
        desc_plan = "T280"
    else:
        # Trường hợp req.plan == 'VIP_30'
        amount = 100000
        plan_name = "Gia han VIP (30 Ngay)"
        desc_plan = "VIP"
    
    # Tạo mã đơn hàng duy nhất (Dùng timestamp integer)
    order_code = int(time.time() * 1000)

    # 🚀 2. XỬ LÝ RÚT GỌN NỘI DUNG (DƯỚI 25 KÝ TỰ)
    now = datetime.now()
    clean_name = shorten_name(user.get("name", "Khach"))
    date_str = now.strftime("%d%m") # Lấy NgàyTháng (ví dụ 1504)
    
    # Tạo chuỗi nội dung: "Hoàng Nghĩa 1504 T120" (Rất ngắn gọn và an toàn)
    description = f"{clean_name} {date_str} {desc_plan}"

    # Kiểm tra cuối cùng trước khi gửi sang PayOS
    if len(description) > 25:
        # Nếu vẫn dài, chỉ lấy tên chính và ngày
        description = f"{clean_name.split()[-1]} {date_str} {desc_plan}"

    # 3. LƯU ĐƠN HÀNG VÀO DATABASE
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO DonHang (MaDon, Email, Goi_DichVu, SoTien, TrangThai)
        VALUES (?, ?, ?, ?, 'PENDING')
    """, (order_code, user["email"], req.plan, amount))
    conn.commit()
    conn.close()

    # 4. CẤU HÌNH PAYOS
    item = ItemData(name=plan_name, quantity=1, price=amount)
    
    # THỰC TẾ: domain phải là domain thật (hoặc ngrok) để PayOS redirect về. 
    domain = "http://127.0.0.1:8000" 
    
    payment_data = PaymentData(
        orderCode=order_code,
        amount=amount,
        description=description,
        items=[item],
        cancelUrl=f"{domain}/checkout",
        returnUrl=f"{domain}/invoice/{order_code}" # Thanh toán xong văng về trang Hóa đơn
    )

    try:
        payos_response = payos_client.createPaymentLink(payment_data)
        return {"status": "success", "checkoutUrl": payos_response.checkoutUrl}
    except Exception as e:
        print(f"Lỗi tạo link PayOS: {e}")
        return {"status": "error", "message": "Không thể tạo link thanh toán lúc này."}

@router.post("/api/payos-webhook")
async def payos_webhook(request: Request):
    """Webhook nhận thông báo thanh toán thành công từ PayOS"""
    try:
        body = await request.json()
        data = body.get("data", {})
        order_code = data.get("orderCode")
        
        # Nếu thanh toán thành công
        if body.get("code") == "00" or data.get("desc") == "success":
            conn = get_connection()
            cursor = conn.cursor()
            
            # Lấy thông tin đơn hàng (Chỉ lấy đơn PENDING để tránh xử lý trùng)
            cursor.execute("""
                SELECT d.Email, d.Goi_DichVu, d.SoTien, u.HoTen 
                FROM DonHang d JOIN NguoiDung u ON d.Email = u.Email
                WHERE d.MaDon = ? AND d.TrangThai = 'PENDING'
            """, (order_code,))
            order = cursor.fetchone()
            
            if order:
                cursor.execute("UPDATE DonHang SET TrangThai = 'SUCCESS' WHERE MaDon = ?", (order_code,))
                now = datetime.now()
                
                # KIỂM TRA MUA TOKEN HAY MUA VIP
                if order.Goi_DichVu.startswith('TOKEN'):
                    tokens_to_add = int(order.Goi_DichVu.split('_')[1])
                    cursor.execute("UPDATE NguoiDung SET So_Token = So_Token + ? WHERE Email = ?", (tokens_to_add, order.Email))
                    plan_label = f"Nạp {tokens_to_add} Token"
                    start_str, end_str = "Sử dụng vĩnh viễn", ""
                else:
                    end_date = now + timedelta(days=30)
                    cursor.execute("UPDATE NguoiDung SET Goi_DichVu = 'VIP', Ngay_KichHoat = ?, Ngay_HetHan = ? WHERE Email = ?", (now, end_date, order.Email))
                    plan_label = "Gia hạn VIP (30 Ngày)"
                    start_str, end_str = now.strftime("%d/%m/%Y"), end_date.strftime("%d/%m/%Y")
                
                conn.commit()
                
                # 3. 🚀 GỬI EMAIL HÓA ĐƠN KHI WEBHOOK CHẠY TRƯỚC
                plan_label = "VIP" if order.Goi_DichVu == 'VIP' else "Thường (Basic)"
                send_invoice_email(
                    to_email=order.Email,
                    full_name=order.HoTen,
                    order_code=order_code,
                    plan_name=plan_label,
                    amount=order.SoTien,
                    start_date=now.strftime("%d/%m/%Y"),
                    end_date=end_date.strftime("%d/%m/%Y")
                )
                
            conn.close()
        return {"success": True}
    except Exception as e:
        print(f"Lỗi Webhook: {e}")
        return {"success": False}

@router.get("/invoice/{order_id}", response_class=HTMLResponse)
def view_invoice(request: Request, order_id: int):
    """Trang Hóa đơn điện tử có tích hợp Kiểm tra chéo PayOS"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.MaDon, d.Goi_DichVu, d.SoTien, d.TrangThai, d.NgayTao, u.HoTen, u.Email 
        FROM DonHang d
        JOIN NguoiDung u ON d.Email = u.Email
        WHERE d.MaDon = ? AND d.Email = ?
    """, (order_id, user["email"]))
    order = cursor.fetchone()

    if not order:
        conn.close()
        return HTMLResponse("Không tìm thấy hóa đơn hoặc bạn không có quyền xem.")

    # 🚀 FIX LOCALHOST: TỰ ĐỘNG HỎI PAYOS NẾU ĐƠN VẪN ĐANG PENDING
    if order.TrangThai == 'PENDING':
        try:
            # Gọi API PayOS để lấy trạng thái thực tế của đơn hàng
            payment_info = payos_client.payment_requests.get(order_id)
            
            # Nếu PayOS báo đã thanh toán thành công
            if payment_info.status == "PAID":
                # 1. Đổi trạng thái hóa đơn
                cursor.execute("UPDATE DonHang SET TrangThai = 'SUCCESS' WHERE MaDon = ?", (order_id,))
                
                # 2. Gia hạn Gói dịch vụ cho tài khoản
                now = datetime.now()
                end_date = now + timedelta(days=30)
                cursor.execute("""
                    UPDATE NguoiDung 
                    SET Goi_DichVu = ?, Ngay_KichHoat = ?, Ngay_HetHan = ? 
                    WHERE Email = ?
                """, (order.Goi_DichVu, now, end_date, order.Email))
                
                conn.commit()
                
                # 3. Lấy lại dữ liệu order mới nhất để hiển thị ra HTML
                cursor.execute("""
                    SELECT d.MaDon, d.Goi_DichVu, d.SoTien, d.TrangThai, d.NgayTao, u.HoTen, u.Email 
                    FROM DonHang d JOIN NguoiDung u ON d.Email = u.Email
                    WHERE d.MaDon = ?
                """, (order_id,))
                order = cursor.fetchone()
                
                # 🚀 GỬI EMAIL HÓA ĐƠN
                plan_label = "VIP" if order.Goi_DichVu == 'VIP' else "Thường (Basic)"
                send_invoice_email(
                    to_email=order.Email,
                    full_name=order.HoTen,
                    order_code=order_id,
                    plan_name=plan_label,
                    amount=order.SoTien,
                    start_date=now.strftime("%d/%m/%Y"),
                    end_date=end_date.strftime("%d/%m/%Y")
                )
                
        except Exception as e:
            print(f"Lỗi khi kiểm tra chéo với PayOS: {e}")
            
    conn.close()

    # Tính ngày hết hạn hiển thị trên hóa đơn
    start_date = order.NgayTao
    end_date = start_date + timedelta(days=30)

    context = {
        "request": request,
        "order": order,
        "start_date": start_date.strftime("%d/%m/%Y"),
        "end_date": end_date.strftime("%d/%m/%Y"),
        "print_date": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    return templates.TemplateResponse("invoice.jinja2", context)


def send_invoice_email(to_email, full_name, order_code, plan_name, amount, start_date, end_date):
    """Gửi email hóa đơn điện tử chuyên nghiệp sau khi thanh toán thành công"""
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    
    if not sender_email or not sender_password:
        print("[Email Error] Thiếu cấu hình EMAIL_SENDER hoặc EMAIL_PASSWORD trong .env")
        return

    msg = MIMEMultipart()
    msg['From'] = f"Tiên Phong Tech <{sender_email}>"
    msg['To'] = to_email
    msg['Subject'] = f"Hóa đơn thanh toán #{order_code} - Tiên Phong Tech"

    # 🚀 FIX LỖI ĐỊNH DẠNG SỐ: Format xong mới Replace
    formatted_amount = "{:,.0f}".format(amount).replace(',', '.') + " đ"

    html_content = f"""
    <html>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 0;">
        <div style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <div style="background-color: #4f46e5; padding: 30px; text-align: center; color: #ffffff;">
                <h1 style="margin: 0; font-size: 24px; letter-spacing: 1px;">XÁC NHẬN THANH TOÁN</h1>
                <p style="margin: 5px 0 0; opacity: 0.8;">Cảm ơn bạn đã tin dùng Tiên Phong Tech</p>
            </div>
            
            <div style="padding: 30px; color: #333333;">
                <p>Xin chào <strong>{full_name}</strong>,</p>
                <p>Chúng tôi đã nhận được thanh toán cho đơn hàng <strong>#{order_code}</strong>. Gói dịch vụ của bạn đã được kích hoạt thành công.</p>
                
                <div style="background-color: #f9fafb; border-radius: 6px; padding: 20px; margin: 20px 0; border: 1px solid #e5e7eb;">
                    <h3 style="margin-top: 0; color: #4f46e5; border-bottom: 1px solid #e5e7eb; padding-bottom: 10px;">Chi tiết hóa đơn</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">Dịch vụ:</td>
                            <td style="padding: 8px 0; text-align: right; font-weight: bold;">{plan_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">Thời hạn:</td>
                            <td style="padding: 8px 0; text-align: right;">{start_date} - {end_date}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">Tổng cộng:</td>
                            <td style="padding: 8px 0; text-align: right; font-size: 18px; color: #059669; font-weight: bold;">{formatted_amount}</td>
                        </tr>
                    </table>
                </div>

                <div style="text-align: center; margin-top: 30px;">
                    <a href="http://127.0.0.1:8000/dashboard" style="background-color: #4f46e5; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Truy cập Dashboard ngay</a>
                </div>
            </div>

            <div style="background-color: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #9ca3af; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0;">Đây là email tự động, vui lòng không trả lời email này.</p>
                <p style="margin: 5px 0;">&copy; 2026 Tiên Phong Tech - Chuyên trang phân tích thương hiệu Shopee</p>
            </div>
        </div>
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
        print(f"[Email Success] Đã gửi hóa đơn cho {to_email}")
    except Exception as e:
        print(f"[Email Error] Không thể gửi mail: {e}")

# ==========================================
# CÁC TRANG WEB TĨNH (STATIC PAGES)
# ==========================================
@router.get("/page/{page_name}", response_class=HTMLResponse)
def static_pages(request: Request, page_name: str):
    """Render các trang tĩnh (Câu chuyện, Liên hệ, FAQ, Điều khoản)"""
    user = get_current_user(request)
    
    # Map tên URL với tên file .jinja2 tương ứng
    valid_pages = {
        "cau-chuyen": "story.jinja2",
        "lien-he": "contact.jinja2",
        "dieu-khoan": "terms.jinja2",
        "faq": "faq.jinja2"
    }
    
    template_file = valid_pages.get(page_name)
    if not template_file:
        # Nếu nhập sai tên trang, ném về trang chủ
        return RedirectResponse(url="/")
        
    return templates.TemplateResponse(template_file, {
        "request": request, 
        "user": user,
        "current_date": datetime.now().strftime("%d/%m/%Y")
    })