from typing import List
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent

class WeightedSentimentAggregator:
    def __init__(self, agents: List[BaseSentimentAgent], weights: List[float]):
        # Sửa lại logic: agents (3 LLMs) + 1 (VADER) = 4 weights
        if len(agents) + 1 != len(weights):
            raise ValueError(f"Lỗi: Có {len(agents)} LLM agents + 1 VADER, nhưng lại truyền vào {len(weights)} weights.")
        if round(sum(weights), 5) != 1.0:
            raise ValueError("Tổng trọng số (weights) phải bằng 1.0")
            
        self.agents = agents
        self.weights = weights

    def aggregate(self, text: str, vader_score_minus1_to_1: float) -> float:
        # Gọi các LLM Agents. Nếu bất kỳ agent nào raise QUOTA_EXCEEDED, 
        # nó sẽ văng thẳng ra khỏi hàm này và AnalysisService sẽ bắt được.
        llm_scores = []
        for agent in self.agents:
            score = agent.analyze_sentiment(text)
            llm_scores.append(score)
            
        # Chỉ khi chạy hết các Agent mà không lỗi thì mới tính toán
        all_scores = [vader_score_minus1_to_1] + llm_scores
        
        # Tính Weighted Average
        final_minus1_to_1 = sum(s * w for s, w in zip(all_scores, self.weights))
        
        # Chuẩn hóa về [0, 1]
        sentiment_ratio = (final_minus1_to_1 + 1.0) / 2.0
        return round(sentiment_ratio, 4)