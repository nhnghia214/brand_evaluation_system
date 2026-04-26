# # ======================================================
# # repositories.py 
# # ======================================================

# from crawler.db.db_connection import get_connection
# from datetime import datetime


# # ======================================================
# # PRODUCT
# # ======================================================

# def save_product(product, product_id, brand_id, category_id):
#     product_id = str(product_id)

#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         IF NOT EXISTS (SELECT 1 FROM Product WHERE ProductId = ?)
#         INSERT INTO Product (
#             ProductId,
#             ProductName,
#             BrandId,
#             CategoryId,
#             ProductUrl,
#             CreatedAt
#         )
#         VALUES (?, ?, ?, ?, ?, ?)
#     """,
#         product_id,
#         product_id,
#         product.get("name"),
#         brand_id,
#         category_id,
#         product.get("url"),
#         datetime.now()
#     )

#     conn.commit()
#     conn.close()


# # ======================================================
# # REVIEW
# # ======================================================

# def save_reviews(reviews, product_id):
#     from datetime import datetime
#     from crawler.db.db_connection import get_connection

#     product_id = str(product_id)

#     conn = get_connection()
#     cursor = conn.cursor()

#     for r in reviews:
#         cursor.execute("""
#             IF NOT EXISTS (
#                 SELECT 1 FROM Review WHERE ReviewId = ?
#             )
#             BEGIN
#                 INSERT INTO Review (
#                     ReviewId,
#                     ProductId,
#                     Rating,
#                     Comment,
#                     ReviewTime,
#                     CollectedAt
#                 )
#                 VALUES (?, ?, ?, ?, ?, ?)
#             END
#         """,
#             r["review_id"],          # IF
#             r["review_id"],          # ReviewId
#             product_id,              # ProductId
#             r.get("rating"),
#             r.get("comment"),
#             r.get("review_time"),
#             datetime.now()
#         )

#     conn.commit()
#     conn.close()



# # ======================================================
# # BRAND / CATEGORY
# # ======================================================

# def get_or_create_brand(brand_name):
#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute(
#         "SELECT BrandId FROM Brand WHERE BrandName = ?",
#         brand_name
#     )
#     row = cursor.fetchone()

#     if row:
#         brand_id = row[0]
#     else:
#         cursor.execute("""
#             INSERT INTO Brand (BrandName, CreatedAt)
#             OUTPUT INSERTED.BrandId
#             VALUES (?, ?)
#         """, brand_name, datetime.now())
#         brand_id = cursor.fetchone()[0]
#         conn.commit()

#     conn.close()
#     return brand_id


# def get_or_create_category(category_name):
#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute(
#         "SELECT CategoryId FROM Category WHERE CategoryName = ?",
#         category_name
#     )
#     row = cursor.fetchone()

#     if row:
#         category_id = row[0]
#     else:
#         cursor.execute("""
#             INSERT INTO Category (CategoryName, Platform, CreatedAt)
#             OUTPUT INSERTED.CategoryId
#             VALUES (?, 'Shopee', ?)
#         """, category_name, datetime.now())
#         category_id = cursor.fetchone()[0]
#         conn.commit()

#     conn.close()
#     return category_id


# # ======================================================
# # JOB
# # ======================================================

# def create_job(brand, category):
#     brand_id = get_or_create_brand(brand)
#     category_id = get_or_create_category(category)

#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         INSERT INTO CrawlJob (BrandId, CategoryId, JobStatus, CreatedAt)
#         OUTPUT INSERTED.JobId
#         VALUES (?, ?, 'PENDING', ?)
#     """, brand_id, category_id, datetime.now())

#     job_id = cursor.fetchone()[0]
#     conn.commit()
#     conn.close()

#     return job_id


# def update_job_status(job_id, status):
#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         UPDATE CrawlJob
#         SET JobStatus = ?, FinishedAt = ?
#         WHERE JobId = ?
#     """, status, datetime.now(), job_id)

#     conn.commit()
#     conn.close()


# def get_pending_jobs():
#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         SELECT JobId
#         FROM CrawlJob
#         WHERE JobStatus IN ('PENDING', 'PAUSED')
#         ORDER BY CreatedAt ASC
#     """)

#     job_ids = [row[0] for row in cursor.fetchall()]
#     conn.close()
#     return job_ids


# def get_brand_category(job_id):
#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         SELECT
#             j.JobId,
#             b.BrandName,
#             c.CategoryName,
#             b.BrandId,
#             c.CategoryId
#         FROM CrawlJob j
#         JOIN Brand b ON j.BrandId = b.BrandId
#         JOIN Category c ON j.CategoryId = c.CategoryId
#         WHERE j.JobId = ?
#     """, job_id)

