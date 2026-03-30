import asyncio
from typing import List, Dict, Any
from core.layer_b.sentiment_agents.base_agent import BaseSentimentAgent

class SentimentPipelineOrchestrator:
    def __init__(self, cleaner_agent: BaseSentimentAgent, worker_agents: List[BaseSentimentAgent], referee_agent: BaseSentimentAgent):
        self.cleaner_agent = cleaner_agent
        self.worker_agents = worker_agents
        self.referee_agent = referee_agent

    async def run_pipeline(self, raw_reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # ==========================================
        # Giai đoạn 1: Lọc rác và đánh dấu seeding
        # ==========================================
        cleaned_batch = await self.cleaner_agent.process_batch(raw_reviews)
        
        if cleaned_batch and cleaned_batch[0].get("status") == "api_error":
            return cleaned_batch
            
        valid_reviews = [r for r in cleaned_batch if r.get("is_valid", False)]
        if not valid_reviews:
            return cleaned_batch # Toàn rác, trả về luôn để Service đánh dấu IsAnalyzed=1
            
        # ==========================================
        # Giai đoạn 2: Ba thợ bóc tách làm việc song song
        # ==========================================
        worker_tasks = [worker.process_batch(valid_reviews) for worker in self.worker_agents]
        worker_results_matrix = await asyncio.gather(*worker_tasks)
        
        # Kiểm tra xem có Worker nào bị hết API không
        for worker_result in worker_results_matrix:
            if worker_result and worker_result[0].get("status") == "api_error":
                cleaned_batch[0]["status"] = "api_error"
                return cleaned_batch
                
        merged_for_referee = self._merge_worker_results(valid_reviews, worker_results_matrix)
        
        # ==========================================
        # Giai đoạn 3: Trọng tài chốt danh sách
        # ==========================================
        referee_results = await self.referee_agent.process_batch(merged_for_referee)
        
        if referee_results and referee_results[0].get("status") == "api_error":
            cleaned_batch[0]["status"] = "api_error"
            return cleaned_batch
            
        # ==========================================
        # Giai đoạn 4: Tính điểm cho các câu Hợp lệ
        # ==========================================
        final_scored_valid_batch = self._calculate_final_scores(referee_results)
        
        # ==========================================
        # Giai đoạn 5: Ráp nối lại với các câu Rác
        # ==========================================
        # Đảm bảo trả về đủ 50 câu (cả rác lẫn xịn) để Service update Database
        valid_map = {item["id"]: item for item in final_scored_valid_batch}
        
        final_full_batch = []
        for item in cleaned_batch:
            if item["id"] in valid_map:
                final_full_batch.append(valid_map[item["id"]])
            else:
                # Đây là câu rác (is_valid = False), gán điểm trung tính 0.5
                item["final_score_0_to_1"] = 0.5
                final_full_batch.append(item)
                
        return final_full_batch

    def _merge_worker_results(self, original_reviews: List[Dict[str, Any]], worker_results_matrix: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        merged = []
        for i, review in enumerate(original_reviews):
            combined_item = review.copy()
            combined_item["worker_extractions"] = []
            for worker_idx, worker_result_list in enumerate(worker_results_matrix):
                extraction = worker_result_list[i].get("extracted_words", {"pos": [], "neg": []})
                combined_item["worker_extractions"].append({
                    "worker_name": self.worker_agents[worker_idx].agent_name,
                    "data": extraction
                })
            merged.append(combined_item)
        return merged

    def _calculate_final_scores(self, refereed_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for item in refereed_batch:
            referee_data = item.get("referee_final_words", {"pos": [], "neg": []})
            pos_count = len(referee_data.get("pos", []))
            neg_count = len(referee_data.get("neg", []))
            
            total_words = pos_count + neg_count
            if total_words == 0:
                raw_score = 0.0
            else:
                raw_score = (pos_count - neg_count) / total_words
                
            normalized_score = (raw_score + 1.0) / 2.0
            
            # Phạt điểm cực mạnh nếu phát hiện Seeding
            if item.get("is_potential_seeding", False):
                normalized_score = normalized_score * 0.8
                
            item["final_score_0_to_1"] = round(normalized_score, 4)
            
        return refereed_batch