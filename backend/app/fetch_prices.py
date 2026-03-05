"""
fetch_prices.py

Usage examples:
  python -m backend.app.fetch_prices --ticker AAPL --months 6
  python -m backend.app.fetch_prices --ticker 600519.SS --db sqlite:///data/stocks.db

Behavior:
- Uses yfinance to download daily OHLCV for the requested ticker for the last N months (default 6).
- Ensures a Stock record exists; populates basic metadata from yfinance info when available.
- Inserts or updates PriceHistory rows (based on stock_id + date uniqueness).
- Logs progress and exceptions.
"""
import argparse
import logging
from datetime import datetime, timedelta
import os
import pandas as pd
import yfinance as yf
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Stock, PriceHistory, Base
from .db_init import DEFAULT_DB_URL

# logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def get_engine(db_url):
    engine = create_engine(db_url, echo=False, future=True)
    return engine

def ensure_tables(engine):
    Base.metadata.create_all(bind=engine)

def fetch_history_df(ticker, months=6):
    period = f"{months}mo"
    logger.info("Requesting data for %s period=%s", ticker, period)
    # use yfinance to download daily
    df = yf.download(ticker, period=period, interval="1d", auto_adjust=False, progress=False)
    if df.empty:
        logger.warning("No data returned for %s", ticker)
        return pd.DataFrame()
    # Ensure index is DatetimeIndex; convert to date
    df = df.reset_index()
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    # Normalize column names
    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
        "Date": "date"
    })
    # Keep necessary columns
    cols = ['date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

def upsert_price_history(session, stock_id: int, row):
    # row is a pandas Series with date/open/high/low/close/adj_close/volume
    dt = row['date']
    # try existing
    existing = session.query(PriceHistory).filter_by(stock_id=stock_id, date=dt).one_or_none()
    if existing:
        # update fields
        existing.open = row['open']
        existing.high = row['high']
        existing.low = row['low']
        existing.close = row['close']
        existing.adjusted_close = row['adj_close']
        existing.volume = int(row['volume']) if pd.notna(row['volume']) else None
    else:
        ph = PriceHistory(
            stock_id=stock_id,
            date=dt,
            open=row['open'],
            high=row['high'],
            low=row['low'],
            close=row['close'],
            adjusted_close=row['adj_close'],
            volume=int(row['volume']) if pd.notna(row['volume']) else None
        )
        session.add(ph)

def fetch_and_store(ticker: str, db_url: str = DEFAULT_DB_URL, months: int = 6):
    engine = get_engine(db_url)
    ensure_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # get or create stock
        stock = session.query(Stock).filter_by(ticker=ticker).one_or_none()
        if not stock:
            # attempt to get metadata from yfinance
            logger.info("Creating new Stock record for %s", ticker)
            info = {}
            try:
                t = yf.Ticker(ticker)
                info = t.info or {}
            except Exception as e:
                logger.warning("Failed to fetch metadata for %s: %s", ticker, str(e))
            stock = Stock(
                ticker=ticker,
                name=info.get("shortName") or info.get("longName"),
                exchange=info.get("exchange"),
                currency=info.get("currency"),
                sector=info.get("sector"),
                industry=info.get("industry")
            )
            session.add(stock)
            session.commit()  # commit to get stock.id
            logger.info("Created Stock id=%s", stock.id)
        else:
            logger.info("Using existing Stock id=%s ticker=%s", stock.id, stock.ticker)

        # fetch OHLCV
        df = fetch_history_df(ticker, months=months)
        if df.empty:
            logger.warning("No historical price rows to insert for %s", ticker)
            return

        inserted = 0
        updated = 0
        for _, row in df.iterrows():
            dt = row['date']
            existing = session.query(PriceHistory).filter_by(stock_id=stock.id, date=dt).one_or_none()
            if existing:
                # check if values differ (simple check) and update
                existing_changed = False
                for attr, col in [("open", "open"), ("high", "high"), ("low", "low"), ("close", "close"), ("adjusted_close", "adj_close"), ("volume", "volume")]:
                    new_val = row[col]
                    if pd.isna(new_val):
                        new_val = None
                    if getattr(existing, attr) != new_val:
                        setattr(existing, attr, int(new_val) if attr == "volume" and new_val is not None else new_val)
                        existing_changed = True
                if existing_changed:
                    updated += 1
            else:
                ph = PriceHistory(
                    stock_id=stock.id,
                    date=dt,
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    adjusted_close=row['adj_close'],
                    volume=int(row['volume']) if pd.notna(row['volume']) else None
                )
                session.add(ph)
                inserted += 1

        session.commit()
        logger.info("Done for %s: inserted=%d updated=%d", ticker, inserted, updated)
    except Exception as e:
        logger.exception("Error during fetch_and_store for %s: %s", ticker, str(e))
        session.rollback()
        raise
    finally:
        session.close()

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", required=True, help="Ticker symbol (e.g. AAPL, 600519.SS)")
    p.add_argument("--db", dest="db_url", default=os.environ.get("DATABASE_URL", DEFAULT_DB_URL), help="SQLAlchemy DB URL")
    p.add_argument("--months", type=int, default=6, help="Months of history to fetch (default 6)")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    fetch_and_store(args.ticker, db_url=args.db_url, months=args.months)
