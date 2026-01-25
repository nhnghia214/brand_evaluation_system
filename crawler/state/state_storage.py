import json
import os
import datetime
from state.crawl_state import CrawlState, CrawlStatus

STATE_FILE = "crawl_state.json"

def state_to_dict(state):
    return {
        "current_page": state.current_page,
        "status": state.status.name,
        "backoff_level": state.backoff_level,
        "last_error_time": state.last_error_time.isoformat() if state.last_error_time else None
    }

def dict_to_state(data):
    state = CrawlState()
    state.current_page = data["current_page"]
    state.status = CrawlStatus[data["status"]]
    state.backoff_level = data["backoff_level"]
    state.last_error_time = (
        datetime.datetime.fromisoformat(data["last_error_time"])
        if data["last_error_time"] else None
    )
    return state

def load_states(products):
    if not os.path.exists(STATE_FILE):
        return {pid: CrawlState() for pid in products}

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    states = {}
    for pid in products:
        pid_str = str(pid)
        states[pid] = dict_to_state(raw[pid_str]) if pid_str in raw else CrawlState()

    return states

def save_states(states):
    data = {str(pid): state_to_dict(state) for pid, state in states.items()}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
