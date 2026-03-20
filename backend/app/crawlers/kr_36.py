# backend/app/crawlers/kr_36.py
"""
36氪实时新闻爬虫
数据源：https://www.36kr.com/
"""
import asyncio
import datetime
import re
import aiohttp
import logging
from typing import List, Dict
from lxml import etree
from .base import BaseSpider

logger = logging.getLogger(__name__)


class Kr36Spider(BaseSpider):
    def __init__(self):
        super().__init__("36kr")
        self.data = {
            "partner_id": "web",
            "param": {
                "type": 0,
                "subnavNick": "web_news",
                "pageSize": 20,
                "pageEvent": 1,
                "siteId": 1,
                "platformId": 2
            }
        }
        self.url = "https://gateway.36kr.com/api/mis/nav/newsflash/list"
        self.headers = {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Origin": "https://36kr.com",
            "Referer": "https://36kr.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    def _get_time(self, time_str: str) -> str:
        """将相对时间转换为标准格式
        
        例如：
        - "5分钟前" -> 当前时间 - 5分钟
        - "2小时前" -> 当前时间 - 2小时
        - "3天前" -> 当前时间 - 3天
        """
        now = datetime.datetime.now()
        pattern = r'(\d+)'
        pattern_1 = r'\d+([\u4e00-\u9fa5]+)'

        try:
            match = int(re.search(pattern, time_str).group(1))
            match_1 = re.search(pattern_1, time_str).group(1)
        except (AttributeError, ValueError):
            return now.strftime("%Y-%m-%d %H:%M:%S")

        if match_1 == '秒前':
            delta = datetime.timedelta(seconds=match)
        elif match_1 == '分钟前':
            delta = datetime.timedelta(minutes=match)
        elif match_1 == '天前':
            delta = datetime.timedelta(days=match)
        elif match_1 == '小时前':
            delta = datetime.timedelta(hours=match)
        else:
            delta = datetime.timedelta(hours=24)

        return (now - delta).strftime("%Y-%m-%d %H:%M:%S")

    def _get_first_pageCallback(self) -> str:
        """
        【重要】获取第一个 pageCallback
        
        说明：
        - 36氪 API 使用分页令牌 pageCallback 来控制数据获取
        - 第一次请求需要从网页中提取初始的 pageCallback
        - 后续每次请求会返回新的 pageCallback 用于下一页
        """
        try:
            headers = {
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            }
            url = "https://36kr.com/newsflashes/catalog/0"
            resp = asyncio.run(self._fetch_html(url, headers))
            
            if not resp:
                return None

            # 从页面源代码中提取 pageCallback
            pattern = r'"pageCallback":\s*"([^"]+)"'
            match = re.search(pattern, resp)
            return match.group(1) if match else None
        except Exception as e:
            self.logger.error(f"获取 pageCallback 失败: {e}")
            return None

    async def _fetch_html(self, url: str, headers: dict) -> str:
        """异步获取网页内容"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    return await response.text()
        except Exception as e:
            self.logger.warning(f"获取 HTML 失败 ({url}): {e}")
            return None

    async def fetch_news(self) -> List[Dict]:
        """
        【爬虫核心方法】获取36氪新闻
        
        工作流程：
        1. 获取初始分页令牌（pageCallback）
        2. 循环请求多页数据（默认4页 = 80条新闻）
        3. 提取新闻标题、内容和发布时间
        4. 统一返回格式
        
        【可能的问题】：
        - 网站改版可能导致选择器失效
        - API 频率限制：建议间隔 >= 2秒
        - 时间戳可能出现解析错误
        """
        try:
            news_list = []
            page_callback = self._get_first_pageCallback()
            
            if not page_callback:
                self.logger.warning("无法获取初始 pageCallback，跳过")
                return []

            # 【关键】每个数据源设置不同的间隔，避免频率限制
            for page in range(1, 5):  # 获取前4页
                try:
                    self.data['param']['pageCallback'] = page_callback
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            self.url, 
                            headers=self.headers, 
                            json=self.data,
                            timeout=10
                        ) as response:
                            res = await response.json()
                            
                            if not res.get('data', {}).get('itemList'):
                                break

                            page_callback = res['data'].get('pageCallback')

                            for item in res['data']['itemList']:
                                try:
                                    news_item = {
                                        'title': item.get('templateMaterial', {}).get('widgetTitle', ''),
                                        'content': item.get('templateMaterial', {}).get('widgetContent', ''),
                                        'datetime': datetime.datetime.fromtimestamp(
                                            int(item['templateMaterial']['publishTime']) / 1000
                                        ).strftime("%Y-%m-%d %H:%M:%S"),
                                        'url': item.get('templateMaterial', {}).get('itemUrl', ''),
                                        'source': self.name,
                                    }
                                    if news_item['title']:  # 必须有标题
                                        news_list.append(news_item)
                                except (KeyError, ValueError, TypeError) as e:
                                    self.logger.debug(f"解析单条新闻失败: {e}")
                                    continue

                    # 【重要】请求间隔，避免被限流
                    await asyncio.sleep(2)

                except Exception as e:
                    self.logger.error(f"第 {page} 页请求失败: {e}")
                    continue

            self.logger.info(f"成功获取 {len(news_list)} 条 36氪新闻")
            return news_list

        except Exception as e:
            self.logger.error(f"36氪爬虫异常: {str(e)}")
            return []
