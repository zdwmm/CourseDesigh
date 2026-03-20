# backend/app/crawlers/cailianshe.py
"""
财联社电报爬虫
数据源：https://www.cls.cn/telegraph
"""
import asyncio
import aiohttp
import datetime
import logging
from typing import List, Dict
from .base import BaseSpider

logger = logging.getLogger(__name__)


class ClsSpider(BaseSpider):
    def __init__(self):
        super().__init__("cailianshe")
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "application/json;charset=utf-8",
            "Pragma": "no-cache",
            "Referer": "https://www.cls.cn/telegraph",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        self.url = "https://www.cls.cn/nodeapi/updateTelegraphList"
        self.params = {
            "app": "CailianpressWeb",
            "category": "",
            "hasFirstVipArticle": "1",
            "lastTime": str(int(datetime.datetime.now().timestamp())),
            "os": "web",
            "rn": "20",
            "subscribedColumnIds": "",
            "sv": "8.4.6",
        }

    async def fetch_news(self) -> List[Dict]:
        """
        【爬虫核心方法】获取财联社新闻
        
        特点：
        - 返回的 level 字段标记新闻重要性（A: 高, B: 中, 其他: 低）
        - vipGlobal 字段包含 VIP 新闻
        - 每次请求返回 20 条新闻
        
        【可能的问题】：
        - 网站需要有效的 Cookie，可能过期
        - API 响应可能包含 null 字段
        - 时间戳为 Unix 秒级时间戳
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
                        self.logger.error(f"财联社 API 返回 {response.status}")
                        return []

                    res = await response.json()
                    
                    # 处理主要新闻流
                    if 'data' in res and 'roll_data' in res['data']:
                        for item in res['data']['roll_data']:
                            try:
                                news_item = {
                                    'title': item.get('content', ''),  # 财联社没有单独标题，用内容作标题
                                    'content': item.get('content', ''),
                                    'datetime': datetime.datetime.fromtimestamp(
                                        int(item['ctime'])
                                    ).strftime("%Y-%m-%d %H:%M:%S"),
                                    'url': item.get('shareUrl', ''),
                                    'source': self.name,
                                }
                                if news_item['title']:
                                    news_list.append(news_item)
                            except (KeyError, ValueError, TypeError) as e:
                                self.logger.debug(f"解析新闻失败: {e}")
                                continue

                    # 处理 VIP 新闻
                    if 'vipGlobal' in res:
                        for item in res['vipGlobal']:
                            try:
                                news_item = {
                                    'title': item.get('brief', ''),
                                    'content': item.get('brief', ''),
                                    'datetime': datetime.datetime.fromtimestamp(
                                        int(item['ctime'])
                                    ).strftime("%Y-%m-%d %H:%M:%S"),
                                    'url': item.get('shareUrl', ''),
                                    'source': self.name,
                                }
                                if news_item['title']:
                                    news_list.append(news_item)
                            except (KeyError, ValueError, TypeError) as e:
                                self.logger.debug(f"解析 VIP 新闻失败: {e}")
                                continue

            self.logger.info(f"成功获取 {len(news_list)} 条财联社新闻")
            return news_list

        except asyncio.TimeoutError:
            self.logger.error("财联社爬虫超时")
            return []
        except Exception as e:
            self.logger.error(f"财联社爬虫异常: {str(e)}")
            return []
