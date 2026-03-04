from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import date

class Stock(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str
    name: Optional[str] = None
    market: Optional[str] = None

class PriceHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stock_code: str = Field(index=True)
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    source: Optional[str] = None

class NewsItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stock_code: str = Field(index=True)
    title: str
    url: Optional[str] = None
    published_at: Optional[str] = None  # ISO date string
    content: Optional[str] = None
    source: Optional[str] = None
    sentiment_score: Optional[float] = None
