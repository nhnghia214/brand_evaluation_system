import time, random

def human_sleep(min_s=8, max_s=15):
    time.sleep(random.uniform(min_s, max_s))

def short_sleep():
    time.sleep(random.uniform(1.5, 3.0))
