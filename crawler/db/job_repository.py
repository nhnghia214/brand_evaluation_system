from db.db_connection import get_connection

def get_pending_job():
    """
    Lấy 1 CrawlJob đang ở trạng thái PENDING
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT TOP 1 JobId, BrandId, CategoryId
        FROM CrawlJob
        WHERE JobStatus = 'PENDING'
        ORDER BY CreatedAt
    """)

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "JobId": row.JobId,
        "BrandId": row.BrandId,
        "CategoryId": row.CategoryId
    }


def mark_job_running(job_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE CrawlJob
        SET JobStatus = 'RUNNING',
            StartedAt = GETDATE()
        WHERE JobId = ?
    """, job_id)

    conn.commit()
    conn.close()


def mark_job_completed(job_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE CrawlJob
        SET JobStatus = 'COMPLETED',
            FinishedAt = GETDATE()
        WHERE JobId = ?
    """, job_id)

    conn.commit()
    conn.close()
