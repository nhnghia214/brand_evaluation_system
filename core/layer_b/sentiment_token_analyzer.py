# core/layer_b/sentiment_token_analyzer.py

from typing import List, Tuple
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import nltk

# download tokenizer (chỉ chạy lần đầu)
nltk.download('punkt')
from nltk.tokenize import sent_tokenize, word_tokenize


class SentimentTokenAnalyzer:
    """
    Analyze review texts and count sentiment-weighted tokens.

    Output:
    - positive_token_count
    - negative_token_count
    """

    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()

    def analyze_reviews(self, reviews: List[str]) -> Tuple[float, float]:
        """
        :param reviews: list of review text
        :return: (positive_tokens, negative_tokens)
        """

        positive_tokens = 0.0
        negative_tokens = 0.0

        for review in reviews:
            if not review:
                continue

            sentences = sent_tokenize(review)

            for sentence in sentences:
                sentiment = self.analyzer.polarity_scores(sentence)
                compound = sentiment["compound"]  # [-1, 1]

                tokens = word_tokenize(sentence)
                token_count = len(tokens)

                if token_count == 0:
                    continue

                if compound > 0.05:
                    positive_tokens += token_count * compound
                elif compound < -0.05:
                    negative_tokens += token_count * abs(compound)
                # neutral → ignore

        return round(positive_tokens, 2), round(negative_tokens, 2)
