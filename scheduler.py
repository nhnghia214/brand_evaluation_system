# =========================
# scheduler.py (DEEP CRAWL – BATCH BASED + RESUME SAFE)
# =========================
import time
from random import uniform
import sys
from datetime import datetime

from crawler.exceptions import CaptchaError

from crawler.db.repositories import (
    get_brand_category,
    update_job_status,
    save_product,
    save_reviews,

    mark_product_crawling,
    mark_product_completed,
    get_product_crawl_state,
    update_review_progress,

    get_search_crawl_state,
    update_search_crawl_page,
    reset_search_crawl,

    # 🔥 DEEP CRAWL
    get_or_create_deep_batches,
    get_next_pending_batch,
    mark_deep_batch_running,
    mark_deep_batch_done
)

from crawler.utils.shopee_parser import extract_product_id
from crawler.fetcher.search_fetcher import SearchFetcher
from crawler.fetcher.review_fetcher import ReviewFetcher
from config import *


class CrawlWorker:
    def __init__(self, page):
        self.page = page
        self.current_job_id = None
        self.stop_requested = False

    def request_stop(self):
        self.stop_requested = True

    def run_single_job(self, job_id):
        job_id, brand, category, brand_id, category_id = get_brand_category(job_id)
        self.current_job_id = job_id
        update_job_status(job_id, "RUNNING")

        searcher = SearchFetcher(self.page, start_page=get_search_crawl_state(job_id))
        reviewer = ReviewFetcher(self.page)

        start_time = datetime.now()
        product_count = 0
        soft_block_count = 0
        search_soft_block_count = 0

        try:
            for item in searcher.search_and_collect_forever(brand, category):

                # ===== SEARCH PAGE DONE =====
                if "_page_done" in item:
                    page_idx = item["page_index"]

                    # Nếu trang báo "exhausted" mà không tìm thấy item nào (sự cố mạng/captcha)
                    if item.get("items_found", 0) == 0:
                        search_soft_block_count += 1
                    else:
                        search_soft_block_count = 0

                    if search_soft_block_count >= 5:
                        update_job_status(job_id, "PAUSED")
                        raise CaptchaError("Search captcha detected")

                    update_search_crawl_page(job_id, page_idx + 1)

                    if page_idx + 1 >= MAX_SEARCH_PAGE:
                        reset_search_crawl(job_id)
                        update_job_status(job_id, "COMPLETED")
                        return

                    continue

                # ===== SEARCH DONE =====
                if "_search_done" in item:
                    reset_search_crawl(job_id)
                    update_job_status(job_id, "COMPLETED")
                    return

                # ===== STOP / TIMEOUT =====
                if self.stop_requested:
                    update_job_status(job_id, "PAUSED")
                    raise CaptchaError("Manual stop")

                if (datetime.now() - start_time).total_seconds() / 60 > MAX_JOB_DURATION_MIN:
                    update_job_status(job_id, "PAUSED")
                    return

                if product_count >= MAX_PRODUCT_PER_JOB:
                    update_job_status(job_id, "PAUSED")
                    return

                # ===== PRODUCT =====
                product_id = extract_product_id(item["url"])
                if not product_id:
                    continue

                save_product(item, product_id, brand_id, category_id)

                sold = item.get("sold", 0)
                state = get_product_crawl_state(product_id)

                if state.get("status") == "COMPLETED" and sold < 500:
                    continue

                # ===== REVIEW (SAFE MODE) =====
                if sold < 500:
                    mark_product_crawling(product_id)

                    result = reviewer.crawl_reviews(
                        product=item,
                        start_offset=state.get("review_offset", 0),
                        last_review_time=state.get("last_review_time"),
                        max_reviews=SAFE_MAX_REVIEWS,
                        max_review_pages=35
                    )

                    reviews = result["reviews"] or []

                    if not reviews:
                        soft_block_count += 1
                    else:
                        soft_block_count = 0

                    if soft_block_count >= 10:
                        update_job_status(job_id, "PAUSED")
                        raise CaptchaError("Review captcha detected")

                    if reviews:
                        save_reviews(reviews, product_id)
                        update_review_progress(
                            product_id,
                            result["last_offset"],
                            result["latest_review_time"]
                        )

                    mark_product_completed(product_id)
                    product_count += 1
                    time.sleep(uniform(*DELAY_BETWEEN_PRODUCT))
                    continue

                # ===== DEEP CRAWL =====
                get_or_create_deep_batches(product_id, sold)
                batch = get_next_pending_batch(product_id)

                if not batch:
                    mark_product_completed(product_id)
                    continue

                mark_product_crawling(product_id)
                mark_deep_batch_running(batch["DeepCrawlId"])

                result = reviewer.crawl_reviews(
                    product=item,
                    start_offset=state.get("review_offset", 0),
                    last_review_time=batch["LastReviewTime"],
                    max_reviews=ANCHOR_MAX_REVIEWS,
                    max_review_pages=batch["PageEnd"] - batch["PageStart"] + 1
                )

                reviews = result["reviews"] or []

                if not reviews:
                    soft_block_count += 1
                else:
                    soft_block_count = 0

                if soft_block_count >= 5:
                    update_job_status(job_id, "PAUSED")
                    raise CaptchaError("Deep review captcha detected")

                if reviews:
                    save_reviews(reviews, product_id)
                    update_review_progress(
                        product_id,
                        result["last_offset"],
                        result["latest_review_time"]
                    )

                mark_deep_batch_done(
                    batch_id=batch["DeepCrawlId"],
                    reviews_collected=len(reviews),
                    latest_review_time=result["latest_review_time"]
                )

                product_count += 1
                time.sleep(uniform(*DELAY_BETWEEN_PRODUCT))
                
                # ĐÃ SỬA TẠI ĐÂY: Dùng continue để vòng lặp đi tiếp sang sản phẩm khác
                continue

        except CaptchaError:
            raise
