import json
import os
import time
from groq import Groq
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent, SYSTEM_PROMPT

class LlamaSentimentAgent(BaseSentimentAgent):
    def __init__(self):
        super().__init__("Llama-3")
        
        # Lấy danh sách key từ file .env
        keys_str = os.getenv("GROQ_API_KEYS", "")
        self.api_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        
        if not self.api_keys:
            single_key = os.getenv("GROQ_API_KEY")
            if single_key:
                self.api_keys = [single_key]
            else:
                raise ValueError("❌ Không tìm thấy GROQ_API_KEYS trong file .env")

        self.current_key_index = 0
        self._init_client()

    def _init_client(self):
        """Khởi tạo client với key hiện tại"""
        self.client = Groq(api_key=self.api_keys[self.current_key_index])

    def _rotate_key(self):
        """Chuyển sang key tiếp theo (Không quay vòng lại 0)"""
        self.current_key_index += 1
        if self.current_key_index < len(self.api_keys):
            self._init_client()
            print(f"🔄 [Llama-3] Đã chuyển sang API Key số {self.current_key_index + 1}/{len(self.api_keys)}")

    def analyze_sentiment(self, text: str) -> float:
        # Vòng lặp vô tận nhưng sẽ bị chặn đứng bởi logic bên trong
        while True:
            try:
                response = self.client.chat.completions.create(
                    model="llama-3.1-8b-instant", 
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Review text: '{text}'"}
                    ],
                    temperature=0.0
                )
                content = response.choices[0].message.content.strip()
                data = json.loads(content)
                return float(data.get("score", 0.0))
                
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "rate limit" in error_msg or "quota" in error_msg:
                    # Nếu chưa phải là Key cuối cùng thì mới đổi
                    if self.current_key_index < len(self.api_keys) - 1:
                        print(f" ⏳ [Llama-3] Key {self.current_key_index + 1} nghẽn. Đổi sang Key tiếp theo...")
                        self._rotate_key()
                        time.sleep(2) # Nghỉ ngắn để tránh dồn dập
                        continue # Thử lại với Key mới
                    else:
                        # Đã chạm đến Key cuối cùng mà vẫn lỗi -> DỪNG NGAY
                        print(" ❌ [Llama-3] ĐÃ CHẠM ĐẾN KEY CUỐI CÙNG VÀ HẾT REQUEST. DỪNG ĐỂ NGỦ ĐÔNG!")
                        raise Exception("QUOTA_EXCEEDED")
                else:
                    # Các lỗi khác (mạng, timeout) cũng cho dừng để an toàn dữ liệu
                    raise Exception("QUOTA_EXCEEDED")

        raise Exception("QUOTA_EXCEEDED")