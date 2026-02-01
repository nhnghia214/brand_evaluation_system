"""
crawl_job_orchestrator.py

Layer A – Crawl job orchestration
"""

from datetime import datetime
from crawler.db.db_connection import get_connection


class CrawlJobOrchestrator:
    def handle_decision(
        self,
        brand_id: int,
        category_id: int,
        recommended_action: str
    ) -> str:

        # ===============================
        # CASE 1: KHÔNG CẦN CRAWL
        # ===============================
        if recommended_action == "READY_FOR_ANALYSIS":
            return "NO_CRAWL_REQUIRED"

        conn = get_connection()
        cursor = conn.cursor()

        # ===============================
        # CASE 2: ĐÃ CÓ JOB ĐANG HOẠT ĐỘNG
        # ===============================
        cursor.execute("""
            SELECT TOP 1 JobId
            FROM CrawlJob
            WHERE BrandId = ?
              AND CategoryId = ?
              AND JobStatus IN ('PENDING', 'RUNNING', 'PAUSED')
        """, (brand_id, category_id))

        row = cursor.fetchone()
        if row:
            conn.close()
            return "JOB_ALREADY_EXISTS"

        # ===============================
        # CASE 3: CHỈ CÒN JOB COMPLETED → TẠO JOB MỚI
        # ===============================
        cursor.execute("""
            INSERT INTO CrawlJob (
                BrandId,
                CategoryId,
                JobStatus,
                CreatedAt
            )
            VALUES (?, ?, 'PENDING', ?)
        """, (brand_id, category_id, datetime.now()))

        conn.commit()
        conn.close()
        return "JOB_RECREATED"
