import json
import os
import time
from groq import Groq
from dotenv import load_dotenv
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent, SYSTEM_PROMPT

load_dotenv()

class LockedGroqAgent(BaseSentimentAgent):
    def __init__(self):
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
        
        self.lock_file = "locked_model.txt" 
        self.model_name = self._get_or_lock_model()
        
        super().__init__(self.model_name)

    def _init_client(self):
        self.client = Groq(api_key=self.api_keys[self.current_key_index])

    def _rotate_key(self):
        self.current_key_index += 1
        if self.current_key_index < len(self.api_keys):
            self._init_client()
            print(f"🔄 [Locked Agent] Đã chuyển sang API Key số {self.current_key_index + 1}/{len(self.api_keys)}")

    def _get_or_lock_model(self):
        if os.path.exists(self.lock_file):
            with open(self.lock_file, "r") as f:
                locked_name = f.read().strip()
                print(f"🔒 [Locked Agent] Đang dùng model đã khóa từ hôm trước: {locked_name}")
                return locked_name
        
        try:
            models = self.client.models.list().data
            active_models = [m.id for m in models]
            chosen_model = None
            
            for m in active_models:
                if "deepseek" in m.lower():
                    chosen_model = m
                    break
            if not chosen_model:
                for m in active_models:
                    if "mixtral" in m.lower():
                        chosen_model = m
                        break
            if not chosen_model:
                for m in active_models:
                    if "70b" in m.lower() and "llama" in m.lower():
                        chosen_model = m
                        break
            
            if chosen_model:
                with open(self.lock_file, "w") as f:
                    f.write(chosen_model)
                print(f"🎯 [Locked Agent] Đã bắt được và KHÓA CHẶT model: {chosen_model}")
                return chosen_model
            else:
                return "llama-3.3-70b-versatile"
                
        except Exception as e:
            print(f"⚠️ Lỗi kết nối Groq: {e}")
            return "llama-3.3-70b-versatile"

    def analyze_sentiment(self, text: str) -> float:
        while True:
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
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
                if "429" in error_msg or "rate limit" in error_msg or "limit 1000" in error_msg:
                    if self.current_key_index < len(self.api_keys) - 1:
                        print(f" ⏳ [Locked Agent] Key {self.current_key_index + 1} nghẽn. Đổi sang Key tiếp theo...")
                        self._rotate_key()
                        time.sleep(2)
                        continue
                    else:
                        print(" ❌ [Locked Agent] ĐÃ CHẠM ĐẾN KEY CUỐI CÙNG VÀ HẾT REQUEST. DỪNG ĐỂ NGỦ ĐÔNG!")
                        raise Exception("QUOTA_EXCEEDED")
                else:
                    raise Exception("QUOTA_EXCEEDED")

        raise Exception("QUOTA_EXCEEDED")