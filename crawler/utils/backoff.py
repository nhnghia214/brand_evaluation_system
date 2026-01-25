import time

def apply_backoff(backoff_level):
    if backoff_level == 0:
        return
    elif backoff_level == 1:
        time.sleep(2)
    elif backoff_level >= 2:
        time.sleep(5)
