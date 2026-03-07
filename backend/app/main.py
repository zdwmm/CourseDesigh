from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import SQLModel, Session, create_engine, select
from typing import Optional
import os
from datetime import date, datetime, timedelta
import pandas as pd

from .models import Stock, PriceHistory, NewsItem
from .fetch_price import fetch_and_store_prices
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
    """
    历史行情查询接口：
    /stocks/{code}/history?start=YYYY-MM-DD&end=YYYY-MM-DD
    """
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
            q = q.where(PriceHistory.date >= start_date)
        if end_date:
            q = q.where(PriceHistory.date <= end_date)
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
        return [r.dict() for r in results]

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
    return generate_prediction_from_sentiment(code.upper(), window, alpha, engine)
