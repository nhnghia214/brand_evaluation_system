# agent/intent_parser.py

import json
from dotenv import load_dotenv
from openai import OpenAI
from agent.prompts import INTENT_PROMPT

load_dotenv()
client = OpenAI()


class IntentParser:

    @staticmethod
    def parse(user_input: str) -> dict:
        prompt = INTENT_PROMPT.format(user_input=user_input)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Bạn là bộ phân tích intent."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        content = response.choices[0].message.content.strip()
        data = json.loads(content)

        # ==== VALIDATION NHẸ ====
        if data["intent"] == "COMPARE_BRANDS":
            if "brands" not in data or len(data["brands"]) < 2:
                raise ValueError("COMPARE_BRANDS requires at least 2 brands")

        return data
