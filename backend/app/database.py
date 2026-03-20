# backend/app/database.py
import os
import redis
from sqlmodel import SQLModel, create_engine
from sqlalchemy.pool import QueuePool

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:root@localhost:3306/stock_analysis")

# MySQL 连接池配置
engine = create_engine(
    DATABASE_URL,
    echo=False,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # 连接前检查
)

# Redis 连接池配置
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    password=os.getenv("REDIS_PASSWORD", None),
    decode_responses=True,
    socket_connect_timeout=5,
    socket_keepalive=True,
)

def get_engine():
    return engine

def get_redis_client():
    return redis_client

def init_db():
    """初始化数据库表"""
    from . import models  # noqa: F401
    SQLModel.metadata.create_all(engine)

def test_redis_connection():
    """测试 Redis 连接"""
    try:
        redis_client.ping()
        return True
    except Exception as e:
        print(f"Redis 连接失败: {e}")
        return False
