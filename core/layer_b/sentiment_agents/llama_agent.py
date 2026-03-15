import json
import os
from groq import Groq
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent, SYSTEM_PROMPT

class LlamaSentimentAgent(BaseSentimentAgent):
    def __init__(self):
        super().__init__("Llama-3")
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def analyze_sentiment(self, text: str) -> float:
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant", 
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
            print(f"[LlamaSentimentAgent] Error processing text: {e}")
            return 0.0