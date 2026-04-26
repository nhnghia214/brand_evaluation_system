# # =========================
# # fetcher/search_fetcher.py (FINAL – ANTI LAZY-LOAD & DEBUG LOGS)
# # =========================
# import time
# from crawler.utils.sleeper import short_sleep
# from config import MIN_SOLD_COUNT, MAX_SEARCH_PAGE, ANCHOR_PRODUCT_LIMIT
# from urllib.parse import quote

# # THÊM DÒNG NÀY ĐỂ GỌI HÀM CHECK CAPTCHA
# from captcha_solver import check_and_solve_captcha 

# class SearchFetcher:
#     def __init__(self, page, start_page=0):
#         self.page = page
#         self.start_page = start_page

#     def _scroll_gradually(self):
#         """
#         Cuộn từ từ để Shopee load hết text/hình ảnh của 60 items (Chống Lazy Load)
#         """
#         for i in range(1, 11):
#             self.page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i/10})")
#             time.sleep(0.5)
#         time.sleep(1) # Chờ ổn định DOM sau khi chạm đáy

#     def search_and_collect_forever(self, brand, category):
#         if not category or category.strip() == "":
#             category = "ALL"

#         raw_keyword = f"{category} {brand}".lower()
#         keyword = quote(raw_keyword, safe="")

#         seen_urls = set()

#         # Shopee đã dùng phân trang bằng URL, nên ta chỉ cần lặp qua các Page
#         for page_index in range(self.start_page, MAX_SEARCH_PAGE):
#             url = (
#                 "https://shopee.vn/search?"
#                 f"keyword={keyword}&sortBy=sales&page={page_index}"
#             )

#             print(f"\n[SearchFetcher] 🌐 Open: {url}")
#             self.page.goto(url, wait_until="domcontentloaded")
#             time.sleep(3)

#             # ==================================================
#             # 🛑 TRẠM CHECK CAPTCHA Ở TRANG TÌM KIẾM
#             # ==================================================
#             if not check_and_solve_captcha(self.page):
#                 print("[SearchFetcher] ❌ Dính Captcha và không thể giải quyết. Tạm ngưng trang này.")
#                 yield {"_page_done": True, "page_index": page_index, "items_found": 0}
#                 continue

#             # 🚀 ĐIỂM QUYẾT ĐỊNH: Bắt buộc cuộn trang để lấy dữ liệu thực trước khi Query
#             print("[SearchFetcher] Đang cuộn trang để kích hoạt Lazy Loading...")
#             self._scroll_gradually()

#             items = self.page.query_selector_all('[data-sqe="item"]')
#             items_found_on_dom = len(items)

#             added_this_round = 0
#             anchor_used = 0
            
#             # Khởi tạo bộ đếm để báo cáo Log
#             err_no_link = 0
#             err_low_sold = 0
#             err_dup = 0

#             for item in items:
#                 try:
#                     # 1. Tìm thẻ A chứa link (Dùng a[href] để bất chấp sự thay đổi class của Shopee)
#                     a = item.query_selector("a[href]")
#                     if not a:
#                         err_no_link += 1
#                         continue

#                     href = a.get_attribute("href")
#                     if not href:
#                         err_no_link += 1
#                         continue

#                     if href.startswith("/"):
#                         href = "https://shopee.vn" + href

#                     # ❌ Bỏ qua nếu bị trùng lặp
#                     if href in seen_urls:
#                         err_dup += 1
#                         continue

#                     # 2. Tìm số lượng đã bán
#                     sold = self._parse_sold_count(item)
#                     if sold < MIN_SOLD_COUNT:
#                         err_low_sold += 1
#                         continue

#                     # 3. Lấy tên sản phẩm
#                     name_el = item.query_selector('div[data-sqe="name"] > div')
#                     if not name_el:
#                         name_el = item.query_selector('div[data-sqe="name"]')
#                     name = name_el.inner_text().strip() if name_el else "Unknown Product"

#                     # ✅ SẢN PHẨM HỢP LỆ
#                     seen_urls.add(href)
#                     added_this_round += 1

#                     # Mỏ neo an toàn
#                     is_anchor = False
#                     if page_index == 0 and anchor_used < ANCHOR_PRODUCT_LIMIT:
#                         is_anchor = True
#                         anchor_used += 1

#                     yield {
#                         "url": href,
#                         "name": name,
#                         "sold": sold,
#                         "is_anchor": is_anchor,
#                         "page_index": page_index
#                     }

#                 except Exception:
#                     continue

#             # =============================
#             # 📊 BÁO CÁO LOG SAU MỖI TRANG
#             # =============================
#             print(f"[SearchFetcher] Báo cáo Page {page_index}: Thấy {items_found_on_dom} SP | Lấy được: {added_this_round} | Lỗi Link: {err_no_link} | Lượt bán thấp: {err_low_sold} | Bị trùng: {err_dup}")

