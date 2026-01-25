from enum import Enum
import datetime

class CrawlStatus(Enum):
    NOT_STARTED = 0
    RUNNING = 1
    PAUSED = 2
    COMPLETED = 3


class CrawlState:
    def __init__(self):
        self.current_page = 0
        self.status = CrawlStatus.NOT_STARTED
        self.backoff_level = 0
        self.last_error_time = None
