import time
from utils.sleeper import short_sleep

class ShopeeFetcher:
    def __init__(self, browser):
        self.browser = browser

    def crawl_reviews_on_current_page(self, max_reviews=20):
        time.sleep(5)

        # 1️⃣ Click tab "Đánh giá"
        try:
            review_tab = self.browser.find_element(
                "XPATH",
                "//div[contains(text(),'Đánh giá')]"
            )
            review_tab.click()
            short_sleep()
        except:
            raise RuntimeError("REVIEW_TAB_NOT_FOUND")

        # 2️⃣ Lấy review items
        review_items = self.browser.find_elements(
            "CSS_SELECTOR",
            "div.shopee-product-rating"
        )

        if not review_items:
            raise RuntimeError("NO_REVIEW_DOM")

        reviews = []

        for r in review_items[:max_reviews]:
            try:
                rating = r.find_element(
                    "CSS_SELECTOR",
                    "div.shopee-product-rating__rating svg"
                )
                comment = r.find_element(
                    "CSS_SELECTOR",
                    "div.shopee-product-rating__content"
                ).text

                reviews.append({
                    "rating": "star",  # có thể parse sau
                    "comment": comment
                })
            except:
                continue

        return reviews
