import json
import os
import time
import requests
from dotenv import load_dotenv
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent, SYSTEM_PROMPT

load_dotenv()

class GeminiSentimentAgent(BaseSentimentAgent):
    def __init__(self):
        super().__init__("Gemini")
        self.api_key = os.getenv("GEMINI_API_KEY")
        # Danh sách bọc lót: Hỏng tên này ta tự động thử tên khác
        self.model_names = [
            "gemini-1.5-flash-latest", 
            "gemini-1.5-flash-001",
            "gemini-1.5-flash-002",
            "gemini-1.5-flash-8b",
            "gemini-1.5-flash"
        ]

    def analyze_sentiment(self, text: str) -> float:
        headers = {'Content-Type': 'application/json'}
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": f"Review text: '{text}'"}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.0}
        }

        # Quét qua từng tên model
        for model_name in self.model_names:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            
            for attempt in range(2): # Thử 2 lần cho mỗi tên
                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=15)
                    
                    # 1. Nếu thành công
                    if response.status_code == 200:
                        data = response.json()
                        content_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        result = json.loads(content_text)
                        return float(result.get("score", 0.0))
                        
                    # 2. Nếu quá tải API (Chờ 15s)
                    elif response.status_code == 429:
                        print(f"⚠️ [Gemini] Quá giới hạn API. Đang chờ 15s...")
                        time.sleep(15)
                        
                    # 3. Nếu sai tên model (404) -> THOÁT ra để thử tên model_name tiếp theo
                    elif response.status_code == 404:
                        break 
                        
                    # 4. Các lỗi khác
                    else:
                        print(f"[Gemini] Server báo lỗi {response.status_code} ({model_name}): {response.text[:100]}...")
                        time.sleep(5)
                        
                except Exception as e:
                    print(f"[Gemini] Lỗi kết nối mạng: {e}")
                    time.sleep(5)
                    
        # Nếu thử toàn bộ danh sách tên vẫn không được
        print("❌ [Gemini] Đã thử toàn bộ danh sách model nhưng đều thất bại.")
        return 0.0