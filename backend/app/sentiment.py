from datetime import datetime

from snownlp import SnowNLP
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sqlmodel import Session, select

from .models import NewsItem

# 作为兜底的英语情感分析器
vader_analyzer = SentimentIntensityAnalyzer()


def _score_with_snownlp(text: str) -> float:
    """使用 SnowNLP 生成 [0,1] 情感分数；异常时抛出。"""
    s = SnowNLP(text)
    return float(s.sentiments)  # already 0~1


def _score_with_vader(text: str) -> float:
    """VADER 兜底，输出 0~1 区间以统一范围。"""
    vs = vader_analyzer.polarity_scores(text)
    return (vs["compound"] + 1) / 2  # map [-1,1] -> [0,1]


def compute_sentiment_for_news(code: str, engine):
    """为指定股票的所有新闻计算情感分数并写回 DB，返回被评分的数量。"""
    with Session(engine) as session:
        items = session.exec(
            select(NewsItem).where(NewsItem.stock_code == code.upper())
        ).all()

        count = 0
        for it in items:
            text = f"{it.title or ''}\n{it.content or ''}".strip()
            if not text:
                continue

            try:
                score = _score_with_snownlp(text)
            except Exception:
                score = _score_with_vader(text)

            it.sentiment_score = score
            session.add(it)
            count += 1

        session.commit()

    return count