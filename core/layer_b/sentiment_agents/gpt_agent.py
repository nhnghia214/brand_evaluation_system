import json
from openai import OpenAI
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent, SYSTEM_PROMPT

class GPTSentimentAgent(BaseSentimentAgent):
    def __init__(self):
        super().__init__("ChatGPT")
        self.client = OpenAI() # Tự động lấy OPENAI_API_KEY từ file .env

    def analyze_sentiment(self, text: str) -> float:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Review text: '{text}'"}
                ],
                temperature=0.0 # Để 0.0 cho kết quả ổn định, không sáng tạo
            )
            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            return float(data.get("score", 0.0))
        except Exception as e:
            print(f"[GPTSentimentAgent] Error processing text: {e}")
            return 0.0