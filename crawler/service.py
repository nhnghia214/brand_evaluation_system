# crawler/service.py
import time
from random import uniform

from crawler.db.db_connection import get_connection
from browser_manager import connect_cdp
from scheduler import CrawlWorker
from crawler.exceptions import CaptchaError
from config import PAUSE_AFTER_ERROR

from core.layer_b.analysis_service import AnalysisService


class CrawlService:
    SLEEP_SECONDS = 30

    def __init__(self):
        self.browser_ready = False
        self.worker = None
        self.analysis_service = AnalysisService()

    # ===============================
    # INIT BROWSER + WORKER
    # ===============================
    def _init_browser(self):
        if not self.browser_ready:
            print("[Crawler] Initializing browser...")
            p, browser, context, page = connect_cdp()
            self.worker = CrawlWorker(page)
            self.browser_ready = True

    # ===============================
    # MAIN LOOP
    # ===============================
    def run(self):
        print("[Crawler] Started")

        while True:
            job = self._get_next_job()

            if not job:
                time.sleep(self.SLEEP_SECONDS)
                continue

            job_id, brand_id, category_id, status = job
            print(f"[Crawler] Pick job {job_id} ({status})")

            try:
                self._init_browser()
                self._mark_running(job_id)

                # ===== RUN CRAWL =====
                self.worker.run_single_job(job_id)

            except CaptchaError as e:
                print(f"[Crawler] Captcha detected on job {job_id}: {e}")
                self._mark_paused(job_id)

                sleep_time = uniform(*PAUSE_AFTER_ERROR)
                print(f"[Crawler] Sleeping {sleep_time/60:.1f} minutes before resume")
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                print("[Crawler] Interrupted by user (Ctrl+C)")
                self._mark_paused(job_id)
                raise

            except Exception as e:
                print(f"[Crawler] Job {job_id} error:", e)
                self._mark_paused(job_id)

            finally:
                # 🔥🔥🔥 GUARANTEED SNAPSHOT UPDATE
                try:
                    print(
                        f"[Crawler] Force snapshot update "
                        f"brand={brand_id}, category={category_id}"
                    )
                    self.analysis_service._analyze_single(
                        brand_id=brand_id,
                        category_id=category_id
                    )
                except Exception as e:
                    print("[Crawler] Snapshot update failed:", e)

    # ===============================
    # GET JOB
    # ===============================
    def _get_next_job(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 1 JobId, BrandId, CategoryId, JobStatus
            FROM CrawlJob
            WHERE JobStatus IN ('PENDING')
                OR (JobStatus = 'PAUSED' AND PausedUntil <= GETDATE())
            ORDER BY CreatedAt ASC
        """)
        row = cursor.fetchone()
        conn.close()
        return row

    # ===============================
    # JOB STATUS
    # ===============================
    def _mark_running(self, job_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE CrawlJob
            SET JobStatus = 'RUNNING', StartedAt = GETDATE()
            WHERE JobId = ?
        """, (job_id,))
        conn.commit()
        conn.close()

    def _mark_paused(self, job_id, minutes=90):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE CrawlJob
            SET JobStatus = 'PAUSED',
                PausedUntil = DATEADD(MINUTE, ?, GETDATE())
            WHERE JobId = ?
        """, (minutes, job_id))
        conn.commit()
        conn.close()

