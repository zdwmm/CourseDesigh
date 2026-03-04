import yfinance as yf
import pandas as pd
from sqlmodel import Session
from datetime import date, timedelta
from models import PriceHistory, Stock

def fetch_and_store_prices(code: str, period_days: int, engine):
    ticker = yf.Ticker(code)
    period = f"{period_days}d"
    hist = ticker.history(period=period)
    if hist.empty:
        return 0
    rows = 0
    with Session(engine) as session:
        for idx, row in hist.iterrows():
            ph = PriceHistory(
                stock_code=code.upper(),
                date=idx.date(),
                open=float(row['Open']),
                high=float(row['High']),
                low=float(row['Low']),
                close=float(row['Close']),
                volume=float(row.get('Volume', 0)),
                source='yfinance'
            )
            session.add(ph)
            rows += 1
        session.commit()
    return rows
