from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sqlmodel import Session, select
from .models import NewsItem
from datetime import datetime

analyzer = SentimentIntensityAnalyzer()

def compute_sentiment_for_news(code: str, engine):
    with Session(engine) as session:
        q = select(NewsItem).where(NewsItem.stock_code == code.upper())
        items = session.exec(q).all()
        count = 0
        for it in items:
            text = (it.title or '') + '\n' + (it.content or '')
            if not text.strip():
                continue
            vs = analyzer.polarity_scores(text)
            # use compound score in [-1,1]
            it.sentiment_score = float(vs['compound'])
            session.add(it)
            count += 1
        session.commit()
    return count
