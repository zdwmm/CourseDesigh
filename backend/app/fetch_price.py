"""
fetch_prices.py

Provides fetch_and_store_prices(code, period_days, engine) used by backend/app/main.py.

Behavior:
- Uses yfinance to download daily OHLCV for the requested ticker for the last `period_days` days.
- Ensures a Stock record exists (creates/updates basic metadata).
- Inserts or updates PriceHistory rows keyed by (stock_code, date).
- Returns number of rows inserted/updated (inserted + updated).
"""
from datetime import datetime, timedelta, date
import logging
import pandas as pd
import yfinance as yf
from sqlmodel import Session, select

from .models import Stock, PriceHistory

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def _download_history_df(code: str, period_days: int) -> pd.DataFrame:
    # yfinance supports start/end; compute start date
    end = datetime.utcnow().date()
    start = end - timedelta(days=period_days)
    # yfinance expects strings; use start and end
    df = yf.download(code, start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(), interval="1d", progress=False, auto_adjust=False)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.reset_index()
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    df = df.rename(columns={
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adjusted_close",
        "Volume": "volume"
    })
    # ensure expected columns exist
    for c in ['date','open','high','low','close','adjusted_close','volume']:
        if c not in df.columns:
            df[c] = None
    return df[['date','open','high','low','close','adjusted_close','volume']]

def fetch_and_store_prices(code: str, period_days: int, engine) -> int:
    """
    Fetch `period_days` of daily data for `code` and store into DB using provided SQLModel engine.
    Returns: total inserted_or_updated rows count.
    """
    code_uc = code.upper()
    df = _download_history_df(code_uc, period_days)
    if df.empty:
        logger.warning("No data fetched for %s", code_uc)
        return 0

    inserted = 0
    updated = 0

    with Session(engine) as session:
        # ensure stock exists
        stmt = select(Stock).where(Stock.ticker == code_uc)
        stock = session.exec(stmt).one_or_none()
        if not stock:
            # try get metadata from yfinance Ticker.info (best-effort)
            name = None
            try:
                info = yf.Ticker(code_uc).info or {}
                name = info.get("shortName") or info.get("longName")
            except Exception:
                name = None
            stock = Stock(ticker=code_uc, name=name)
            session.add(stock)
            session.commit()
            session.refresh(stock)

        for _, row in df.iterrows():
            dt = row['date']
            # try find existing PriceHistory by stock_code + date
            stmt2 = select(PriceHistory).where(PriceHistory.stock_code == code_uc, PriceHistory.date == dt)
            existing = session.exec(stmt2).one_or_none()
            if existing:
                # update fields if changed
                changed = False
                for attr, col in [('open','open'), ('high','high'), ('low','low'), ('close','close'), ('adjusted_close','adjusted_close'), ('volume','volume')]:
                    new_val = row[col]
                    # pandas may use numpy types; normalize to python types / None
                    if pd.isna(new_val):
                        new_val = None
                    if getattr(existing, attr) != new_val:
                        setattr(existing, attr, int(new_val) if attr == 'volume' and new_val is not None else new_val)
                        changed = True
                if changed:
                    session.add(existing)
                    updated += 1
            else:
                ph = PriceHistory(
                    stock_id=stock.id,
                    stock_code=code_uc,
                    date=dt,
                    open=row['open'] if not pd.isna(row['open']) else None,
                    high=row['high'] if not pd.isna(row['high']) else None,
                    low=row['low'] if not pd.isna(row['low']) else None,
                    close=row['close'] if not pd.isna(row['close']) else None,
                    adjusted_close=row['adjusted_close'] if not pd.isna(row['adjusted_close']) else None,
                    volume=int(row['volume']) if not pd.isna(row['volume']) else None
                )
                session.add(ph)
                inserted += 1
        session.commit()

    logger.info("fetch_and_store_prices %s: inserted=%d updated=%d", code_uc, inserted, updated)
    return inserted + updated
