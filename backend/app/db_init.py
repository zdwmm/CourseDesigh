"""
db_init.py
- Create database tables (SQLAlchemy Base metadata.create_all)
- Default DB URL: sqlite:///data/stocks.db
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "sqlite:///data/stocks.db")

def create_database(db_url: str = DEFAULT_DB_URL):
    engine = create_engine(db_url, echo=False, future=True)
    Base.metadata.create_all(bind=engine)
    return engine

if __name__ == "__main__":
    engine = create_database()
    print("Database initialized/created for URL:", DEFAULT_DB_URL)
