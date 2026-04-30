# import smtplib
# import time
# import os
# from email.mime.text import MIMEText

# STRIKE_COUNT = 0 

# def send_rescue_email(subject, body):
#     sender = os.getenv("EMAIL_SENDER")
#     password = os.getenv("EMAIL_PASSWORD")
#     receiver = os.getenv("EMAIL_RECEIVER")
    
#     if not sender or not password:
#         print("⚠️ Chưa cấu hình Email trong .env, bỏ qua bước gửi mail.")
#         return

#     msg = MIMEText(body)
#     msg['Subject'] = subject
#     msg['From'] = sender
#     msg['To'] = receiver

#     try:
#         with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
#             server.login(sender, password)
#             server.sendmail(sender, receiver, msg.as_string())
#         print("📧 [Notification] Đã gửi email cầu cứu đến Nghĩa!")
#     except Exception as e:
#         print(f"❌ [Error] Không gửi được email: {e}")

# def check_and_solve_captcha(page):
#     global STRIKE_COUNT
    
#     # 1. Nhận diện chặn
#     current_url = page.url.lower()
#     is_blocked = "verify" in current_url or "captcha" in current_url
#     if not is_blocked:
#         if page.get_by_text("Kéo qua để hoàn thiện", exact=False).is_visible():
#             is_blocked = True

#     if not is_blocked:
#         STRIKE_COUNT = 0 # An toàn thì reset bộ đếm
#         return True

#     print(f"\n🚨 [Anti-Bot] PHÁT HIỆN CAPTCHA! (Lần vi phạm: {STRIKE_COUNT + 1})")

#     # ==========================================
#     # CƠ HỘI VÀNG: Chờ bạn 3 phút để tự giải tay
#     # ==========================================
#     print("⏳ Cho bạn 3 phút (180s) để vào kéo thanh trượt...")
#     for i in range(36): # 36 lần x 5s = 180s
#         time.sleep(5)
#         # Kiểm tra xem bạn đã giải xong chưa
#         if "verify" not in page.url.lower() and "captcha" not in page.url.lower():
#             print("✅ Bạn đã giải tay thành công! Hệ thống tiếp tục cào ngay lập tức...")
#             STRIKE_COUNT = 0
#             return True

#     # ==========================================
#     # QUÁ 3 PHÚT KHÔNG CÓ AI GIẢI -> ĐI NGỦ
#     # ==========================================
#     if STRIKE_COUNT == 0:
#         print("💤 Không thấy Nghĩa giải. Hệ thống sẽ tạm dừng 1 giờ để Shopee nhả IP...")
#         time.sleep(3600) # Ngủ 1 tiếng
#         STRIKE_COUNT += 1
#         print("🔄 Đã hết 1 giờ, đang tự động tải lại trang xem Shopee đã nhả chưa...")
#         page.reload(wait_until="domcontentloaded")
#         time.sleep(5)
#         return check_and_solve_captcha(page) # Kiểm tra lại sau khi ngủ dậy

#     # Nếu đã ngủ dậy mà vẫn dính tiếp -> Gửi Mail
#     elif STRIKE_COUNT >= 1:
#         print("🆘 BỊ KHÓA CỨNG! Đang gửi email cầu cứu...")
#         send_rescue_email(
#             "CỨU VIỆN: Crawler dính Captcha nặng!",
#             f"Nghĩa ơi, hệ thống đã ngủ 1 tiếng nhưng vẫn bị chặn tại: {page.url}\n\nHãy vào Remote Desktop để giải tay nhé!"
#         )
        
#         print("🛑 DỪNG VÔ THỜI HẠN cho đến khi Admin vào giải tay xong...")
#         # Vòng lặp kẹt vô thời hạn chờ bạn vào Remote Desktop
#         while "verify" in page.url.lower() or "captcha" in page.url.lower():
#             time.sleep(10)
        
#         print("✅ Đã nhận thấy qua ải! Reset bộ đếm và tiếp tục...")
#         STRIKE_COUNT = 0
#         return True