#     row = cursor.fetchone()
#     conn.close()
#     return row


# # ======================================================
# # PRODUCT CRAWL STATE
# # ======================================================

# def mark_product_crawling(product_id):
#     product_id = str(product_id)

#     conn = get_connection()
#     cursor = conn.cursor()

#     # Kiểm tra xem product đã có state chưa
#     cursor.execute("SELECT 1 FROM ProductCrawlState WHERE ProductId = ?", product_id)
#     exists = cursor.fetchone()

#     if not exists:
#         cursor.execute("""
#             INSERT INTO ProductCrawlState (
#                 ProductId, Status, ReviewOffset, LastReviewTime
#             )
#             VALUES (?, 'COLLECTING', 0, NULL)
#         """, product_id)
#     else:
#         cursor.execute("""
#             UPDATE ProductCrawlState
#             SET Status = 'COLLECTING'
#             WHERE ProductId = ?
#         """, product_id)

#     conn.commit()
#     conn.close()


# def mark_product_completed(product_id):
#     product_id = str(product_id)

#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         UPDATE ProductCrawlState
#         SET Status = 'COMPLETED',
#             LastCrawledAt = GETDATE()
#         WHERE ProductId = ?
#     """, product_id)

#     conn.commit()
#     conn.close()


# def get_product_crawl_state(product_id):
#     product_id = str(product_id)

#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         SELECT ReviewOffset, LastReviewTime, Status
#         FROM ProductCrawlState
#         WHERE ProductId = ?
#     """, product_id)

#     row = cursor.fetchone()
#     conn.close()

#     if not row:
#         return {}

#     return {
#         "review_offset": row[0] or 0,
#         "last_review_time": row[1],
#         "status": row[2]
#     }


# def update_review_progress(product_id, review_offset, last_review_time):
#     product_id = str(product_id)

#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         UPDATE ProductCrawlState
#         SET ReviewOffset = ?, LastReviewTime = ?
#         WHERE ProductId = ?
#     """, review_offset, last_review_time, product_id)

#     conn.commit()
#     conn.close()


# # ======================================================
# # SEARCH CRAWL STATE
# # ======================================================

# def get_search_crawl_state(job_id):
#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         SELECT CurrentPage
#         FROM SearchCrawlState
#         WHERE JobId = ?
#     """, job_id)

#     row = cursor.fetchone()
#     conn.close()
#     return row[0] if row else 0


# def update_search_crawl_page(job_id, page_index):
#     conn = get_connection()
#     cursor = conn.cursor()

#     # 1️⃣ thử UPDATE trước
#     cursor.execute("""
#         UPDATE SearchCrawlState
#         SET CurrentPage = ?, UpdatedAt = GETDATE()
#         WHERE JobId = ?
#     """, page_index, job_id)

#     # 2️⃣ nếu chưa có row → INSERT
#     if cursor.rowcount == 0:
#         cursor.execute("""
#             INSERT INTO SearchCrawlState (JobId, CurrentPage, UpdatedAt)
#             VALUES (?, ?, GETDATE())
#         """, job_id, page_index)

#     conn.commit()
#     conn.close()



# def reset_search_crawl(job_id):
#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         DELETE FROM SearchCrawlState WHERE JobId = ?
#     """, job_id)

#     conn.commit()
#     conn.close()


# # ======================================================
# # 🔥 DEEP CRAWL STATE (BATCH BASED)
# # ======================================================

# def get_or_create_deep_batches(product_id, sold):
#     product_id = str(product_id)

#     if sold < 500:
#         return

#     if sold >= 1000:
#         review_tier = "HIGH"
#         total_pages = 35
#     else:
#         review_tier = "MID"
#         total_pages = 35

#     batch_size = 35

#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         SELECT COUNT(*) FROM DeepCrawlState WHERE ProductId = ?
#     """, product_id)

#     if cursor.fetchone()[0] > 0:
#         conn.close()
#         return

#     batch_index = 1
#     for start in range(1, total_pages + 1, batch_size):
#         end = min(start + batch_size - 1, total_pages)

#         cursor.execute("""
#             INSERT INTO DeepCrawlState (
#                 ProductId,
#                 ReviewTier,
#                 BatchIndex,
#                 PageStart,
#                 PageEnd,
#                 BatchStatus,
#                 ReviewsCollected,
#                 CreatedAt
#             )
#             VALUES (?, ?, ?, ?, ?, 'PENDING', 0, GETDATE())
#         """,
#             product_id,
#             review_tier,
#             batch_index,
#             start,
#             end
#         )

