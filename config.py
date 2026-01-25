# =========================
# config.py (FINAL – ANCHOR MODE)
# =========================

# ===== JOB CONTROL =====
MAX_PRODUCT_PER_JOB = 50          # soft limit (scheduler vẫn timeout theo thời gian)
MAX_JOB_DURATION_MIN = 25         # mỗi job tối đa 25 phút
MAX_CONSECUTIVE_ERRORS = 3        # lỗi liên tiếp → PAUSE

# ===== DELAY =====
DELAY_BETWEEN_PRODUCT = (15, 30)  # giây – đủ nhanh cho Phase1A
DELAY_BETWEEN_JOB = (60, 120)     # nghỉ giữa các job
PAUSE_AFTER_ERROR = (3600, 7200)  # captcha / block → nghỉ 1–2 tiếng

# ===== SEARCH FILTER =====
MIN_SOLD_COUNT = 1                # crawl sản phẩm có bán
MAX_SEARCH_PAGE = 10   # số page search tối đa (10 page ≈ 600 sản phẩm)

# ===== ANCHOR MODE =====
ANCHOR_PRODUCT_LIMIT = 3          # mỗi job chỉ tập trung 3 sản phẩm lớn
ANCHOR_MIN_SOLD_COUNT = 3000      # coi là sản phẩm "nhiều tài nguyên"
ANCHOR_MAX_REVIEWS = 300          # crawl sâu (Phase1A)

# ===== SAFE MODE =====
SAFE_MAX_REVIEWS = 20             # sản phẩm thường (Phase1B)

# ===== PHASE 2 (sau này) =====
MAX_REVIEW_STALE_HOURS = 48       # bao lâu thì quay lại crawl review mới