#             # Nếu DOM có sản phẩm nhưng không lấy được cái nào -> Shopee hết hàng hoặc bán quá ế
#             if items_found_on_dom > 0 and added_this_round == 0:
#                 print(f"[SearchFetcher] Tạm ngưng quét tìm kiếm vì các sản phẩm trang này đều dưới chuẩn (Bán < {MIN_SOLD_COUNT})")
#                 yield {"_page_done": True, "page_index": page_index, "items_found": 0}
#                 break
                
#             # Nếu DOM hoàn toàn trống trơn -> Bị chặn (Captcha ngầm) hoặc lỗi mạng
#             if items_found_on_dom == 0:
#                 print(f"[SearchFetcher] CẢNH BÁO: DOM trống trơn. Shopee từ chối hiển thị kết quả.")
#                 yield {"_page_done": True, "page_index": page_index, "items_found": 0}
#                 break

#             yield {
#                 "_page_done": True,
#                 "page_index": page_index,
#                 "items_found": items_found_on_dom
#             }

#         # 🔚 KẾT THÚC VÒNG LẶP TRANG
#         yield {"_search_done": True}

#     # =============================
#     # PARSE SOLD COUNT (CHỐNG LỖI)
#     # =============================
#     def _parse_sold_count(self, item):
#         try:
#             text = item.inner_text().lower()
#             sold_text = ""
            
#             if "đã bán" in text:
#                 sold_text = text.split("đã bán")[1].split('\n')[0].strip()
#             elif "sold" in text:
#                 sold_text = text.split("sold")[1].split('\n')[0].strip()
#             else:
#                 return 0

#             if "k" in sold_text:
#                 sold_text = sold_text.replace(",", ".") 
#                 digits = "".join(c for c in sold_text if c.isdigit() or c == '.')
#                 return int(float(digits) * 1000) if digits else 0

#             digits = "".join(c for c in sold_text if c.isdigit())
#             return int(digits) if digits else 0
#         except:
#             return 0


import time
import os
import smtplib
import requests
from email.mime.text import MIMEText

STRIKE_COUNT = 0
CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY")

