# backend/app/crawlers/kr_36氪.py

import asyncio
import aiohttp
import datetime
from typing import List, Dict, Optional
from lxml import etree
from .base import BaseSpider  # ✅ 导入基类


class Kr36Spider(BaseSpider):  # ✅ 继承 BaseSpider
    def __init__(self):
        super().__init__("36kr")  # ✅ 调用父类初始化
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
            "Pragma": "no-cache",
            "Referer": "https://36kr.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    async def _async_get_first_pageCallback(self) -> Optional[str]:
        """【异步版本】获取第一个 pageCallback"""
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        url = "https://36kr.com/newsflashes/catalog/0"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        self.logger.error(f"获取首页失败，状态码: {response.status}")
                        return None

                    html = await response.text()

            parser = etree.HTML(html)
            if parser is None:
                self.logger.error("HTML 解析失败")
                return None

            items = parser.xpath('//div[@class="newsflash-catalog-flow-list"]/div[@class="flow-item"]')
            if not items:
                self.logger.warning("未找到新闻列表")
                return None

            import re
            pattern = r'"pageCallback":\s*"([^"]+)"'
            match = re.search(pattern, html)
            if match:
                page_callback = match.group(1)
                self.logger.info(f"成功获取初始 pageCallback")
                return page_callback
            else:
                self.logger.warning("未找到 pageCallback")
                return None

        except asyncio.TimeoutError:
            self.logger.error("获取首页超时")
            return None
        except Exception as e:
            self.logger.error(f"获取首页异常: {str(e)}")
            return None

    async def fetch_news(self) -> List[Dict]:
        """【爬虫核心方法】获取36氪新闻"""
        try:
            news_list = []

            page_callback = await self._async_get_first_pageCallback()

            if not page_callback:
                self.logger.warning("无法获取初始 pageCallback，跳过")
                return []

            for page in range(1, 5):
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
                                    if news_item['title']:
                                        news_list.append(news_item)
                                except (KeyError, ValueError, TypeError) as e:
                                    self.logger.debug(f"解析单条新闻失败: {e}")
                                    continue

                    await asyncio.sleep(2)

                except Exception as e:
                    self.logger.error(f"第 {page} 页请求失败: {e}")
                    continue

            self.logger.info(f"成功获取 {len(news_list)} 条 36氪新闻")
            return news_list

        except Exception as e:
            self.logger.error(f"36氪爬虫异常: {str(e)}")
            return []
