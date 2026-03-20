# backend/app/main.py
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from .database import init_db, get_engine, get_redis_client, test_redis_connection
from .models import PriceHistory, NewsItem, Stock
from .fetch_price import fetch_and_store_prices
from .sentiment import compute_sentiment_for_news
from .predict import generate_prediction_from_sentiment
from .crawlers.manager import CrawlerManager

# 配置日志
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 全局爬虫管理器
crawler_manager = None
crawler_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    startup：应用启动时
    - 初始化数据库
    - 测试 Redis 连接
    - 启动后台爬虫任务
    
    shutdown：应用关闭时
    - 取消爬虫任务
    """
    global crawler_manager, crawler_task

    # 应用启动
    logger.info("=" * 50)
    logger.info("应用启动中...")
    logger.info("=" * 50)

    try:
        # 初始化数据库
        init_db()
        logger.info("✓ 数据库初始化完成")

        # 测试 Redis 连接
        if test_redis_connection():
            logger.info("✓ Redis 连接成功")
        else:
            logger.warning("⚠ Redis 连接失败，部分功能可能不可用")

        # 初始化爬虫管理器
        crawler_manager = CrawlerManager()
        logger.info("✓ 爬虫管理器初始化完成")

        # 启动后台爬虫任务
        crawler_interval = int(os.getenv("CRAWLER_INTERVAL", 1))
        crawler_task = asyncio.create_task(
            crawler_manager.start_periodic_fetch(interval_minutes=crawler_interval)
        )
        logger.info(f"✓ 后台爬虫任务已启动（间隔 {crawler_interval} 分钟）")

    except Exception as e:
        logger.error(f"✗ 应用启动失败: {e}")
        raise

    logger.info("=" * 50)
    logger.info("应用启动完成，服务就绪")
    logger.info("=" * 50)

    yield

    # 应用关闭
    logger.info("=" * 50)
    logger.info("应用关闭中...")
    logger.info("=" * 50)

    if crawler_task:
        crawler_task.cancel()
        try:
            await crawler_task
        except asyncio.CancelledError:
            logger.info("✓ 爬虫任务已停止")

    logger.info("=" * 50)
    logger.info("应用已关闭")
    logger.info("=" * 50)


app = FastAPI(
    title="Stock Sentiment Prediction API",
    description="支持实时新闻爬取、情感分析和预测的股票分析平台",
    version="2.0.0",
    lifespan=lifespan
)

engine = get_engine()
redis_client = get_redis_client()

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 健康检查 ====================

@app.get("/health")
def health():
    """健康检查端点"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ==================== 新闻相关接口 ====================

@app.post("/admin/crawler/run")
async def admin_run_crawler():
    """
    【管理接口】手动触发一次爬虫运行
    
    用途：
    - 测试爬虫是否正常工作
    - 手动补充新闻数据
    - 开发和调试
    """
    if not crawler_manager:
        raise HTTPException(status_code=500, detail="爬虫管理器未初始化")

    try:
        result = await crawler_manager.fetch_and_process_news()
        return result
    except Exception as e:
        logger.error(f"手动爬虫执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/news/hot")
def get_hot_news(limit: int = 20):
    """
    获取热点新闻（从 Redis 缓存）
    
    参数：
    - limit: 返回新闻数量（默认 20）
    
    特点：
    - 极速返回（Redis 内存查询）
    - 用于前端实时展示
    - 支持 WebSocket 订阅实时更新
    """
    try:
        # 从 Redis 获取新闻
        cache_key = "stock:hot_news"
        news_data = redis_client.lrange(cache_key, 0, limit - 1)

        if not news_data:
            return {"data": [], "count": 0}

        import json
        news_list = [json.loads(item) for item in news_data]

        return {
            "data": news_list,
            "count": len(news_list),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"获取热点新闻失败: {e}")
        raise HTTPException(status_code=500, detail="获取新闻失败")


@app.get("/news/{code}")
def get_news_by_code(code: str, limit: int = 20):
    """
    按股票代码获取新闻
    
    参数：
    - code: 股票代码（例如 INDEX 表示聚合热点新闻）
    - limit: 返回新闻数量
    """
    code = code.upper().strip()

    with Session(engine) as session:
        q = select(NewsItem).where(
            NewsItem.stock_code == code
        ).order_by(NewsItem.published_at.desc())

        results = session.exec(q).all()[:limit]

        if not results:
            raise HTTPException(status_code=404, detail="未找到相关新闻")

        return {
            "data": [r.dict() for r in results],
            "count": len(results)
        }


# ==================== 价格相关接口 ====================

@app.post("/admin/fetch_prices/{code}")
def admin_fetch_prices(code: str, period_days: int = 365):
    """获取并存储股票历史价格"""
    try:
        rows = fetch_and_store_prices(code, period_days, engine)
        return {"fetched_rows": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stocks/{code}/history")
def get_history(code: str, start: Optional[str] = None, end: Optional[str] = None):
    """获取股票历史行情"""
    code = code.upper().strip()
    if not code:
        raise HTTPException(status_code=400, detail="Stock code cannot be empty")

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

    start_date = _parse_date_param(start, "start")
    end_date = _parse_date_param(end, "end")

    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start date cannot be after end date")

    with Session(engine) as session:
        q = select(PriceHistory).where(PriceHistory.stock_code == code)
        if start_date:
            q = q.where(PriceHistory.date >= start_date.isoformat())
        if end_date:
            q = q.where(PriceHistory.date <= end_date.isoformat())
        q = q.order_by(PriceHistory.date)

        results = session.exec(q).all()
        if not results:
            raise HTTPException(status_code=404, detail="No history found for this range")

        return {
            "data": [r.dict() for r in results],
            "count": len(results)
        }


# ==================== 情感分析接口 ====================

@app.post("/admin/sentiment/{code}")
def admin_sentiment(code: str):
    """计算新闻情感分数"""
    count = compute_sentiment_for_news(code, engine)
    return {"processed": count}


@app.get("/sentiment/{code}")
def get_sentiment(code: str):
    """获取情感分析结果"""
    with Session(engine) as session:
        results = session.exec(
            select(NewsItem).where(
                NewsItem.stock_code == code,
                NewsItem.sentiment_score != None
            )
        ).all()

        return {
            "data": [r.dict() for r in results],
            "count": len(results)
        }


# ==================== 预测接口 ====================

@app.post("/admin/predict/{code}")
def admin_predict(code: str):
    """生成预测信号"""
    result = generate_prediction_from_sentiment(code, engine)
    return result


@app.get("/prediction/{code}")
def get_prediction(code: str, window: int = 30, alpha: float = 0.01):
    """获取预测结果"""
    return {"code": code, "window": window, "alpha": alpha}
