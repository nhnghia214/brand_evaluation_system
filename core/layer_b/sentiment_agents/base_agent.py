from abc import ABC, abstractmethod
import json

# Prompt chuẩn hóa bắt buộc trả về JSON
SYSTEM_PROMPT = """
You are an objective sentiment analysis engine for e-commerce reviews in Vietnamese. 
Your ONLY task is to evaluate the overall sentiment of the provided text and output a score strictly between -1.0 (extremely negative) and 1.0 (extremely positive). 0.0 means neutral.
You MUST return ONLY a valid JSON object with a single key "score". Do not include Markdown, explanations, or any other text.
"""

class BaseSentimentAgent(ABC):
    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    @abstractmethod
    def analyze_sentiment(self, text: str) -> float:
        """
        Nhận vào 1 đoạn review text, trả về điểm số từ -1.0 đến 1.0.
        Bắt buộc phải có try-except bên trong để nếu API lỗi thì trả về 0.0 (Neutral).
        """
        pass