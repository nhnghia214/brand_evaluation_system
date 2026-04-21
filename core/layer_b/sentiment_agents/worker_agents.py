import json
import asyncio
from typing import List, Dict, Any
from groq import AsyncGroq
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent

WORKER_SYSTEM_PROMPT = """
Bạn là chuyên gia bóc tách từ vựng tiếng Việt.
Nhiệm vụ: Đọc review và trích xuất CÁC TỪ KHÓA NGẮN GỌN (1-3 từ) thể hiện sự Khen (pos) và Chê (neg).
Quy tắc:
1. Chỉ trích xuất cụm từ trọng tâm, KHÔNG copy cả câu dài. (VD: "giao nhanh", "màu đẹp", "dùng chán").
2. Nếu không có khen/chê, để mảng rỗng [].

BẮT BUỘC TRẢ VỀ JSON EXACTLY NHƯ SAU (KHÔNG GIẢI THÍCH):
{
  "results": [
    {
      "id": 12345,
      "pos": ["đóng gói kỹ", "mịn"],
      "neg": ["giao chậm"]
    }
  ]
}
"""

class WorkerAgent(BaseSentimentAgent):
    def __init__(self, agent_name: str, api_key: str, model_name: str):
        super().__init__(agent_name, api_key, model_name)
        # Khởi tạo client bất đồng bộ của Groq
        self.client = AsyncGroq(api_key=self.api_key)

    async def process_batch(self, batch_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Chỉ lấy những câu hợp lệ (đã được Cleaner Agent duyệt) để tiết kiệm token
        valid_items = [item for item in batch_data if item.get("is_valid", False)]
        if not valid_items:
            return [{"id": item["id"], "extracted_words": {"pos": [], "neg": []}} for item in batch_data]
        
        print(f" 🛠️ [{self.agent_name}] Bắt đầu bóc tách từ vựng cho {len(valid_items)} câu...")
        
        input_list = [{"id": item["id"], "text": item["text"]} for item in valid_items]
        user_content = json.dumps(input_list, ensure_ascii=False)
        
        max_retries = 3
        base_wait_time = 2
        
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": WORKER_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.0,
                    max_tokens=4500
                )
                content = response.choices[0].message.content.strip()
                parsed_data = self._parse_json_safe(content)
                
                results_array = parsed_data.get("results", [])
                result_map = {item["id"]: item for item in results_array}
                
                output_batch = []
                for item in batch_data:
                    rid = item["id"]
                    if rid in result_map:
                        output_batch.append({
                            "id": rid,
                            "extracted_words": {
                                "pos": result_map[rid].get("pos", []),
                                "neg": result_map[rid].get("neg", [])
                            }
                        })
                    else:
                        output_batch.append({"id": rid, "extracted_words": {"pos": [], "neg": []}})
                        
                return output_batch
                
            except Exception as e:
                print(f" ⏳ [{self.agent_name}] Lỗi API: {e}. Thử lại {attempt+1}/{max_retries}...")
                await asyncio.sleep(base_wait_time)
                base_wait_time *= 2
                
        print(f" ❌ [{self.agent_name}] Thất bại hoàn toàn. Đánh dấu API Error.")
        if batch_data: batch_data[0]["status"] = "api_error"
        return batch_data