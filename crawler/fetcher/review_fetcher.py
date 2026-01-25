# =========================
# fetcher/review_fetcher.py
# FINAL – DEEP CRAWL STATE (BATCH SAFE + STABLE)
# =========================
import time
from datetime import datetime


class ReviewFetcher:
    """
    REVIEW FETCHER – SHOPEE DEEP CRAWL (STABLE)

    ✔ Hook network theo ĐÚNG product page
    ✔ Click pagination có kiểm soát (theo batch)
    ✔ Không click vượt page
    ✔ Không thoát product sớm
    ✔ Thu review CHẮC CHẮN hoặc dừng an toàn
    """

    def __init__(self, page):
        self.page = page

    # =========================
    # NETWORK HANDLER (PER PRODUCT PAGE)
    # =========================
    def _handle_response(self, response, reviews, activity):
        url = response.url
        if "api/v2/item/get_ratings" not in url:
            return

        try:
            data = response.json()
        except:
            return

        ratings = data.get("data", {}).get("ratings", [])
        if not ratings:
            return

        activity["last"] = time.time()

        for r in ratings:
            rid = r.get("cmtid")
            if not rid or rid in reviews:
                continue

            reviews[rid] = {
                "review_id": rid,
                "rating": r.get("rating_star"),
                "comment": r.get("comment"),
                "review_time": self._parse_ctime(r.get("ctime"))
            }

    def _parse_ctime(self, ctime):
        try:
            return datetime.fromtimestamp(ctime)
        except:
            return None

    # =========================
    # UI HELPERS
    # =========================
    def _scroll_like_human(self, page, rounds=1, step=450, delay=1.2):
        for _ in range(rounds):
            page.evaluate(f"window.scrollBy(0, {step})")
            time.sleep(delay)

    def _click_next_review_page(self, page):
        """
        Click nút pagination ">"
        Chỉ click khi:
        - Nút tồn tại
        - Không disabled
        """
        try:
            next_btn = page.query_selector(
                "button.shopee-icon-button--right"
            )
            if not next_btn:
                return False

            cls = next_btn.get_attribute("class") or ""
            if "disabled" in cls:
                return False

            next_btn.scroll_into_view_if_needed()
            time.sleep(1)

            next_btn.click()
            time.sleep(5)  # 🔑 CHỜ ĐỦ LÂU để API bắn

            return True
        except:
            return False

    # =========================
    # PUBLIC API – DEEP BATCH
    # =========================
    def crawl_reviews(
        self,
        product,
        start_offset=0,
        last_review_time=None,
        max_reviews=30,
        max_review_pages=1,
        max_idle_seconds=25
    ):
        """
        Crawl review theo batch page (DeepCrawlState)

        max_review_pages = PageEnd - PageStart + 1
        """

        reviews = {}
        activity = {"last": time.time()}

        product_page = self.page.context.new_page()

        try:
            # 🔒 Hook response CHỈ trong page này
            product_page.on(
                "response",
                lambda r: self._handle_response(r, reviews, activity)
            )

            print(f"[ReviewFetcher] Open product: {product['url']}")
            product_page.goto(product["url"], wait_until="domcontentloaded")
            time.sleep(5)

            # Scroll xuống khu review (BẮT BUỘC)
            self._scroll_like_human(product_page, rounds=5)

            current_page = 1
            last_count = 0
            idle_round = 0

            while True:
                # =========================
                # STOP CONDITIONS
                # =========================
                if current_page > max_review_pages:
                    break

                if max_review_pages == 1 and len(reviews) >= max_reviews:
                    break

                if time.time() - activity["last"] > max_idle_seconds:
                    idle_round += 1
                else:
                    idle_round = 0

                if idle_round >= 2:
                    break

                # =========================
                # FORCE LOAD REVIEWS
                # =========================
                self._scroll_like_human(product_page, rounds=2)
                time.sleep(2)

                # =========================
                # PAGINATION
                # =========================
                if len(reviews) == last_count:
                    clicked = self._click_next_review_page(product_page)
                    if not clicked:
                        break
                    current_page += 1
                    last_count = len(reviews)
                    continue

                last_count = len(reviews)

            result = list(reviews.values())

            # PHASE 2 (sau này): lọc review mới
            if last_review_time:
                result = [
                    r for r in result
                    if r["review_time"] and r["review_time"] > last_review_time
                ]

            latest_time = max(
                (r["review_time"] for r in result if r["review_time"]),
                default=last_review_time
            )

            print(
                f"[ReviewFetcher] DONE – pages={current_page - 1}, "
                f"reviews={len(result)}"
            )

            return {
                "reviews": result,
                "last_offset": start_offset,
                "latest_review_time": latest_time
            }

        finally:
            product_page.close()
