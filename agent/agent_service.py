# agent/agent_service.py

import requests
from agent.intent_parser import IntentParser

API_URL = "http://127.0.0.1:8000/evaluate"

class BrandEvaluationAgent:

    @staticmethod
    def handle(user_input: str) -> str:
        intent_data = IntentParser.parse(user_input)

        if intent_data["intent"] != "EVALUATE_BRAND":
            return "Xin lỗi, tôi chưa hiểu yêu cầu của bạn."

        payload = {
            "brand": intent_data["brand"],
            "category": intent_data.get("category")
        }

        response = requests.post(API_URL, json=payload)
        result = response.json()

        return result["message"]
