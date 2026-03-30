import json
import asyncio
from typing import List, Dict, Any
from openai import AsyncOpenAI
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent

REFEREE_SYSTEM_PROMPT = """
Bạn là Trọng tài AI cấp cao (Referee) đánh giá thương hiệu. 
Bạn sẽ nhận được 1 mảng JSON. Mỗi phần tử gồm: câu review gốc (text) và danh sách từ vựng Tích cực/Tiêu cực do 3 AI cấp dưới trích xuất (worker_1, worker_2, worker_3).

Nhiệm vụ:
1. Đọc review gốc để hiểu đúng ngữ cảnh.
2. Đối chiếu với kết quả của 3 AI cấp dưới.
3. Loại bỏ các từ ngữ bị nhặt sai ngữ cảnh, trùng lặp hoặc hiểu lầm (ví dụ: "chậm" trong "không chậm" là tích cực chứ không phải tiêu cực).
4. Chốt lại 1 danh sách từ vựng Tích cực (pos) và Tiêu cực (neg) cuối cùng và chính xác nhất.

BẮT BUỘC TRẢ VỀ JSON EXACTLY NHƯ SAU:
{
  "results": [
    {
      "id": 12345,
      "pos": ["tốt", "rất đẹp"],
      "neg": ["giao hàng hơi chậm"]
    }
  ]
}
Tuyệt đối không giải thích thêm.
"""

class RefereeAgent(BaseSentimentAgent):
    def __init__(self, api_key: str):
        super().__init__("RefereeAgent_GPT4o_Mini", api_key=api_key)
        # Dùng AsyncOpenAI để chạy đồng bộ với Dây chuyền
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def process_batch(self, batch_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        valid_items = [item for item in batch_data if item.get("is_valid", False)]
        if not valid_items:
            return batch_data

        print(f" ⚖️ [{self.agent_name}] Đang phân xử và chốt sổ lô {len(valid_items)} câu...")

        input_list = []
        for item in valid_items:
            input_list.append({
                "id": item["id"],
                "text": item["text"],
                "worker_1": item["worker_extractions"][0]["data"],
                "worker_2": item["worker_extractions"][1]["data"],
                "worker_3": item["worker_extractions"][2]["data"]
            })
        
        user_content = json.dumps(input_list, ensure_ascii=False)
        
        max_retries = 3
        base_wait_time = 2
        
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": REFEREE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.0
                )
                content = response.choices[0].message.content.strip()
                parsed_data = self._parse_json_safe(content)
                
                results_array = parsed_data.get("results", [])
                result_map = {item["id"]: item for item in results_array}
                
                for item in batch_data:
                    rid = item["id"]
                    if rid in result_map:
                        item["referee_final_words"] = {
                            "pos": result_map[rid].get("pos", []),
                            "neg": result_map[rid].get("neg", [])
                        }
                    else:
                        item["referee_final_words"] = {"pos": [], "neg": []}
                        
                return batch_data
                
            except Exception as e:
                print(f" ⏳ [{self.agent_name}] Lỗi API: {e}. Thử lại {attempt+1}/{max_retries}...")
                await asyncio.sleep(base_wait_time)
                base_wait_time *= 2
                
        print(f" ❌ [{self.agent_name}] Thất bại hoàn toàn. Đánh dấu API Error.")
        if batch_data: batch_data[0]["status"] = "api_error"
        return batch_data