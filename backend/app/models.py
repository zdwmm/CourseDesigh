from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Float, BigInteger, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(32), unique=True, nullable=False, index=True)  # e.g. AAPL, 600519.SS
    name = Column(String(255), nullable=True)
    exchange = Column(String(64), nullable=True)
    currency = Column(String(16), nullable=True)
    sector = Column(String(128), nullable=True)
    industry = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    price_history = relationship("PriceHistory", back_populates="stock", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Stock(id={self.id} ticker={self.ticker} name={self.name})>"

class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uix_stock_date"),
        Index("ix_price_history_date", "date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)  # trading date (UTC)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    adjusted_close = Column(Float, nullable=True)
    volume = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    stock = relationship("Stock", back_populates="price_history")

    def __repr__(self):
        return f"<PriceHistory(stock_id={self.stock_id} date={self.date} close={self.close})>"
