import json
import os
from groq import Groq
from dotenv import load_dotenv
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent, SYSTEM_PROMPT

load_dotenv()

class DynamicGroqAgent(BaseSentimentAgent):
    def __init__(self):
        self.client = Groq()
        self.model_name = "Chưa xác định"
        
        try:
            models = self.client.models.list().data
            # Danh sách tất cả các ID model đang sống trên Groq
            active_models = [m.id for m in models]
            
            # LỌC CỰC MẠNH: Bỏ qua TẤT CẢ những model có chữ "llama" hoặc "whisper" (âm thanh)
            non_llama_models = [m for m in active_models if "llama" not in m.lower() and "whisper" not in m.lower()]
            
            if non_llama_models:
                # Ưu tiên chọn Mixtral, Gemma, hoặc DeepSeek nếu có
                self.model_name = non_llama_models[0]
                for m in non_llama_models:
                    if "mixtral" in m.lower() or "gemma" in m.lower() or "deepseek" in m.lower():
                        self.model_name = m
                        break
            else:
                self.model_name = "Không tìm thấy model nào ngoài Llama trên Groq"
                
        except Exception as e:
            print(f"⚠️ [DynamicAgent] Lỗi: {e}")
            self.model_name = "Lỗi kết nối"

        super().__init__(f"{self.model_name}")
        print(f"🤖 [Đặc vụ tìm kiếm] Đã bắt được model KHÁC Llama: {self.model_name}")

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
            print(f"[{self.model_name}] Lỗi: {e}")
            return 0.0