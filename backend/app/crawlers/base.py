# backend/app/crawlers/base.py
"""
爬虫基类定义
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict

logger = logging.getLogger(__name__)


class BaseSpider(ABC):
    """所有爬虫的基类"""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(self.name)

    @abstractmethod
    async def fetch_news(self) -> List[Dict]:
        """
        抓取新闻的抽象方法
        
        返回格式：
        [
            {
                'title': str,           # 新闻标题
                'content': str,         # 新闻内容/摘要
                'datetime': str,        # "YYYY-MM-DD HH:MM:SS" 格式
                'url': str,            # 新闻链接（可选）
                'source': str,         # 爬虫名称
            },
            ...
        ]
        
        异常处理：
        - 必须捕获所有异常，返回 []，不得抛出异常
        - 应记录错误日志用于调试
        """
        pass

    async def run_with_timeout(self, timeout_seconds: int = 30) -> List[Dict]:
        """带超时的执行"""
        try:
            return await asyncio.wait_for(self.fetch_news(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            self.logger.warning(f"{self.name} 爬虫超时 ({timeout_seconds}s)")
            return []
        except Exception as e:
            self.logger.error(f"{self.name} 爬虫执行失败: {str(e)}")
            return []
