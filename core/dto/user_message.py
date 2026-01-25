from dataclasses import dataclass

@dataclass
class UserMessage:
    message_key: str
    severity: str   # INFO | SUCCESS | WARNING | ERROR
    message: str
