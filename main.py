from browser_manager import connect_cdp
from scheduler import CrawlWorker

if __name__ == "__main__":
    p, browser, context, page = connect_cdp()
    worker = CrawlWorker(page)
    worker.run_forever()

    # KHÔNG đóng browser
