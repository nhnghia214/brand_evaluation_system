import platform
import os
from playwright.sync_api import sync_playwright

USER_DATA_DIR = "./chrome_profile"

def connect_cdp():
    p = sync_playwright().start()
    # Khi chạy trên Ubuntu đã cài GUI, ta vẫn để headless=False để thấy cửa sổ
    # Nếu muốn chạy ngầm hoàn toàn thì mới để True
    is_headless = False 

    chrome_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars"
    ]
    
    print(f"[Browser] Khởi động Chrome với Profile: {USER_DATA_DIR}")
    
    context = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=is_headless,
        args=chrome_args,
        viewport={"width": 1280, "height": 720},
        channel="chrome"
    )
    
    page = context.pages[0] if context.pages else context.new_page()
    return p, None, context, page