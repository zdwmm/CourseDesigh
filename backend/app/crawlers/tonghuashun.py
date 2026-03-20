# backend/app/crawlers/tonghuashun.py
"""
同花顺实时新闻爬虫
数据源：https://news.10jqka.com.cn/
"""
import asyncio
import aiohttp
import datetime
import logging
from typing import List, Dict
from .base import BaseSpider

logger = logging.getLogger(__name__)


class ThsSpider(BaseSpider):
    def __init__(self):
        super().__init__("tonghuashun")
        self.headers = {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Referer": "https://news.10jqka.com.cn/realtimenews.html",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }
        self.url = "https://news.10jqka.com.cn/tapp/news/push/stock/"
        self.params = {
            "page": "1",
            "tag": "",
            "track": "website",
            "pagesize": "400"
        }

    async def fetch_news(self) -> List[Dict]:
        """
        【爬虫核心方法】获取同花顺新闻
        
        特点：
        - 一次请求可获取 400 条新闻
        - tags 字段包含新闻分类标签
        - digest 是新闻摘要
        
        【可能的问题】：
        - 网站频繁变更 API，容易出现 404
        - digest 字段可能为空
        - tags 数组可能为空
        """
        try:
            news_list = []

            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(
                    self.url,
                    params=self.params,
                    timeout=10
                ) as response:
                    if response.status != 200:
                        self.logger.error(f"同花顺 API 返回 {response.status}")
                        return []

                    res = await response.json()

                    if 'data' not in res or 'list' not in res['data']:
                        self.logger.warning("同花顺返回数据格式异常")
                        return []

                    for item in res['data']['list']:
                        try:
                            news_item = {
                                'title': item.get('title', ''),
                                'content': item.get('digest', ''),
                                'datetime': datetime.datetime.fromtimestamp(
                                    int(item['ctime'])
                                ).strftime("%Y-%m-%d %H:%M:%S"),
                                'url': item.get('url', ''),
                                'source': self.name,
                            }
                            if news_item['title']:
                                news_list.append(news_item)
                        except (KeyError, ValueError, TypeError) as e:
                            self.logger.debug(f"解析新闻失败: {e}")
                            continue

            self.logger.info(f"成功获取 {len(news_list)} 条同花顺新闻")
            return news_list

        except asyncio.TimeoutError:
            self.logger.error("同花顺爬虫超时")
            return []
        except Exception as e:
            self.logger.error(f"同花顺爬虫异常: {str(e)}")
            return []
