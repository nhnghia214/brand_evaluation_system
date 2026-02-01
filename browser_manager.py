# browser_manager.py
from playwright.sync_api import sync_playwright
import subprocess
import time
import requests


CHROME_CDP_URL = "http://127.0.0.1:9222"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def _is_cdp_running():
    try:
        requests.get(CHROME_CDP_URL, timeout=1)
        return True
    except:
        return False


def _launch_chrome_cdp():
    print("[Browser] Launching Chrome with CDP...")
    subprocess.Popen([
        CHROME_PATH,
        "--remote-debugging-port=9222",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-infobars"
    ])
    time.sleep(3)


def connect_cdp():
    if not _is_cdp_running():
        _launch_chrome_cdp()

    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(CHROME_CDP_URL)

    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()

    return p, browser, context, page
