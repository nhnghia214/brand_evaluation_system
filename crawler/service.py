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

            job_resolved = False  # Cờ để kiểm soát khối finally

            try:
                self._init_browser()
                self._mark_running(job_id)

                # ===== RUN CRAWL =====
                self.worker.run_single_job(job_id)

                # KIỂM TRA LẠI TRẠNG THÁI THỰC TẾ TRONG DATABASE SAU KHI CHẠY XONG
                # Thay vì tự ý set COMPLETED, ta tôn trọng trạng thái do scheduler.py quyết định
                current_status = self._get_job_status_from_db(job_id)
                print(f"[Crawler] Job {job_id} stopped. Current status in DB: {current_status}")
                job_resolved = True

            except CaptchaError as e:
                print(f"[Crawler] Captcha detected on job {job_id}: {e}")
                self._mark_paused(job_id) # Mặc định 90 phút
                job_resolved = True
                
                sleep_time = uniform(*PAUSE_AFTER_ERROR)
                print(f"[Crawler] Sleeping {sleep_time/60:.1f} minutes before resume")
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                print("[Crawler] Interrupted by user (Ctrl+C)")
                self._mark_paused(job_id, minutes=0)
                job_resolved = True
                raise

            except Exception as e:
                print(f"[Crawler] Job {job_id} error:", e)
                self._mark_paused(job_id) # Set 90 phút để sau chạy lại
                job_resolved = True

            finally:
                # 🔥 CHỈ GIẢI PHÓNG NẾU CÓ LỖI CHƯA ĐƯỢC XỬ LÝ (Crash ngầm)
                if not job_resolved:
                    try:
                        print(f"[Crawler] Fallback: Releasing stuck job {job_id} to PAUSED.")
                        self._mark_paused(job_id, minutes=0)
                    except Exception as e:
                        print(f"[Crawler] Failed to release job {job_id}: {e}")

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
                OR (JobStatus = 'PAUSED' AND (PausedUntil IS NULL OR PausedUntil <= GETDATE()))
            ORDER BY CreatedAt ASC
        """)
        row = cursor.fetchone()
        conn.close()
        return row

    def _get_job_status_from_db(self, job_id):
        """Hỏi lại Database xem trạng thái hiện tại thực sự là gì"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT JobStatus FROM CrawlJob WHERE JobId = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        return row.JobStatus if row else "UNKNOWN"

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

    def _mark_completed(self, job_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE CrawlJob
            SET JobStatus = 'COMPLETED'
            WHERE JobId = ?
        """, (job_id,))
        conn.commit()
        conn.close()