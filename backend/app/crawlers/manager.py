# backend/app/crawlers/manager.py
"""
爬虫管理器 - 统一管理所有爬虫的生命周期
"""
import asyncio
import logging
import json
import hashlib
from datetime import datetime
from typing import List, Dict
from sqlmodel import Session, select
from ..database import redis_client, get_engine
from ..models import NewsItem
from .kr_36 import Kr36Spider
from .cailianshe import ClsSpider
from .tonghuashun import ThsSpider
from .sina_finance import SinaSpider

logger = logging.getLogger(__name__)


class CrawlerManager:
    """
    爬虫管理器
    
    职责：
    1. 并发运行多个爬虫
    2. 数据去重和存储
    3. Redis 实时缓存
    4. 发送新闻事件通知
    """

    def __init__(self):
        self.spiders = [
            Kr36Spider(),
            ClsSpider(),
            ThsSpider(),
            SinaSpider(),
        ]
        self.engine = get_engine()
        self.redis = redis_client
        
        # Redis 键前缀
        self.hot_news_key = "stock:hot_news"
        self.news_hash_key = "stock:news_hashes"
        self.news_event_channel = "stock:news:add"

    async def run_all_crawlers(self) -> List[Dict]:
        """
        并发运行所有爬虫
        
        【重要】：
        - 使用 asyncio.gather 并发执行所有爬虫
        - 单个爬虫超时设置为 30 秒
        - 异常被捕获，不影响其他爬虫
        
        返回：所有爬虫获取的去重后新闻列表
        """
        try:
            logger.info("开始并发运行爬虫...")
            
            # 并发运行所有爬虫，设置 30 秒超时
            tasks = [
                spider.run_with_timeout(timeout_seconds=30) 
                for spider in self.spiders
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_news = []
            for spider, result in zip(self.spiders, results):
                if isinstance(result, Exception):
                    logger.error(f"爬虫 {spider.name} 异常: {result}")
                    continue
                
                if isinstance(result, list):
                    logger.info(f"爬虫 {spider.name} 获取 {len(result)} 条新闻")
                    all_news.extend(result)

            logger.info(f"总共获取 {len(all_news)} 条新闻（去重前）")
            
            # 去重
            unique_news = self._deduplicate_news(all_news)
            logger.info(f"去重后 {len(unique_news)} 条新闻")
            
            return unique_news

        except Exception as e:
            logger.error(f"运行爬虫异常: {e}")
            return []

    def _deduplicate_news(self, news_list: List[Dict]) -> List[Dict]:
        """
        【去重策略】
        
        使用 MD5 哈希去重：
        - 计算 (title + content) 的 MD5
        - 检查是否已存在（过 Redis 的 hashes 集合）
        - 若重复则跳过
        
        【优势】：
        - 快速（O(1) 查询）
        - 准确（MD5 碰撞几率极低）
        - 可持久化
        """
        if not news_list:
            return []

        # 从 Redis 获取已存储新闻的哈希值
        existing_hashes = self.redis.smembers(self.news_hash_key)

        unique_news = []
        new_hashes = []

        for news in news_list:
            # 构建唯一标识：(标题 + 内容)
            hash_str = f"{news.get('title', '')}|{news.get('content', '')}"
            news_hash = hashlib.md5(hash_str.encode('utf-8')).hexdigest()

            # 检查是否已存在
            if news_hash not in existing_hashes:
                unique_news.append(news)
                new_hashes.append(news_hash)

        # 更新 Redis 中的哈希集合
        if new_hashes:
            self.redis.sadd(self.news_hash_key, *new_hashes)

        return unique_news

    async def store_news_to_db(self, news_list: List[Dict]) -> int:
        """
        存储新闻到 MySQL 数据库
        
        【关键】：
        - 使用唯一约束 (stock_code, title, published_at) 避免重复
        - 插入时忽略已存在的记录
        - 返回插入数量
        
        【注意】：
        - 这里的 stock_code 固定为 "INDEX" 或某个聚合值
        - 实际项目可能需要提取股票代码（如从新闻内容）
        """
        inserted = 0

        with Session(self.engine) as session:
            for news in news_list:
                try:
                    # 检查是否已存在
                    existing = session.exec(
                        select(NewsItem).where(
                            NewsItem.title == news.get('title', ''),
                            NewsItem.source == news.get('source', ''),
                        )
                    ).first()

                    if existing:
                        continue

                    # 解析时间
                    try:
                        published_at = datetime.strptime(
                            news['datetime'], 
                            "%Y-%m-%d %H:%M:%S"
                        )
                    except (ValueError, KeyError):
                        published_at = datetime.now()

                    # 创建新闻记录
                    news_item = NewsItem(
                        stock_code="INDEX",  # 热点新闻的聚合标记
                        title=news.get('title', '')[:500],
                        url=news.get('url', ''),
                        published_at=published_at,
                        content=news.get('content', ''),
                        source=news.get('source', 'unknown'),
                    )

                    session.add(news_item)
                    inserted += 1

                except Exception as e:
                    logger.error(f"存储新闻失败: {e}")
                    continue

            session.commit()

        return inserted

    async def cache_news_to_redis(self, news_list: List[Dict]) -> None:
        """
        缓存新闻到 Redis（用于实时展示）
        
        【架构】：
        - 使用 Redis 列表存储最新 N 条新闻
        - 列表名：stock:hot_news
        - 自动过期：防止无限增长
        
        【前端订阅】：
        - 可通过 WebSocket 订阅 stock:news:add 通道
        - 实时接收新闻更新
        """
        if not news_list:
            return

        try:
            # 序列化新闻列表
            news_json = [
                json.dumps(news, ensure_ascii=False) 
                for news in news_list
            ]

            # 加入 Redis 列表（最新的在最前面）
            if news_json:
                self.redis.lpush(self.hot_news_key, *news_json)
                
                # 保留最新的 1000 条
                self.redis.ltrim(self.hot_news_key, 0, 999)
                
                # 设置过期时间（24 小时）
                self.redis.expire(self.hot_news_key, 86400)

                # 发布新闻添加事件
                for news in news_list[:10]:  # 只发布前 10 条
                    event_data = {
                        'title': news.get('title', ''),
                        'source': news.get('source', ''),
                        'timestamp': datetime.now().timestamp()
                    }
                    self.redis.publish(
                        self.news_event_channel, 
                        json.dumps(event_data, ensure_ascii=False)
                    )

                logger.info(f"已缓存 {len(news_list)} 条新闻到 Redis")

        except Exception as e:
            logger.error(f"缓存新闻到 Redis 失败: {e}")

    async def fetch_and_process_news(self) -> Dict:
        """
        【主流程】运行完整的新闻获取和处理流程
        
        流程：
        1. 并发运行所有爬虫
        2. 去重处理
        3. 存储到 MySQL
        4. 缓存到 Redis
        5. 返回统计信息
        """
        try:
            logger.info("=" * 50)
            logger.info("开始新一轮新闻抓取循环")
            logger.info("=" * 50)

            # 第一步：并发获取新闻
            news_list = await self.run_all_crawlers()

            if not news_list:
                logger.warning("本轮未获取任何新闻")
                return {
                    "fetched": 0,
                    "stored": 0,
                    "cached": len(news_list),
                    "status": "no_news"
                }

            # 第二步：存储到数据库
            stored_count = await self.store_news_to_db(news_list)

            # 第三步：缓存到 Redis（用于实时展示）
            await self.cache_news_to_redis(news_list)

            result = {
                "fetched": len(news_list),
                "stored": stored_count,
                "cached": len(news_list),
                "status": "success"
            }

            logger.info(f"本轮完成: {result}")
            return result

        except Exception as e:
            logger.error(f"新闻处理异常: {e}")
            return {
                "fetched": 0,
                "stored": 0,
                "cached": 0,
                "status": "error",
                "error": str(e)
            }

    async def start_periodic_fetch(self, interval_minutes: int = 1):
        """
        【后台任务】定期获取新闻
        
        参数：
        - interval_minutes: 爬取间隔（分钟）
        
        【推荐配置】：
        - 开发环境：1-2 分钟（测试爬虫稳定性）
        - 生产环境：5-10 分钟（减轻网站服务器压力）
        
        【生命周期】：
        - 应在应用启动时调用
        - 通常包装在一个后台任务中（如 APScheduler）
        """
        logger.info(f"启动定期新闻爬取任务，间隔 {interval_minutes} 分钟")

        while True:
            try:
                await self.fetch_and_process_news()
                
                # 等待指定时间后再执行下一轮
                await asyncio.sleep(interval_minutes * 60)

            except Exception as e:
                logger.error(f"定期爬取任务异常: {e}")
                # 发生异常后，等待 1 分钟再重试
                await asyncio.sleep(60)
