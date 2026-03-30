from abc import ABC, abstractmethod
from typing import List, Dict, Any
import json
import asyncio

class BaseSentimentAgent(ABC):
    def __init__(self, agent_name: str, api_key: str = None, model_name: str = None):
        self.agent_name = agent_name
        self.api_key = api_key
        self.model_name = model_name

    @abstractmethod
    async def process_batch(self, batch_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Nhận vào 1 mảng các review (Batch).
        Ví dụ Input: [{"id": 1, "text": "Hàng đẹp", "is_valid": True}, ...]
        Trả về mảng review đã được xử lý (thêm các trường dữ liệu mới).
        """
        pass

    def _parse_json_safe(self, text: str) -> Dict:
        """Hàm dùng chung để ép kiểu chuỗi JSON từ LLM về Dictionary an toàn"""
        try:
            # Lọc bỏ các markdown code block nếu LLM lỡ sinh ra
            if text.startswith("```json"):
                text = text.replace("```json", "", 1)
            if text.endswith("```"):
                text = text[:-3]
            
            return json.loads(text.strip())
        except Exception as e:
            print(f"❌ [{self.agent_name}] Lỗi parse JSON: {e} - Nội dung gốc: {text[:50]}...")
            return {}