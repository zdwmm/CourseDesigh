from typing import Optional, List
from datetime import date, datetime
from sqlmodel import SQLModel, Field, Relationship

class Stock(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True, nullable=False, max_length=32)
    name: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # relationship to price rows (not strictly required for queries that use stock_code)
    prices: List["PriceHistory"] = Relationship(back_populates="stock")

class PriceHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # optional FK to Stock.id (table name is 'stock' by default); keep a denormalized stock_code used by queries
    stock_id: Optional[int] = Field(default=None, foreign_key="stock.id")
    stock_code: str = Field(index=True, nullable=False, max_length=32)
    date: date = Field(index=True)
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    adjusted_close: Optional[float] = None
    volume: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    stock: Optional[Stock] = Relationship(back_populates="prices")

class NewsItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stock_code: str = Field(index=True, nullable=False, max_length=32)
    title: str = Field(nullable=False)
    url: Optional[str] = None
    published_at: Optional[date] = Field(index=True)
    content: Optional[str] = None
    source: Optional[str] = None
    sentiment_score: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    stock = relationship("Stock", back_populates="price_history")

    def __repr__(self):
        return f"<PriceHistory(stock_id={self.stock_id} date={self.date} close={self.close})>"
