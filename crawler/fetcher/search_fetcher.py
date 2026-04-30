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

#             print(f"\n[SearchFetcher]  Open: {url}")
#             self.page.goto(url, wait_until="domcontentloaded")
#             time.sleep(3)

#             # ==================================================
#             #  TRẠM CHECK CAPTCHA Ở TRANG TÌM KIẾM
#             # ==================================================
#             if not check_and_solve_captcha(self.page):
#                 print("[SearchFetcher] ❌ Dính Captcha và không thể giải quyết. Tạm ngưng trang này.")
#                 yield {"_page_done": True, "page_index": page_index, "items_found": 0}
#                 continue

#             #  ĐIỂM QUYẾT ĐỊNH: Bắt buộc cuộn trang để lấy dữ liệu thực trước khi Query
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
#             #  BÁO CÁO LOG SAU MỖI TRANG
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

#         #  KẾT THÚC VÒNG LẶP TRANG
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


# =========================
# fetcher/search_fetcher.py
# =========================
import time
from urllib.parse import quote

from captcha_solver import check_and_solve_captcha
from config import MIN_SOLD_COUNT, MAX_SEARCH_PAGE, ANCHOR_PRODUCT_LIMIT


class SearchFetcher:
    def __init__(self, page, start_page=0):
        self.page = page
        self.start_page = start_page

    # ----------------------------------------
    # CUỘN TỪNG BƯỚC (CHỐNG LAZY LOAD)
    # ----------------------------------------
    def _scroll_gradually(self):
        for i in range(1, 11):
            self.page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i/10})")
            time.sleep(0.5)
        time.sleep(1)

    # ----------------------------------------
    # PARSE SỐ LƯỢNG ĐÃ BÁN
    # ----------------------------------------
    def _parse_sold_count(self, item):
        try:
            text = item.inner_text().lower()
            sold_text = ""

            if "đã bán" in text:
                sold_text = text.split("đã bán")[1].split('\n')[0].strip()
            elif "sold" in text:
                sold_text = text.split("sold")[1].split('\n')[0].strip()
            else:
                return 0

            if "k" in sold_text:
                sold_text = sold_text.replace(",", ".")
                digits = "".join(c for c in sold_text if c.isdigit() or c == '.')
                return int(float(digits) * 1000) if digits else 0

            digits = "".join(c for c in sold_text if c.isdigit())
            return int(digits) if digits else 0
        except:
            return 0

    # ----------------------------------------
    # GENERATOR CHÍNH: DUYỆT TỪNG TRANG TÌM KIẾM
    # ----------------------------------------
    def search_and_collect_forever(self, brand, category, job_id=None):
        if not category or category.strip() == "":
            category = "ALL"

        raw_keyword = f"{category} {brand}".lower()
        keyword = quote(raw_keyword, safe="")
        seen_urls = set()

        for page_index in range(self.start_page, MAX_SEARCH_PAGE):
            url = (
                f"https://shopee.vn/search?"
                f"keyword={keyword}&sortBy=sales&page={page_index}"
            )

            print(f"\n[SearchFetcher]  Open: {url}")
            self.page.goto(url, wait_until="domcontentloaded")
            time.sleep(3)

            # TRẠM CAPTCHA
            # 2. Truyền job_id vào hàm
            if not check_and_solve_captcha(self.page, job_id=job_id):
                print("[SearchFetcher] ❌ Captcha không giải được. Bỏ qua trang này.")
                yield {"_page_done": True, "page_index": page_index, "items_found": 0}
                continue

            # KÍCH HOẠT LAZY LOAD
            print("[SearchFetcher] Đang cuộn để kích hoạt Lazy Loading...")
            self._scroll_gradually()

            items = self.page.query_selector_all('[data-sqe="item"]')
            items_found_on_dom = len(items)

            added_this_round = 0
            anchor_used = 0
            err_no_link = err_low_sold = err_dup = 0

            for item in items:
                try:
                    a = item.query_selector("a[href]")
                    if not a:
                        err_no_link += 1
                        continue

                    href = a.get_attribute("href")
                    if not href:
                        err_no_link += 1
                        continue

                    if href.startswith("/"):
                        href = "https://shopee.vn" + href

                    if href in seen_urls:
                        err_dup += 1
                        continue

                    sold = self._parse_sold_count(item)
                    if sold < MIN_SOLD_COUNT:
                        err_low_sold += 1
                        continue

                    name_el = item.query_selector('div[data-sqe="name"] > div') \
                              or item.query_selector('div[data-sqe="name"]')
                    name = name_el.inner_text().strip() if name_el else "Unknown Product"

                    seen_urls.add(href)
                    added_this_round += 1

                    is_anchor = False
                    if page_index == 0 and anchor_used < ANCHOR_PRODUCT_LIMIT:
                        is_anchor = True
                        anchor_used += 1

                    yield {
                        "url": href,
                        "name": name,
                        "sold": sold,
                        "is_anchor": is_anchor,
                        "page_index": page_index
                    }

                except Exception:
                    continue

            # BÁO CÁO SAU MỖI TRANG
            print(
                f"[SearchFetcher] Page {page_index}: "
                f"DOM={items_found_on_dom} | Lấy={added_this_round} | "
                f"NoLink={err_no_link} | LowSold={err_low_sold} | Dup={err_dup}"
            )

            # HẾT HÀNG (có DOM nhưng không lấy được gì)
            if items_found_on_dom > 0 and added_this_round == 0:
                print(f"[SearchFetcher] Tất cả SP trang này dưới chuẩn bán (<{MIN_SOLD_COUNT}). Dừng quét.")
                yield {"_page_done": True, "page_index": page_index, "items_found": 0}
                break

            # DOM TRỐNG (captcha ngầm / lỗi mạng)
            if items_found_on_dom == 0:
                print("[SearchFetcher] ⚠️ DOM trống trơn. Có thể bị chặn ngầm.")
                yield {"_page_done": True, "page_index": page_index, "items_found": 0}
                break

            yield {
                "_page_done": True,
                "page_index": page_index,
                "items_found": items_found_on_dom
            }

        yield {"_search_done": True}