import time
import os
import smtplib
import requests
from email.mime.text import MIMEText
from crawler.db.db_connection import get_connection # Import DB

STRIKE_COUNT = 0
CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY")

# ============================================================
# HÀM BỔ TRỢ: CẬP NHẬT TRẠNG THÁI DB
# ============================================================
def _update_job_status(job_id, status):
    if not job_id: return
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE CrawlJob SET JobStatus = ? WHERE JobId = ?", (status, job_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ [DB Error] Không thể cập nhật trạng thái {status} cho Job {job_id}: {e}")

# ============================================================
# BƯỚC 1: HÀM LÕI GỌI CAPSOLVER API (Giữ nguyên)
# ============================================================
def solve_shopee_captcha_via_api(page):
    if not CAPSOLVER_API_KEY:
        print("⚠️ Chưa set CAPSOLVER_API_KEY trong .env")
        return False
    current_url = page.url
    print("[CapSolver] Đang tạo task giải captcha...")
    try:
        create_resp = requests.post(
            "https://api.capsolver.com/createTask",
            json={
                "clientKey": CAPSOLVER_API_KEY,
                "task": {
                    "type": "AntiCyberSiAraTask",   
                    "websiteURL": current_url,
                    "websiteKey": _extract_captcha_key(page),  
                }
            },
            timeout=10
        )
        task_data = create_resp.json()
    except Exception as e:
        print(f"[CapSolver] ❌ Lỗi tạo task: {e}")
        return False

    if task_data.get("errorId") != 0:
        print(f"[CapSolver] ❌ API lỗi: {task_data.get('errorDescription')}")
        return False

    task_id = task_data.get("taskId")
    print(f"[CapSolver] ✅ Task tạo thành công: {task_id}")

    for attempt in range(15):
        time.sleep(1)
        try:
            result_resp = requests.post(
                "https://api.capsolver.com/getTaskResult",
                json={"clientKey": CAPSOLVER_API_KEY, "taskId": task_id},
                timeout=5
            )
            result = result_resp.json()
        except Exception as e:
            print(f"[CapSolver] ⚠️ Poll lần {attempt+1} thất bại: {e}")
            continue

        status = result.get("status")
        if status == "ready":
            solution = result.get("solution", {})
            print(f"[CapSolver] ✅ Giải thành công sau {attempt+1}s!")
            return _apply_solution(page, solution)
        elif status == "processing":
            print(f"[CapSolver] ⏳ Đang xử lý... ({attempt+1}s)")
            continue
        else:
            print(f"[CapSolver] ❌ Trạng thái lạ: {result}")
            return False

    print("[CapSolver] ❌ Timeout 15 giây, không giải được.")
    return False

def _extract_captcha_key(page):
    try:
        for selector in ["[data-site-key]", "[data-sitekey]", "iframe[src*='captcha']"]:
            el = page.query_selector(selector)
            if el:
                key = el.get_attribute("data-site-key") or el.get_attribute("data-sitekey")
                if key:
                    print(f"[CapSolver] 🔑 Tìm thấy websiteKey: {key[:20]}...")
                    return key
        
        iframe = page.query_selector("iframe[src*='captcha']")
        if iframe:
            src = iframe.get_attribute("src") or ""
            if "sitekey=" in src: return src.split("sitekey=")[1].split("&")[0]
        return ""
    except: return ""

def _apply_solution(page, solution):
    try:
        if "token" in solution:
            token = solution["token"]
            page.evaluate(f"""
                const fields = document.querySelectorAll('input[name*="captcha"], input[name*="token"], input[id*="captcha"]');
                fields.forEach(f => f.value = '{token}');
                const form = document.querySelector('form[id*="captcha"], form[class*="captcha"]');
                if (form) form.submit();
            """)
            time.sleep(2)
        elif "distance" in solution or "x" in solution:
            distance = solution.get("distance") or solution.get("x", 100)
            _drag_slider(page, distance)

        time.sleep(2)
        if "verify" not in page.url.lower() and "captcha" not in page.url.lower():
            print("[CapSolver] ✅ Apply solution thành công, captcha đã qua!")
            return True
        return False
    except Exception as e:
        print(f"[CapSolver] ❌ Lỗi apply solution: {e}")
        return False

