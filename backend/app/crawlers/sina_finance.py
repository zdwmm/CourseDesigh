# backend/app/crawlers/sina_finance.py
"""
新浪财经实时新闻爬虫
数据源：https://finance.sina.com.cn/
"""
import asyncio
import aiohttp
import datetime
import logging
from typing import List, Dict
from .base import BaseSpider

logger = logging.getLogger(__name__)


class SinaSpider(BaseSpider):
    def __init__(self):
        super().__init__("sinafinance")
        self.headers = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://finance.sina.com.cn/stock/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        self.url = "https://zhibo.sina.com.cn/api/zhibo/feed"
        self.params = {
            "zhibo_id": "152",
            "id": "",
            "tag_id": "0",
            "page": "1",
            "page_size": "20",
            "type": "0",
        }

    async def fetch_news(self) -> List[Dict]:
        """
        【爬虫核心方法】获取新浪财经新闻
        
        特点：
        - 使用 zhibo_id=152 为财经频道
        - create_time 已是标准格式
        - rich_text 包含新闻内容
        
        【可能的问题】：
        - API 返回嵌套结构复杂，容易出现 KeyError
        - 某些项目 rich_text 为空
        - 时间格式需要确认
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
                        self.logger.error(f"新浪财经 API 返回 {response.status}")
                        return []

                    res = await response.json()

                    # 检查响应结构
                    try:
                        feed_list = res['result']['data']['feed']['list']
                    except (KeyError, TypeError):
                        self.logger.warning("新浪财经返回数据格式异常")
                        return []

                    for item in feed_list:
                        try:
                            news_item = {
                                'title': item.get('title', ''),
                                'content': item.get('rich_text', ''),
                                'datetime': item.get('create_time', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                                'url': item.get('url', ''),
                                'source': self.name,
                            }
                            if news_item['title']:
                                news_list.append(news_item)
                        except (KeyError, ValueError, TypeError) as e:
                            self.logger.debug(f"解析新闻失败: {e}")
                            continue

            self.logger.info(f"成功获取 {len(news_list)} 条新浪财经新闻")
            return news_list

        except asyncio.TimeoutError:
            self.logger.error("新浪财经爬虫超时")
            return []
        except Exception as e:
            self.logger.error(f"新浪财经爬虫异常: {str(e)}")
            return []
