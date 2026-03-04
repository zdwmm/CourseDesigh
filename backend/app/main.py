from fastapi import FastAPI, HTTPException
from sqlmodel import SQLModel, Field, Session, create_engine, select
from typing import Optional, List
import os
from datetime import date, datetime, timedelta
import pandas as pd

from .models import Stock, PriceHistory, NewsItem
from .fetch_prices import fetch_and_store_prices
from .fetch_news import import_news_from_csv_or_api
from .sentiment import compute_sentiment_for_news
from .predict import generate_prediction_from_sentiment

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")
engine = create_engine(DATABASE_URL, echo=False)

app = FastAPI(title="Stocks Sentiment PoC")

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

@app.post("/admin/fetch_prices/{code}")
def admin_fetch_prices(code: str, period_days: int = 365):
    # fetch and store using yfinance helper
    rows = fetch_and_store_prices(code, period_days, engine)
    return {"fetched_rows": rows}

@app.get("/stocks/{code}/history")
def get_history(code: str, start: Optional[str] = None, end: Optional[str] = None):
    with Session(engine) as session:
        q = select(PriceHistory).where(PriceHistory.stock_code == code.upper())
        if start:
            q = q.where(PriceHistory.date >= start)
        if end:
            q = q.where(PriceHistory.date <= end)
        q = q.order_by(PriceHistory.date)
        results = session.exec(q).all()
        if not results:
            raise HTTPException(status_code=404, detail="No history found")
        return [r.dict() for r in results]

@app.post("/admin/import_news/{code}")
def admin_import_news(code: str):
    count = import_news_from_csv_or_api(code, engine)
    return {"imported": count}

@app.get("/news/{code}")
def news_list(code: str, limit: int = 20):
    with Session(engine) as session:
        q = select(NewsItem).where(NewsItem.stock_code == code.upper()).order_by(NewsItem.published_at.desc())
        results = session.exec(q).all()[:limit]
        return [r.dict() for r in results]

@app.post("/admin/sentiment/{code}")
def admin_sentiment(code: str):
    count = compute_sentiment_for_news(code, engine)
    return {"scored": count}

@app.get("/news/{code}/sentiment")
def news_sentiment_series(code: str, days: int = 30):
    # return daily aggregated sentiment for last `days`
    with Session(engine) as session:
        end = date.today()
        start = end - timedelta(days=days)
        q = select(NewsItem).where(
            NewsItem.stock_code == code.upper(),
            NewsItem.published_at >= start.isoformat()
        )
        items = session.exec(q).all()
    # aggregate
    df = pd.DataFrame([{"date": it.published_at, "score": it.sentiment_score} for it in items if it.sentiment_score is not None])
    if df.empty:
        return []
    df['date'] = pd.to_datetime(df['date']).dt.date
    agg = df.groupby('date')['score'].mean().reset_index()
    return agg.to_dict(orient="records")

@app.get("/prediction/{code}")
def prediction(code: str, window: int = 30, alpha: float = 0.01):
    # simple generator: fetch recent prices & daily sentiment, produce predicted_close
    return generate_prediction_from_sentiment(code.upper(), window, alpha, engine)
