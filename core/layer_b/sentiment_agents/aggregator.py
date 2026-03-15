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
        """
        Nhận vào text và điểm của Rule-based (đã chuẩn hóa về -1 đến 1).
        Trả về điểm tổng hợp trong khoảng [0, 1] để nạp vào score_calculator.py
        """
        # Gọi 3 LLM Agents phân tích
        llm_scores = []
        for agent in self.agents:
            score = agent.analyze_sentiment(text)
            llm_scores.append(score)
            
        # Ghép điểm VADER vào đầu danh sách (để tương ứng với trọng số w1)
        all_scores = [vader_score_minus1_to_1] + llm_scores
        
        # Tính Weighted Average
        final_minus1_to_1 = sum(score * weight for score, weight in zip(all_scores, self.weights))
        
        # CHUẨN HÓA VỀ [0, 1] ĐỂ ĐƯA VÀO CÔNG THỨC LÕI CỦA BẠN
        # Công thức: Ratio = (Score + 1) / 2
        sentiment_ratio = (final_minus1_to_1 + 1.0) / 2.0
        
        return round(sentiment_ratio, 4)