#         batch_index += 1

#     conn.commit()
#     conn.close()


# def get_next_pending_batch(product_id):
#     product_id = str(product_id)

#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         SELECT TOP 1
#             DeepCrawlId,
#             BatchIndex,
#             PageStart,
#             PageEnd,
#             LastReviewTime
#         FROM DeepCrawlState
#         WHERE ProductId = ?
#           AND BatchStatus = 'PENDING'
#         ORDER BY BatchIndex ASC
#     """, product_id)

#     row = cursor.fetchone()
#     conn.close()

#     if not row:
#         return None

#     return {
#         "DeepCrawlId": row[0],
#         "BatchIndex": row[1],
#         "PageStart": row[2],
#         "PageEnd": row[3],
#         "LastReviewTime": row[4]
#     }


# def mark_deep_batch_running(batch_id):
#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         UPDATE DeepCrawlState
#         SET BatchStatus = 'RUNNING',
#             UpdatedAt = GETDATE()
#         WHERE DeepCrawlId = ?
#     """, batch_id)

#     conn.commit()
#     conn.close()


# def mark_deep_batch_done(batch_id, reviews_collected, latest_review_time):
#     conn = get_connection()
#     cursor = conn.cursor()

#     cursor.execute("""
#         UPDATE DeepCrawlState
#         SET BatchStatus = 'DONE',
#             ReviewsCollected = ?,
#             LastReviewTime = ?,
#             UpdatedAt = GETDATE()
#         WHERE DeepCrawlId = ?
#     """,
#         reviews_collected,
#         latest_review_time,
#         batch_id
#     )

#     conn.commit()
#     conn.close()

# ======================================================
# repositories.py 
# ======================================================

from crawler.db.db_connection import get_connection
from datetime import datetime


# ======================================================
# PRODUCT
# ======================================================

def save_product(product, product_id, brand_id, category_id):
    product_id = str(product_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM Product WHERE ProductId = ?)
        INSERT INTO Product (
            ProductId,
            ProductName,
            BrandId,
            CategoryId,
            ProductUrl,
            CreatedAt
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        product_id,
        product_id,
        product.get("name"),
        brand_id,
        category_id,
        product.get("url"),
        datetime.now()
    )

    conn.commit()
    conn.close()


# ======================================================
# REVIEW
# ======================================================

def save_reviews(reviews, product_id):
    from datetime import datetime
    from crawler.db.db_connection import get_connection

    product_id = str(product_id)

    conn = get_connection()
    cursor = conn.cursor()

    for r in reviews:
        cursor.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM Review WHERE ReviewId = ?
            )
            BEGIN
                INSERT INTO Review (
                    ReviewId,
                    ProductId,
                    Rating,
                    Comment,
                    ReviewTime,
                    CollectedAt
                )
                VALUES (?, ?, ?, ?, ?, ?)
            END
        """,
            r["review_id"],          # IF
            r["review_id"],          # ReviewId
            product_id,              # ProductId
            r.get("rating"),
            r.get("comment"),
            r.get("review_time"),
            datetime.now()
        )

    conn.commit()
    conn.close()



# ======================================================
# BRAND / CATEGORY
# ======================================================

def get_or_create_brand(brand_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT BrandId FROM Brand WHERE BrandName = ?",
        brand_name
    )
    row = cursor.fetchone()

    if row:
        brand_id = row[0]
    else:
        cursor.execute("""
            INSERT INTO Brand (BrandName, CreatedAt)
            OUTPUT INSERTED.BrandId
            VALUES (?, ?)
        """, brand_name, datetime.now())
        brand_id = cursor.fetchone()[0]
        conn.commit()

    conn.close()
    return brand_id


def get_or_create_category(category_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT CategoryId FROM Category WHERE CategoryName = ?",
        category_name
    )
    row = cursor.fetchone()

    if row:
        category_id = row[0]
    else:
        cursor.execute("""
            INSERT INTO Category (CategoryName, Platform, CreatedAt)
            OUTPUT INSERTED.CategoryId
            VALUES (?, 'Shopee', ?)
        """, category_name, datetime.now())
        category_id = cursor.fetchone()[0]
        conn.commit()

    conn.close()
    return category_id


# ======================================================
# JOB
# ======================================================

def create_job(brand, category):
    brand_id = get_or_create_brand(brand)
    category_id = get_or_create_category(category)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO CrawlJob (BrandId, CategoryId, JobStatus, CreatedAt)
        OUTPUT INSERTED.JobId
        VALUES (?, ?, 'PENDING', ?)
    """, brand_id, category_id, datetime.now())

    job_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()

    return job_id


