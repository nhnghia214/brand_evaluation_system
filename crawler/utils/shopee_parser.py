import re

def extract_product_id(url: str):
    """
    Ví dụ URL Shopee:
    https://shopee.vn/...-i.1188557488.24015454328

    - shopid  = 1188557488
    - itemid  = 24015454328  ← dùng làm ProductId
    """

    if not url:
        return None

    # Pattern chuẩn của Shopee
    m = re.search(r"-i\.(\d+)\.(\d+)", url)
    if not m:
        return None

    item_id = m.group(2)
    try:
        return int(item_id)
    except ValueError:
        return None