# ============================================================
# BƯỚC 1: HÀM LÕI GỌI CAPSOLVER API
# ============================================================
def solve_shopee_captcha_via_api(page):
    """
    Gọi CapSolver để giải Shopee slider captcha.
    Flow: Tạo Task → Poll kết quả → Inject & Submit
    """
    if not CAPSOLVER_API_KEY:
        print("⚠️ Chưa set CAPSOLVER_API_KEY trong .env")
        return False

    current_url = page.url

    # --- TẠO TASK ---
    print("[CapSolver] Đang tạo task giải captcha...")
    try:
        create_resp = requests.post(
            "https://api.capsolver.com/createTask",
            json={
                "clientKey": CAPSOLVER_API_KEY,
                "task": {
                    "type": "AntiCyberSiAraTask",   # Task type cho Shopee slider
                    "websiteURL": current_url,
                    "websiteKey": _extract_captcha_key(page),  # Xem hàm bên dưới
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

    # --- POLL KẾT QUẢ (mỗi 1 giây, tối đa 15 giây) ---
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
    """
    Trích xuất websiteKey từ DOM của trang captcha Shopee.
    Key này nằm trong data attribute của iframe/div captcha.
    Cần inspect trang captcha thật để xác định đúng selector.
    """
    try:
        # Thử tìm trong các attribute phổ biến của Shopee captcha widget
        for selector in [
            "[data-site-key]",
            "[data-sitekey]", 
            "iframe[src*='captcha']",
        ]:
            el = page.query_selector(selector)
            if el:
                key = el.get_attribute("data-site-key") or el.get_attribute("data-sitekey")
                if key:
                    print(f"[CapSolver] 🔑 Tìm thấy websiteKey: {key[:20]}...")
                    return key
        
        # Nếu không tìm thấy qua DOM, thử lấy từ URL của iframe
        iframe = page.query_selector("iframe[src*='captcha']")
        if iframe:
            src = iframe.get_attribute("src") or ""
            # Parse key từ URL params
            if "sitekey=" in src:
                return src.split("sitekey=")[1].split("&")[0]

        print("[CapSolver] ⚠️ Không tìm thấy websiteKey, thử gửi rỗng...")
        return ""
    except:
        return ""


def _apply_solution(page, solution):
    """
    Inject token/kết quả từ CapSolver vào trang.
    Với slider captcha, solution thường chứa vị trí kéo hoặc token.
    """
    try:
        # Nếu solution là token (dạng string để inject vào field ẩn)
        if "token" in solution:
            token = solution["token"]
            page.evaluate(f"""
                // Inject vào các field hidden phổ biến của Shopee captcha
                const fields = document.querySelectorAll(
                    'input[name*="captcha"], input[name*="token"], input[id*="captcha"]'
                );
                fields.forEach(f => f.value = '{token}');
                
                // Trigger submit nếu có form
                const form = document.querySelector('form[id*="captcha"], form[class*="captcha"]');
                if (form) form.submit();
            """)
            time.sleep(2)

        # Nếu solution chứa tọa độ kéo slider (x offset)
        elif "distance" in solution or "x" in solution:
            distance = solution.get("distance") or solution.get("x", 100)
            _drag_slider(page, distance)

        # Kiểm tra sau khi apply
        time.sleep(2)
        current_url = page.url.lower()
        if "verify" not in current_url and "captcha" not in current_url:
            print("[CapSolver] ✅ Apply solution thành công, captcha đã qua!")
            return True
        else:
            print("[CapSolver] ❌ Apply xong nhưng vẫn còn captcha.")
            return False

    except Exception as e:
        print(f"[CapSolver] ❌ Lỗi apply solution: {e}")
        return False


def _drag_slider(page, distance):
    """Kéo thanh slider theo distance CapSolver trả về."""
    try:
        slider = page.query_selector(
            ".captcha-slider-btn, .secsdk-captcha-drag-icon, [class*='slider']"
        )
        if not slider:
            print("[CapSolver] ⚠️ Không tìm thấy slider element")
            return

        box = slider.bounding_box()
        if not box:
            return

        start_x = box["x"] + box["width"] / 2
        start_y = box["y"] + box["height"] / 2

        page.mouse.move(start_x, start_y)
        page.mouse.down()
        time.sleep(0.3)

        # Kéo từng bước nhỏ để giả lập tay người
        steps = 20
        for i in range(1, steps + 1):
            page.mouse.move(
                start_x + (distance * i / steps),
                start_y + (i % 3)  # Lắc nhẹ theo trục Y
            )
            time.sleep(0.02)

        page.mouse.up()
        time.sleep(1)
        print(f"[CapSolver] 🖱️ Đã kéo slider {distance}px")

    except Exception as e:
        print(f"[CapSolver] ❌ Lỗi kéo slider: {e}")


# ============================================================
# BƯỚC 2: HÀM PUBLIC (GIỮ NGUYÊN TÊN ĐỂ KHÔNG PHẢI SỬA CÁC FILE KHÁC)
# ============================================================
def check_and_solve_captcha(page):
    global STRIKE_COUNT

    # --- Nhận diện captcha ---
    current_url = page.url.lower()
    is_blocked = "verify" in current_url or "captcha" in current_url
    if not is_blocked:
        try:
            if page.get_by_text("Kéo qua để hoàn thiện", exact=False).is_visible():
                is_blocked = True
        except:
            pass

    if not is_blocked:
        STRIKE_COUNT = 0
        return True

    print(f"\n🚨 [Anti-Bot] PHÁT HIỆN CAPTCHA! (Strike: {STRIKE_COUNT + 1})")

    # --- Thử CapSolver trước (2 lần) ---
    for attempt in range(2):
        print(f"[Anti-Bot] 🤖 Thử CapSolver lần {attempt + 1}...")
        if solve_shopee_captcha_via_api(page):
            STRIKE_COUNT = 0
            return True
        print(f"[Anti-Bot] CapSolver lần {attempt + 1} thất bại, thử lại...")
        time.sleep(3)

    # --- CapSolver thua, cho người giải tay 3 phút ---
    print("⏳ CapSolver không giải được. Cho bạn 3 phút để giải tay...")
    for i in range(36):
        time.sleep(5)
        cur = page.url.lower()
        if "verify" not in cur and "captcha" not in cur:
            print("✅ Đã giải tay thành công!")
            STRIKE_COUNT = 0
            return True

    # --- Vẫn thua, ngủ 1 tiếng ---
    if STRIKE_COUNT == 0:
        print("💤 Ngủ 1 tiếng để Shopee nhả IP...")
        time.sleep(3600)
        STRIKE_COUNT += 1
        page.reload(wait_until="domcontentloaded")
        time.sleep(5)
        return check_and_solve_captcha(page)

    # --- Vẫn thua sau khi ngủ, gửi mail ---
    _send_rescue_email(page.url)
    print("🛑 Chờ Admin vào giải tay qua Remote Desktop...")
    while "verify" in page.url.lower() or "captcha" in page.url.lower():
        time.sleep(10)

    print("✅ Qua ải! Tiếp tục cào...")
    STRIKE_COUNT = 0
    return True


# ============================================================
# EMAIL HELPER (Giữ nguyên logic cũ)
# ============================================================
def _send_rescue_email(blocked_url):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver = os.getenv("EMAIL_RECEIVER")
    if not sender or not password:
        return
    msg = MIMEText(
        f"Hệ thống bị khóa tại:\n{blocked_url}\n\nHãy vào Remote Desktop giải tay!"
    )
    msg['Subject'] = "🆘 CỨU VIỆN: Crawler dính Captcha nặng!"
    msg['From'] = sender
    msg['To'] = receiver
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print("📧 Đã gửi email cầu cứu!")
    except Exception as e:
        print(f"❌ Không gửi được email: {e}")