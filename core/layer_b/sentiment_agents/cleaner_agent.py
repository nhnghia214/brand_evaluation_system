import os
import time
import json
import asyncio
from typing import List, Dict, Any
from groq import AsyncGroq
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent

CLEANER_SYSTEM_PROMPT = """
Bạn là AI làm sạch dữ liệu bình luận e-commerce.
Nhiệm vụ: Đánh giá mảng JSON đầu vào và trả về KẾT QUẢ JSON CHUẨN XÁC (Tuyệt đối không giải thích).

Tiêu chí:
1. "is_valid": Trả về false nếu là RÁC (thơ ca, xin xu, spam ký tự vô nghĩa). Trả về true nếu là nhận xét thật.
2. "is_potential_seeding": Trả về true nếu nghi ngờ BUFF ĐƠN (khen lố lăng, sáo rỗng vô căn cứ). Trả về false nếu bình thường.

BẮT BUỘC TRẢ VỀ FORMAT NÀY:
{
  "results": [
    {
      "id": 12345,
      "is_valid": true,
      "is_potential_seeding": false
    }
  ]
}
"""

class CleanerAgent(BaseSentimentAgent):
    def __init__(self, api_key: str = None):
        super().__init__("CleanerAgent_Groq_8B")
        
        # Lấy key từ tham số truyền vào hoặc biến môi trường
        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
             # Nếu cấu hình GROQ_API_KEYS dạng mảng, lấy key đầu tiên
             keys_str = os.getenv("GROQ_API_KEYS", "")
             keys = [k.strip() for k in keys_str.split(",") if k.strip()]
             if keys: key = keys[0]
             
        if not key:
            raise ValueError("❌ Không tìm thấy API Key cho CleanerAgent")
            
        self.client = AsyncGroq(api_key=key)
        self.model = "llama-3.1-8b-instant" # Dùng model nhẹ, siêu tốc để làm sạch

    async def process_batch(self, batch_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not batch_data:
            return []

        print(f" 🧹 [{self.agent_name}] Đang dọn dẹp lô {len(batch_data)} câu review...")

        # Chuẩn bị dữ liệu đầu vào cho Prompt (Chỉ lấy ID và Text)
        input_list = [{"id": item["id"], "text": item["text"]} for item in batch_data]
        user_content = json.dumps(input_list, ensure_ascii=False)

        max_retries = 3
        base_wait_time = 2

        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": CLEANER_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.0,
                    max_tokens=4500
                )
                
                content = response.choices[0].message.content.strip()
                parsed_data = self._parse_json_safe(content)
                
                results_array = parsed_data.get("results", [])
                
                # Tạo một dictionary map từ ID -> Kết quả để dễ tra cứu
                result_map = {item["id"]: item for item in results_array}
                
                # Gắn kết quả trả về vào mảng batch_data gốc
                for item in batch_data:
                    rid = item["id"]
                    if rid in result_map:
                        item["is_valid"] = result_map[rid].get("is_valid", True)
                        item["is_potential_seeding"] = result_map[rid].get("is_potential_seeding", False)
                    else:
                        # Nếu AI lỡ bỏ sót câu nào, mặc định cho qua
                        item["is_valid"] = True
                        item["is_potential_seeding"] = False
                        
                # Tính toán thống kê in ra màn hình
                valid_count = sum(1 for item in batch_data if item.get("is_valid"))
                seeding_count = sum(1 for item in batch_data if item.get("is_potential_seeding"))
                print(f" ✨ [{self.agent_name}] Xong! Hợp lệ: {valid_count}/{len(batch_data)}. Nghi ngờ Seeding: {seeding_count}.")
                
                return batch_data

            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "rate limit" in error_msg:
                    print(f" ⏳ [{self.agent_name}] Quá tải API. Ngủ {base_wait_time}s... (Thử lại {attempt+1}/{max_retries})")
                    await asyncio.sleep(base_wait_time)
                    base_wait_time *= 2
                else:
                    print(f" ⚠️ [{self.agent_name}] Lỗi: {e}. Thử lại sau {base_wait_time}s...")
                    await asyncio.sleep(base_wait_time)

        print(f" ❌ [{self.agent_name}] Thất bại hoàn toàn sau 3 lần thử. Đánh dấu API Error.")
        # Báo lỗi để dây chuyền bên ngoài (AnalysisService) biết mà khóa Quota
        batch_data[0]["status"] = "api_error" 
        return batch_data