"""
crawl_job_orchestrator.py

Layer A – Crawl job orchestration

Responsibility:
- Handle crawl job creation based on evaluation result
- Guard against duplicate running jobs
- Persist crawl job decision to DB
"""

from datetime import datetime
from typing import Optional

from crawler.db.db_connection import get_connection


class CrawlJobOrchestrator:
    def handle_decision(
        self,
        brand_id: int,
        category_id: int,
        recommended_action: str
    ) -> str:
        """
        Handle crawl decision based on recommended action.

        :return: Job status string
        """

        # ===============================
        # CASE 1: NO CRAWL REQUIRED
        # ===============================
        if recommended_action == "READY_FOR_ANALYSIS":
            return "NO_CRAWL_REQUIRED"

        conn = get_connection()
        cursor = conn.cursor()

        # ===============================
        # CASE 2: JOB ALREADY EXISTS
        # ===============================
        cursor.execute(
            """
            SELECT TOP 1 JobId
            FROM CrawlJob
            WHERE BrandId = ?
              AND CategoryId = ?
              AND JobStatus IN ('PENDING', 'RUNNING', 'PAUSED')
            """,
            (brand_id, category_id)
        )

        existing_job = cursor.fetchone()
        if existing_job:
            return "JOB_ALREADY_EXISTS"

        # ===============================
        # CASE 3: CREATE NEW JOB
        # ===============================
        cursor.execute(
            """
            INSERT INTO CrawlJob (
                BrandId,
                CategoryId,
                JobStatus,
                CreatedAt
            )
            VALUES (?, ?, 'PENDING', ?)
            """,
            (brand_id, category_id, datetime.now())
        )

        conn.commit()
        return "JOB_CREATED"