def update_job_status(job_id, status):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE CrawlJob
        SET JobStatus = ?, FinishedAt = ?
        WHERE JobId = ?
    """, status, datetime.now(), job_id)

    conn.commit()
    conn.close()


def get_pending_jobs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT JobId
        FROM CrawlJob
        WHERE JobStatus IN ('PENDING', 'PAUSED')
        ORDER BY CreatedAt ASC
    """)

    job_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return job_ids


def get_brand_category(job_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            j.JobId,
            b.BrandName,
            c.CategoryName,
            b.BrandId,
            c.CategoryId
        FROM CrawlJob j
        JOIN Brand b ON j.BrandId = b.BrandId
        JOIN Category c ON j.CategoryId = c.CategoryId
        WHERE j.JobId = ?
    """, job_id)

    row = cursor.fetchone()
    conn.close()
    return row


# ======================================================
# PRODUCT CRAWL STATE
# ======================================================

def mark_product_crawling(product_id):
    product_id = str(product_id)

    conn = get_connection()
    cursor = conn.cursor()

    # Kiểm tra xem product đã có state chưa
    cursor.execute("SELECT 1 FROM ProductCrawlState WHERE ProductId = ?", product_id)
    exists = cursor.fetchone()

    if not exists:
        cursor.execute("""
            INSERT INTO ProductCrawlState (
                ProductId, Status, ReviewOffset, LastReviewTime
            )
            VALUES (?, 'COLLECTING', 0, NULL)
        """, product_id)
    else:
        cursor.execute("""
            UPDATE ProductCrawlState
            SET Status = 'COLLECTING'
            WHERE ProductId = ?
        """, product_id)

    conn.commit()
    conn.close()


def mark_product_completed(product_id):
    product_id = str(product_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE ProductCrawlState
        SET Status = 'COMPLETED',
            LastCrawledAt = GETDATE()
        WHERE ProductId = ?
    """, product_id)

    conn.commit()
    conn.close()


def get_product_crawl_state(product_id):
    product_id = str(product_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ReviewOffset, LastReviewTime, Status
        FROM ProductCrawlState
        WHERE ProductId = ?
    """, product_id)

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {}

    return {
        "review_offset": row[0] or 0,
        "last_review_time": row[1],
        "status": row[2]
    }


def update_review_progress(product_id, review_offset, last_review_time):
    product_id = str(product_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE ProductCrawlState
        SET ReviewOffset = ?, LastReviewTime = ?
        WHERE ProductId = ?
    """, review_offset, last_review_time, product_id)

    conn.commit()
    conn.close()


# ======================================================
# SEARCH CRAWL STATE
# ======================================================

def get_search_crawl_state(job_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT CurrentPage
        FROM SearchCrawlState
        WHERE JobId = ?
    """, job_id)

    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0


def update_search_crawl_page(job_id, page_index):
    conn = get_connection()
    cursor = conn.cursor()

    # 1️⃣ thử UPDATE trước
    cursor.execute("""
        UPDATE SearchCrawlState
        SET CurrentPage = ?, UpdatedAt = GETDATE()
        WHERE JobId = ?
    """, page_index, job_id)

    # 2️⃣ nếu chưa có row → INSERT
    if cursor.rowcount == 0:
        cursor.execute("""
            INSERT INTO SearchCrawlState (JobId, CurrentPage, UpdatedAt)
            VALUES (?, ?, GETDATE())
        """, job_id, page_index)

    conn.commit()
    conn.close()



def reset_search_crawl(job_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM SearchCrawlState WHERE JobId = ?
    """, job_id)

    conn.commit()
    conn.close()


# ======================================================
# 🔥 DEEP CRAWL STATE (ROUND-ROBIN BATCH BASED)
# ======================================================

