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
from .crawlers.manager import CrawlerManager
from .analyzers.sentiment_analyzer import NewsSegmentAnalyzer, DailySentimentAggregator
from .analyzers.technical_analyzer import TechnicalAnalysisReport, TechnicalIndicatorCalculator
from .predictors.ensemble_predictor import PredictionEnsembler
import pandas as pd

logger = logging.getLogger(__name__)

# 配置日志
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

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


# ==================== 情感分析接口（已过时，保留用于兼容性）====================

@app.get("/sentiment/{code}")
def get_sentiment(code: str):
    """
    获取情感分析结果
    
    注意：此端点已过时，建议使用 /analyze/sentiment 获取更详细的分析结果
    """
    with Session(engine) as session:
        results = session.exec(
            select(NewsItem).where(
                NewsItem.stock_code == code,
                NewsItem.sentiment_score is not None
            )
        ).all()

        return {
            "data": [r.dict() for r in results],
            "count": len(results)
        }


# ==================== 【新增】情感分析端点 ====================

@app.post("/analyze/sentiment")
async def analyze_news_sentiment(stock_code: str, limit: int = 20):
    """
    【新端点】分析最近新闻的情感
    
    【说明】：
    - 从 MySQL 获取该股票最近的新闻
    - 逐条进行情感分析
    - 返回聚合结果
    
    【示例】：
    curl -X POST "http://localhost:8000/analyze/sentiment?stock_code=INDEX&limit=20"
    """
    try:
        analyzer = NewsSegmentAnalyzer()
        
        # 获取最近新闻
        with Session(engine) as session:
            q = select(NewsItem).where(
                NewsItem.stock_code == stock_code.upper()
            ).order_by(NewsItem.published_at.desc())
            
            news_items = session.exec(q).all()[:limit]
        
        if not news_items:
            return {
                "code": 404,
                "message": f"未找到股票 {stock_code} 的新闻",
                "data": None
            }
        
        # 转换为列表格式
        news_list = [
            {
                'title': item.title,
                'content': item.content,
                'source': item.source,
                'published_at': item.published_at.isoformat() if hasattr(item.published_at, 'isoformat') else str(item.published_at),
            }
            for item in news_items
        ]
        
        # 批量分析
        analyzed_news = analyzer.analyze_batch_news(news_list)
        
        # 聚合日度情感
        daily_agg = DailySentimentAggregator.aggregate_daily_sentiment(analyzed_news)
        
        return {
            "code": 200,
            "message": "情感分析成功",
            "data": {
                "stock_code": stock_code,
                "news_count": len(analyzed_news),
                "daily_sentiment": daily_agg,
                "recent_news": [
                    {
                        'title': item['title'],
                        'sentiment': item['sentiment_analysis']['sentiment'],
                        'confidence': item['sentiment_analysis']['confidence'],
                    }
                    for item in analyzed_news[:5]  # 只返回最近5条
                ]
            }
        }
    
    except Exception as e:
        logger.error(f"情感分析错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyze/technical/{code}")
async def analyze_technical_indicators(code: str, days: int = 60):
    """
    【新端点】技术面分析
    
    【说明】：
    - 获取历史价格数据
    - 计算技术指标
    - 生成技术分析报告
    
    【示例】：
    curl "http://localhost:8000/analyze/technical/AAPL?days=60"
    """
    try:
        code = code.upper()
        
        # 获取价格数据
        with Session(engine) as session:
            q = select(PriceHistory).where(
                PriceHistory.stock_code == code
            ).order_by(PriceHistory.date.desc())
            
            results = session.exec(q).all()[:days]
        
        if not results:
            raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的价格数据")
        
        # 转换为 DataFrame
        df = pd.DataFrame([
            {
                'date': r.date,
                'open': r.open,
                'high': r.high,
                'low': r.low,
                'close': r.close,
                'volume': r.volume,
            }
            for r in reversed(results)  # 按时间升序
        ])
        
        # 生成技术分析报告
        report = TechnicalAnalysisReport.generate_report(df)
        
        return {
            "code": 200,
            "message": "技术分析成功",
            "data": {
                "stock_code": code,
                "analysis_date": datetime.now().isoformat(),
                **report  # 展开报告内容
            }
        }
    
    except Exception as e:
        logger.error(f"技术分析错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predict/signal/{code}")
async def generate_prediction_signal(
    code: str,
    use_sentiment: bool = True,
    use_technical: bool = True
):
    """
    【新端点】生成综合预测信号
    
    【说明】：
    - 融合情感分析和技术指标
    - 生成 BUY/HOLD/SELL 信号
    - 返回置信度和建议
    
    【参数】：
    - use_sentiment: 是否使用情感分析（默认 True）
    - use_technical: 是否使用技术指标（默认 True）
    
    【示例】：
    curl "http://localhost:8000/predict/signal/AAPL?use_sentiment=true&use_technical=true"
    
    【工作流程】：
    1. 获取最近新闻 → 情感分析
    2. 获取价格数据 → 技术分析
    3. 融合两个分数 → 生成信号
    """
    try:
        code = code.upper()
        
        # 初始化评分
        sentiment_score = 0.0
        technical_score = 50.0
        
        # 第一步：情感分析
        if use_sentiment:
            try:
                with Session(engine) as session:
                    q = select(NewsItem).where(
                        NewsItem.stock_code == code
                    ).order_by(NewsItem.published_at.desc())
                    
                    news_items = session.exec(q).all()[:50]  # 获取最近50条新闻
                
                if news_items:
                    analyzer = NewsSegmentAnalyzer()
                    news_list = [
                        {'content': item.content, 'source': item.source}
                        for item in news_items
                    ]
                    analyzed = analyzer.analyze_batch_news(news_list)
                    agg = DailySentimentAggregator.aggregate_daily_sentiment(analyzed)
                    sentiment_score = agg['weighted_sentiment'] / 50 - 1  # 标准化到 -1~1
            
            except Exception as e:
                logger.warning(f"情感分析失败，跳过: {e}")
        
        # 第二步：技术分析
        if use_technical:
            try:
                with Session(engine) as session:
                    q = select(PriceHistory).where(
                        PriceHistory.stock_code == code
                    ).order_by(PriceHistory.date.desc())
                    
                    results = session.exec(q).all()[:60]
                
                if results:
                    df = pd.DataFrame([
                        {
                            'open': r.open,
                            'high': r.high,
                            'low': r.low,
                            'close': r.close,
                            'volume': r.volume,
                        }
                        for r in reversed(results)
                    ])
                    report = TechnicalAnalysisReport.generate_report(df)
                    technical_score = report.get('technical_score', 50.0)
            
            except Exception as e:
                logger.warning(f"技术分析失败，跳过: {e}")
        
        # 第三步：融合生成信号
        signal = PredictionEnsembler.generate_prediction_signal(
            stock_code=code,
            sentiment_score=sentiment_score,
            technical_score=technical_score,
        )
        
        return {
            "code": 200,
            "message": "预测信号生成成功",
            "data": {
                "stock_code": code,
                **signal
            }
        }
    
    except Exception as e:
        logger.error(f"预测信号生成错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
