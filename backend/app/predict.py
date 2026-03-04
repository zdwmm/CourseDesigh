from sqlmodel import Session, select
from .models import PriceHistory, NewsItem
import pandas as pd
from datetime import date, timedelta

def generate_prediction_from_sentiment(code: str, window: int, alpha: float, engine):
    # fetch recent prices
    with Session(engine) as session:
        q = select(PriceHistory).where(PriceHistory.stock_code == code).order_by(PriceHistory.date)
        prices = session.exec(q).all()
        if not prices:
            return {"error": "no prices"}
        dfp = pd.DataFrame([{"date": p.date, "close": p.close} for p in prices])
        dfp['date'] = pd.to_datetime(dfp['date']).dt.date

        # sentiment
        q2 = select(NewsItem).where(NewsItem.stock_code == code)
        news = session.exec(q2).all()
        if not news:
            return {"error": "no news"}
        dfn = pd.DataFrame([{"date": n.published_at, "score": n.sentiment_score or 0} for n in news])
        dfn['date'] = pd.to_datetime(dfn['date']).dt.date
        sent_daily = dfn.groupby('date')['score'].mean().reset_index()

    # align last window days
    end = date.today()
    start = end - timedelta(days=window-1)
    idx = pd.date_range(start, end)
    idx_dates = [d.date() for d in idx]
    price_series = dfp[dfp['date'].isin(idx_dates)].set_index('date').reindex(idx_dates).fillna(method='ffill')
    # if missing, fill with last known close
    if price_series['close'].isna().all():
        last_known = dfp['close'].iloc[-1]
        price_series['close'] = last_known
    last_price = float(price_series['close'].iloc[-1])
    # create predicted series
    pred = []
    current_price = last_price
    for d in idx_dates:
        s = sent_daily[sent_daily['date'] == d]['score']
        sent = float(s.iloc[0]) if not s.empty else 0.0
        # predicted return = alpha * sentiment
        ret = alpha * sent
        current_price = current_price * (1 + ret)
        pred.append({"date": d.isoformat(), "predicted_close": round(current_price, 2)})
    # return aligned real and pred (real might be shorter)
    real = [{"date": d.isoformat(), "real_close": None} for d in idx_dates]
    for i, d in enumerate(idx_dates):
        row = price_series.loc[d]
        if not pd.isna(row['close']):
            real[i]['real_close'] = float(row['close'])
    return {"dates": idx_dates, "real": real, "predicted": pred}
