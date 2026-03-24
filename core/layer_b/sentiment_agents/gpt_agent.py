import json
import time
from openai import OpenAI
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent, SYSTEM_PROMPT

class GPTSentimentAgent(BaseSentimentAgent):
    def __init__(self):
        super().__init__("ChatGPT")
        self.client = OpenAI() # Tự động lấy OPENAI_API_KEY từ file .env

    def analyze_sentiment(self, text: str) -> float:
        max_retries = 3
        base_wait_time = 3  # OpenAI phản hồi nhanh nên chỉ cần ngủ 3s ban đầu

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Review text: '{text}'"}
                    ],
                    temperature=0.0 # Để 0.0 cho kết quả ổn định, không sáng tạo
                )
                content = response.choices[0].message.content.strip()
                data = json.loads(content)
                return float(data.get("score", 0.0))
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Bắt lỗi quá tải (Rate Limit 429)
                if "429" in error_msg or "rate limit" in error_msg or "too many requests" in error_msg:
                    print(f" ⏳ [ChatGPT] Quá tải API. Ngủ {base_wait_time}s... (Thử lại {attempt+1}/{max_retries})")
                    time.sleep(base_wait_time)
                    base_wait_time *= 2  # Cấp số nhân: 3s -> 6s -> 12s
                    
                # Bắt lỗi cú pháp (Lỗi 400 - thường do câu bình luận có ký tự lạ mà AI từ chối đọc)
                elif "400" in error_msg or "invalid" in error_msg:
                    print(f" ❌ [ChatGPT] Lỗi 400 Bad Request/Ký tự lạ. Bỏ qua câu này để bảo vệ hệ thống.")
                    return 0.5
                    
                # Bắt các lỗi đứt mạng, server lỗi 500...
                else:
                    print(f" ⚠️ [ChatGPT] Lỗi mạng/Server: {e}. Chờ {base_wait_time}s...")
                    time.sleep(base_wait_time)
                    base_wait_time *= 2

        print(" ❌ [ChatGPT] Thất bại hoàn toàn sau 3 lần thử. Trả về điểm an toàn 0.5.")
        raise Exception("QUOTA_EXCEEDED")