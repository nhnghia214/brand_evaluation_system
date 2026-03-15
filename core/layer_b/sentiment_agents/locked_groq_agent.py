import json
import os
from groq import Groq
from dotenv import load_dotenv
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent, SYSTEM_PROMPT

load_dotenv()

class LockedGroqAgent(BaseSentimentAgent):
    def __init__(self):
        self.client = Groq()
        self.lock_file = "locked_model.txt" # File dùng để lưu cứng tên model
        self.model_name = self._get_or_lock_model()
        
        super().__init__(self.model_name)

    def _get_or_lock_model(self):
        # 1. NẾU ĐÃ CÓ FILE KHÓA -> ĐỌC VÀ DÙNG LUÔN
        if os.path.exists(self.lock_file):
            with open(self.lock_file, "r") as f:
                locked_name = f.read().strip()
                print(f"🔒 [Locked Agent] Đang dùng model đã khóa từ hôm trước: {locked_name}")
                return locked_name
        
        # 2. NẾU CHƯA CÓ FILE -> ĐI SĂN MODEL VÀ LƯU LẠI
        try:
            models = self.client.models.list().data
            active_models = [m.id for m in models]
            
            chosen_model = None
            
            # Ưu tiên 1: Đi tìm DeepSeek (Bao gồm cả bản distill của Llama)
            for m in active_models:
                if "deepseek" in m.lower():
                    chosen_model = m
                    break
            
            # Ưu tiên 2: Nếu không có DeepSeek, đi tìm Mixtral
            if not chosen_model:
                for m in active_models:
                    if "mixtral" in m.lower():
                        chosen_model = m
                        break
            
            # Ưu tiên 3: Nếu không có cả 2, lấy bản Llama 70B (Bản hạng nặng, khác biệt hoàn toàn với bản 8B)
            if not chosen_model:
                for m in active_models:
                    if "70b" in m.lower() and "llama" in m.lower():
                        chosen_model = m
                        break
            
            # Chốt sổ và lưu file
            if chosen_model:
                with open(self.lock_file, "w") as f:
                    f.write(chosen_model)
                print(f"🎯 [Locked Agent] Đã bắt được và KHÓA CHẶT model: {chosen_model}")
                return chosen_model
            else:
                return "llama-3.3-70b-versatile" # Lấy đại 1 bản mạnh nhất nếu list rỗng
                
        except Exception as e:
            print(f"⚠️ Lỗi kết nối Groq: {e}")
            return "llama-3.3-70b-versatile"

    def analyze_sentiment(self, text: str) -> float:
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
            error_msg = str(e)
            # NẾU BỊ CHẶN VÌ HẾT HẠN MỨC NGÀY -> BÁO ĐỘNG ĐỂ DỪNG TOÀN HỆ THỐNG
            if "429" in error_msg or "rate_limit_exceeded" in error_msg or "Limit 1000" in error_msg:
                raise Exception("RATE_LIMIT_REACHED")
                
            print(f"[{self.model_name}] Lỗi: {e}")
            return 0.0