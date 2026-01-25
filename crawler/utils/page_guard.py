def page_unstable(browser):
    try:
        if not browser.title:
            return True

        current_url = browser.current_url
        if "login" in current_url:
            return True

        # Có thể bổ sung điều kiện khác sau
        return False
    except:
        return True
