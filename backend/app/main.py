from fastapi import FastAPI, HTTPException
from typing import Optional
from datetime import datetime, date, timedelta
import pandas as pd
from sqlmodel import Session, select

from .database import init_db, get_engine
from .models import PriceHistory, NewsItem
from .fetch_price import fetch_and_store_prices
from .fetch_news import import_news_from_csv_or_api
from .sentiment import compute_sentiment_for_news
from .predict import generate_prediction_from_sentiment

app = FastAPI(title="Stock Sentiment Prediction API")
engine = get_engine()

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/admin/fetch_prices/{code}")
def admin_fetch_prices(code: str, period_days: int = 365):
    rows = fetch_and_store_prices(code, period_days, engine)
    return {"fetched_rows": rows}

def _parse_date_param(param: Optional[str], param_name: str) -> Optional[date]:
    if not param:
        return None
    try:
        return datetime.strptime(param, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format for '{param_name}', expected YYYY-MM-DD"
        )

@app.get("/stocks/{code}/history")
def get_history(code: str, start: Optional[str] = None, end: Optional[str] = None):
    code = code.upper().strip()
    if not code:
        raise HTTPException(status_code=400, detail="Stock code cannot be empty")

    start_date = _parse_date_param(start, "start")
    end_date = _parse_date_param(end, "end")

    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start date cannot be after end date")

    with Session(engine) as session:
        q = select(PriceHistory).where(PriceHistory.stock_code == code)
        if start_date:
            q = q.where(PriceHistory.date >= start_date.isoformat())
        if end_date:
            q = q.where(PriceHistory.date <= end_date.isoformat())
        q = q.order_by(PriceHistory.date)

        results = session.exec(q).all()
        if not results:
            raise HTTPException(status_code=404, detail="No history found for this range")
        return [r.dict() for r in results]

@app.post("/admin/import_news/{code}")
def admin_import_news(code: str):
    count = import_news_from_csv_or_api(code, engine)
    return {"imported": count}

@app.get("/news/{code}")
def news_list(code: str, limit: int = 20):
    with Session(engine) as session:
        q = select(NewsItem).where(
            NewsItem.stock_code == code.upper()
        ).order_by(NewsItem.published_at.desc())
        results = session.exec(q).all()[:limit]

    def _summary(text: str, n: int = 80):
        if not text:
            return ""
        return text if len(text) <= n else text[:n] + "..."

    return [
        {
            "id": r.id,
            "stock_code": r.stock_code,
            "published_at": r.published_at,
            "title": r.title,
            "source": r.source,
            "content": r.content,
            "summary": _summary(r.content, 80),
            "sentiment_score": r.sentiment_score,
        }
        for r in results
    ]

@app.post("/admin/sentiment/{code}")
def admin_sentiment(code: str):
    count = compute_sentiment_for_news(code, engine)
    return {"scored": count}

@app.get("/news/{code}/sentiment")
def news_sentiment_series(code: str, days: int = 30):
    with Session(engine) as session:
        end = date.today()
        start = end - timedelta(days=days)
        q = select(NewsItem).where(
            NewsItem.stock_code == code.upper(),
            NewsItem.published_at >= start.isoformat()
        )
        items = session.exec(q).all()

    df = pd.DataFrame(
        [{"date": it.published_at, "score": it.sentiment_score} for it in items if it.sentiment_score is not None]
    )
    if df.empty:
        return []
    df["date"] = pd.to_datetime(df["date"]).dt.date
    agg = df.groupby("date")["score"].mean().reset_index()
    return agg.to_dict(orient="records")

@app.get("/prediction/{code}")
def prediction(code: str, window: int = 30, alpha: float = 0.01):
    result = generate_prediction_from_sentiment(code.upper(), window, alpha, engine)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result