def get_or_create_deep_batches(product_id, sold):
    product_id = str(product_id)

    # BƯỚC 1: TÍNH TOÁN DƯ GIẢ SỐ TRANG DỰA TRÊN LƯỢT BÁN
    # Giả sử tỷ lệ tối đa: Cứ 2 người mua thì có 1 người đánh giá. (1 trang = 6 đánh giá)
    estimated_pages = (sold // 12) + 10 
    
    # BƯỚC 2: THIẾT LẬP MỨC TRẦN VẬT LÝ (SHOPEE API LIMIT)
    # Đẩy lên 2000 trang (Tương đương 12.000 review - vắt kiệt giới hạn phân trang của Shopee)
    if estimated_pages > 2000:
        estimated_pages = 2000
        
    # BƯỚC 3: NẾU SẢN PHẨM BÁN QUÁ ÍT, VẪN CHO NÓ TỐI THIỂU 1 LÔ ĐỂ QUÉT
    if estimated_pages < 35:
        estimated_pages = 35

    batch_size = 35 

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM DeepCrawlState WHERE ProductId = ?", product_id)
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    batch_index = 1
    # Xắt nhỏ số trang tính được thành các Lô 35 trang
    for start in range(1, estimated_pages + 1, batch_size):
        end = min(start + batch_size - 1, estimated_pages)
        
        cursor.execute("""
            INSERT INTO DeepCrawlState (
                ProductId, ReviewTier, BatchIndex, PageStart, PageEnd, BatchStatus, ReviewsCollected, CreatedAt
            )
            VALUES (?, 'HIGH', ?, ?, ?, 'PENDING', 0, GETDATE())
        """, product_id, batch_index, start, end)
        
        batch_index += 1

    conn.commit()
    conn.close()


def get_next_round_robin_batch(brand_id, category_id):
    """
    THUẬT TOÁN ROUND-ROBIN: 
    Lấy Lô PENDING tiếp theo dựa theo BatchIndex. 
    Hệ thống sẽ bốc toàn bộ Batch 1 của TẤT CẢ sản phẩm trước, xong xuôi mới tới Batch 2, Batch 3...
    Tuyệt đối an toàn và giống hệt hành vi người dùng đang lướt dạo.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT TOP 1
            d.DeepCrawlId,
            d.ProductId,
            d.BatchIndex,
            d.PageStart,
            d.PageEnd,
            d.LastReviewTime,
            p.ProductUrl
        FROM DeepCrawlState d
        JOIN Product p ON d.ProductId = p.ProductId
        WHERE p.BrandId = ? AND p.CategoryId = ?
          AND d.BatchStatus = 'PENDING'
        ORDER BY d.BatchIndex ASC, d.ProductId ASC
    """, brand_id, category_id)

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "DeepCrawlId": row[0],
        "ProductId": row[1],
        "BatchIndex": row[2],
        "PageStart": row[3],
        "PageEnd": row[4],
        "LastReviewTime": row[5],
        "ProductUrl": row[6]
    }   


def get_next_pending_batch(product_id):
    product_id = str(product_id)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT TOP 1
            DeepCrawlId,
            BatchIndex,
            PageStart,
            PageEnd,
            LastReviewTime
        FROM DeepCrawlState
        WHERE ProductId = ?
          AND BatchStatus = 'PENDING'
        ORDER BY BatchIndex ASC
    """, product_id)

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "DeepCrawlId": row[0],
        "BatchIndex": row[1],
        "PageStart": row[2],
        "PageEnd": row[3],
        "LastReviewTime": row[4]
    }


def mark_deep_batch_running(batch_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE DeepCrawlState
        SET BatchStatus = 'RUNNING',
            UpdatedAt = GETDATE()
        WHERE DeepCrawlId = ?
    """, batch_id)

    conn.commit()
    conn.close()


def mark_deep_batch_done(batch_id, reviews_collected, latest_review_time):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE DeepCrawlState
        SET BatchStatus = 'DONE',
            ReviewsCollected = ?,
            LastReviewTime = ?,
            UpdatedAt = GETDATE()
        WHERE DeepCrawlId = ?
    """,
        reviews_collected,
        latest_review_time,
        batch_id
    )

    conn.commit()
    conn.close()


def cancel_remaining_batches(product_id):
    """
    Hủy tất cả các lô đang chờ (PENDING) của một sản phẩm
    khi phát hiện sản phẩm đó đã cạn kiệt đánh giá sớm hơn dự kiến.
    """
    product_id = str(product_id)
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE DeepCrawlState
            SET BatchStatus = 'CANCELED',
                UpdatedAt = GETDATE()
            WHERE ProductId = ? AND BatchStatus = 'PENDING'
        """, product_id)
        
        conn.commit()
    except Exception as e:
        print(f"[DB Error] Lỗi khi hủy các lô thừa của sản phẩm {product_id}: {e}")
    finally:
        conn.close()