def _drag_slider(page, distance):
    try:
        slider = page.query_selector(".captcha-slider-btn, .secsdk-captcha-drag-icon, [class*='slider']")
        if not slider: return
        box = slider.bounding_box()
        if not box: return

        start_x, start_y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        time.sleep(0.3)

        steps = 20
        for i in range(1, steps + 1):
            page.mouse.move(start_x + (distance * i / steps), start_y + (i % 3))
            time.sleep(0.02)

        page.mouse.up()
        time.sleep(1)
        print(f"[CapSolver] 🖱️ Đã kéo slider {distance}px")
    except Exception as e: print(f"[CapSolver] ❌ Lỗi kéo slider: {e}")

# ============================================================
# BƯỚC 2: HÀM PUBLIC (CÓ JOB_ID)
# ============================================================
def check_and_solve_captcha(page, job_id=None):
    global STRIKE_COUNT
    current_url = page.url.lower()
    is_blocked = "verify" in current_url or "captcha" in current_url
    if not is_blocked:
        try:
            if page.get_by_text("Kéo qua để hoàn thiện", exact=False).is_visible(): is_blocked = True
        except: pass

    if not is_blocked:
        STRIKE_COUNT = 0
        return True

    print(f"\n🚨 [Anti-Bot] PHÁT HIỆN CAPTCHA! (Strike: {STRIKE_COUNT + 1})")
    for attempt in range(2):
        print(f"[Anti-Bot] 🤖 Thử CapSolver lần {attempt + 1}...")
        if solve_shopee_captcha_via_api(page):
            STRIKE_COUNT = 0
            return True
        print(f"[Anti-Bot] CapSolver lần {attempt + 1} thất bại, thử lại...")
        time.sleep(3)

    print("⏳ CapSolver không giải được. Cho bạn 3 phút để giải tay...")
    for i in range(36):
        time.sleep(5)
        cur = page.url.lower()
        if "verify" not in cur and "captcha" not in cur:
            print("✅ Đã giải tay thành công!")
            STRIKE_COUNT = 0
            return True

    if STRIKE_COUNT == 0:
        print("💤 Ngủ 1 tiếng để Shopee nhả IP. Cập nhật trạng thái PAUSED...")
        _update_job_status(job_id, 'PAUSED')
        time.sleep(3600)
        print("🔄 Đã hết 1 giờ, Cập nhật lại RUNNING...")
        _update_job_status(job_id, 'RUNNING')
        STRIKE_COUNT += 1
        page.reload(wait_until="domcontentloaded")
        time.sleep(5)
        return check_and_solve_captcha(page, job_id)

    _update_job_status(job_id, 'PAUSED')
    _send_rescue_email(page.url)
    print("🛑 Chờ Admin vào giải tay qua Remote Desktop...")
    while "verify" in page.url.lower() or "captcha" in page.url.lower(): time.sleep(10)

    print("✅ Qua ải! Tiếp tục cào...")
    _update_job_status(job_id, 'RUNNING')
    STRIKE_COUNT = 0
    return True

# ============================================================
# EMAIL HELPER (LOCAL - XÀI SMTPLIB)
# ============================================================
def _send_rescue_email(blocked_url):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver = os.getenv("EMAIL_RECEIVER")
    if not sender or not password: return
    msg = MIMEText(f"Hệ thống bị khóa tại:\n{blocked_url}\n\nHãy vào Local giải tay!")
    msg['Subject'] = "🆘 CỨU VIỆN LOCAL: Crawler dính Captcha nặng!"
    msg['From'] = sender
    msg['To'] = receiver
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print("📧 Đã gửi email cầu cứu từ Local!")
    except Exception as e: print(f"❌ Không gửi được email: {e}")