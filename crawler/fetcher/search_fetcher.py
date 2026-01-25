# =========================
# fetcher/search_fetcher.py (FINAL – RESUME + SMART ANCHOR + NO DEAD LOOP)
# =========================
import time
from crawler.utils.sleeper import short_sleep
from config import MIN_SOLD_COUNT, MAX_SEARCH_PAGE, ANCHOR_PRODUCT_LIMIT
from urllib.parse import quote

class SearchFetcher:
    def __init__(self, page, start_page=0):
        self.page = page
        self.start_page = start_page

    def search_and_collect_forever(self, brand, category):

        if not category or category.strip() == "":
            category = "ALL"

        raw_keyword = f"{category} {brand}".lower()
        keyword = quote(raw_keyword, safe="")

        seen_urls = set()

        for page_index in range(self.start_page, MAX_SEARCH_PAGE):
            url = (
                "https://shopee.vn/search?"
                f"keyword={keyword}&sortBy=sales&page={page_index}"
            )

            print(f"[SearchFetcher] Open: {url}")
            self.page.goto(url, wait_until="domcontentloaded")
            time.sleep(5)

            empty_round = 0
            anchor_used = 0

            while True:
                items = self.page.query_selector_all(
                    "li.shopee-search-item-result__item"
                )

                added_this_round = 0  # 🔑 CHỐNG TREO

                for item in items:
                    try:
                        sold = self._parse_sold_count(item)
                        if sold < MIN_SOLD_COUNT:
                            continue

                        a = item.query_selector("a.contents")
                        if not a:
                            continue

                        href = a.get_attribute("href")
                        if not href:
                            continue

                        if href.startswith("/"):
                            href = "https://shopee.vn" + href

                        # ❌ ĐÃ GẶP → BỎ QUA
                        if href in seen_urls:
                            continue

                        # ✅ SẢN PHẨM MỚI THỰC SỰ
                        seen_urls.add(href)
                        added_this_round += 1

                        name_el = item.query_selector("div.line-clamp-2")
                        name = name_el.inner_text().strip() if name_el else None

                        # =============================
                        # 🔥 SMART ANCHOR
                        # - Chỉ page 0
                        # - Chỉ vài sản phẩm bán cao
                        # =============================
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

                # =============================
                # 🔑 LOGIC BREAK PAGE ĐÚNG
                # =============================
                if added_this_round == 0:
                    empty_round += 1
                else:
                    empty_round = 0

                if empty_round >= 3:
                    print(f"[SearchFetcher] Page {page_index} exhausted")
                    break

                # scroll nhẹ để load thêm (an toàn)
                self.page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )
                short_sleep()

            # 🔁 THÔNG BÁO HOÀN TẤT PAGE
            yield {
                "_page_done": True,
                "page_index": page_index,
                "empty_round": empty_round,
                "items_found": len(items)
            }

        # 🔚 THÔNG BÁO KẾT THÚC SEARCH
        yield {"_search_done": True}

    # =============================
    # PARSE SOLD COUNT
    # =============================
    def _parse_sold_count(self, item):
        sold_el = item.query_selector("div.truncate.text-shopee-black87")
        if not sold_el:
            return 0

        text = sold_el.inner_text().lower()

        if "k" in text:
            digits = "".join(c for c in text if c.isdigit())
            return int(digits) * 1000 if digits else 0

        digits = "".join(c for c in text if c.isdigit())
        return int(digits) if digits else 0
