# =========================
# scheduler.py (DEEP CRAWL – BATCH BASED + RESUME SAFE)
# =========================
import time
from random import uniform
import signal
import sys
from datetime import datetime

from db.repositories import (
    get_pending_jobs,
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

    # 🔥 NEW – DEEP CRAWL
    get_or_create_deep_batches,
    get_next_pending_batch,
    mark_deep_batch_running,
    mark_deep_batch_done
)

from utils.shopee_parser import extract_product_id
from fetcher.search_fetcher import SearchFetcher
from fetcher.review_fetcher import ReviewFetcher
from config import *


class CrawlWorker:

    def __init__(self, page):
        self.page = page
        self.current_job_id = None
        self.stop_requested = False

        signal.signal(signal.SIGINT, self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)

    def _handle_stop(self, signum, frame):
        self.stop_requested = True
        if self.current_job_id:
            update_job_status(self.current_job_id, "PAUSED")
        sys.exit(0)

    def run_forever(self):
        while True:
            jobs = get_pending_jobs()
            if not jobs:
                time.sleep(60)
                continue

            for job_id in jobs:
                self.run_single_job(job_id)

            time.sleep(uniform(*DELAY_BETWEEN_JOB))

    def run_single_job(self, job_id):
        job_id, brand, category, brand_id, category_id = get_brand_category(job_id)
        self.current_job_id = job_id
        update_job_status(job_id, "RUNNING")

        start_page = get_search_crawl_state(job_id)
        searcher = SearchFetcher(self.page, start_page=start_page)
        reviewer = ReviewFetcher(self.page)

        start_time = datetime.now()
        product_count = 0
        soft_block_count = 0
        search_soft_block_count = 0
        processed_pages = set()

        try:
            for item in searcher.search_and_collect_forever(brand, category):

                # =========================
                # SEARCH PAGE DONE
                # =========================
                if "_page_done" in item:
                    page_idx = item["page_index"]
                    processed_pages.add(page_idx)

                    # 🚨 SEARCH SOFT BLOCK DETECTION
                    if item.get("items_found", 0) == 0:
                        search_soft_block_count += 1
                        print(f"⚠ Search soft-block ({search_soft_block_count}/5)")
                    else:
                        search_soft_block_count = 0

                    if search_soft_block_count >= 5:
                        print("🛑 Search captcha suspected → PAUSE & SLEEP")
                        update_job_status(job_id, "PAUSED")
                        time.sleep(uniform(*PAUSE_AFTER_ERROR))
                        return

                    update_search_crawl_page(job_id, page_idx + 1)
                    print(f"✅ Search page {page_idx} committed")

                    # 🚫 ĐÃ CHẠY HẾT PAGE CHO PHÉP → KẾT THÚC JOB
                    if page_idx + 1 >= MAX_SEARCH_PAGE:
                        print("🎯 Reached MAX_SEARCH_PAGE → JOB COMPLETED")
                        reset_search_crawl(job_id)
                        update_job_status(job_id, "COMPLETED")
                        return

                    continue

                # =========================
                # SEARCH DONE (HẾT KẾT QUẢ)
                # =========================
                if "_search_done" in item:
                    print("🎯 Search exhausted → JOB COMPLETED")
                    reset_search_crawl(job_id)
                    update_job_status(job_id, "COMPLETED")
                    return

                # =========================
                # STOP / TIMEOUT
                # =========================
                if self.stop_requested:
                    update_job_status(job_id, "PAUSED")
                    return

                if (datetime.now() - start_time).total_seconds() / 60 > MAX_JOB_DURATION_MIN:
                    update_job_status(job_id, "PAUSED")
                    return

                if product_count >= MAX_PRODUCT_PER_JOB:
                    update_job_status(job_id, "PAUSED")
                    return

                # =========================
                # PRODUCT
                # =========================
                product_id = extract_product_id(item["url"])
                if not product_id:
                    continue

                save_product(item, product_id, brand_id, category_id)

                sold = item.get("sold", 0)
                state = get_product_crawl_state(product_id)

                # ⛔ sản phẩm nghèo & đã crawl → bỏ
                if state.get("status") == "COMPLETED" and sold < 500:
                    continue

                # =========================
                # 🎯 REVIEW STRATEGY
                # =========================

                # 🔹 CASE 1: Sản phẩm < 500 review → crawl nhẹ
                if sold < 500:
                    mark_product_crawling(product_id)

                    result = reviewer.crawl_reviews(
                        product=item,
                        start_offset=state.get("review_offset", 0),
                        last_review_time=state.get("last_review_time"),
                        max_reviews=SAFE_MAX_REVIEWS,  # ~6
                        max_review_pages=1
                    )

                    reviews = result["reviews"] or []

                    # =========================
                    # 🚨 SOFT CAPTCHA DETECTION
                    # =========================
                    if len(reviews) == 0:
                        soft_block_count += 1
                        print(f"⚠ Soft-block detected ({soft_block_count}/3)")
                    else:
                        soft_block_count = 0

                    if soft_block_count >= 3:
                        print("🛑 Too many empty review pages → PAUSE & SLEEP")
                        update_job_status(job_id, "PAUSED")
                        time.sleep(uniform(*PAUSE_AFTER_ERROR))
                        return

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

                # 🔥 CASE 2: Sản phẩm >= 500 review → DEEP CRAWL
                get_or_create_deep_batches(product_id, sold)

                batch = get_next_pending_batch(product_id)
                if not batch:
                    mark_product_completed(product_id)
                    continue

                mark_product_crawling(product_id)
                mark_deep_batch_running(batch["DeepCrawlId"])

                print(
                    f"🔥 Deep crawl product={product_id} "
                    f"batch={batch['BatchIndex']} "
                    f"pages={batch['PageStart']}→{batch['PageEnd']}"
                )

                # =========================
                # REVIEW CRAWL – 1 BATCH
                # =========================
                result = reviewer.crawl_reviews(
                    product=item,
                    start_offset=state.get("review_offset", 0),
                    last_review_time=batch["LastReviewTime"],
                    max_reviews=9999,
                    max_review_pages=batch["PageEnd"] - batch["PageStart"] + 1
                )

                reviews = result["reviews"] or []

                # =========================
                # 🚨 SOFT CAPTCHA DETECTION
                # =========================
                if len(reviews) == 0:
                    soft_block_count += 1
                    print(f"⚠ Soft-block detected ({soft_block_count}/3)")
                else:
                    soft_block_count = 0

                if soft_block_count >= 3:
                    print("🛑 Too many empty review pages → PAUSE & SLEEP")
                    update_job_status(job_id, "PAUSED")
                    time.sleep(uniform(*PAUSE_AFTER_ERROR))
                    return

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

            # 🔚 FOR LOOP HẾT → JOB XONG
            print("🎯 No more search results → JOB COMPLETED")
            reset_search_crawl(job_id)
            update_job_status(job_id, "COMPLETED")

        except Exception as e:
            print("⚠ Scheduler error:", e)
            update_job_status(job_id, "PAUSED")
            time.sleep(uniform(*PAUSE_AFTER_ERROR))

