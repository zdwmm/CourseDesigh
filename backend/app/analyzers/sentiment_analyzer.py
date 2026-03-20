import logging
from snownlp import SnowNLP
from typing import Dict, List

logger = logging.getLogger(__name__)


class NewsSegmentAnalyzer:
    """新闻情感分析器"""

    def __init__(self):
        # 股票市场常见词汇
        self.pos_words = [
            '利好', '增长', '上涨', '盈利', '收益', '扩张', '繁荣', 
            '突破', '强劲', '看涨', '业绩', '创新', '领先', '腾飞'
        ]
        self.neg_words = [
            '利空', '下跌', '减少', '亏损', '萎缩', '衰退', '破位', 
            '疲软', '看跌', '风险', '下滑', '困难', '挑战', '跌停'
        ]

        # 行业特定词汇（中药/药业）
        self.pharma_pos_words = [
            '新药', '政策扶持', '销售增长', '专利', '研发突破', 
            '中医药振兴', '获批', '上市', '销售稳定'
        ]
        self.pharma_neg_words = [
            '副作用', '监管趋严', '药价下降', '集采影响', 
            '原材料上涨', '假药', '质量问题', '召回'
        ]

    def analyze_single_news(
        self, 
        news_text: str, 
        industry: str = None
    ) -> Dict[str, float]:
        """
        【核心方法】分析单条新闻的情感
        
        参数：
        - news_text: 新闻内容
        - industry: 行业（可选，如 '中药'）
        
        返回：
        {
            'sentiment': float (-1 ~ 1),    # 情感得分
            'confidence': float (0 ~ 1),   # 置信度
            'has_market_words': bool,      # 是否包含市场词汇
            'has_industry_words': bool,    # 是否包含行业词汇
        }
        """
        if not isinstance(news_text, str) or not news_text.strip():
            return {
                'sentiment': 0.0,
                'confidence': 0.0,
                'has_market_words': False,
                'has_industry_words': False,
            }

        try:
            # 第一步：SnowNLP 基础情感分析
            # SnowNLP 返回值：0-1，1表示积极，0表示消极
            s = SnowNLP(news_text)
            base_sentiment = (s.sentiments - 0.5) * 2  # 转换为 -1~1

            # 第二步：市场词汇权重计算
            market_pos_count = sum(1 for word in self.pos_words if word in news_text)
            market_neg_count = sum(1 for word in self.neg_words if word in news_text)
            market_sentiment = (market_pos_count - market_neg_count) * 0.05

            # 第三步：行业词汇权重计算
            industry_sentiment = 0.0
            has_industry_words = False
            if industry == '中药':
                industry_pos_count = sum(1 for word in self.pharma_pos_words if word in news_text)
                industry_neg_count = sum(1 for word in self.pharma_neg_words if word in news_text)
                industry_sentiment = (industry_pos_count - industry_neg_count) * 0.08
                has_industry_words = (industry_pos_count + industry_neg_count) > 0

            # 第四步：综合得分
            final_sentiment = base_sentiment + market_sentiment + industry_sentiment
            final_sentiment = max(-1.0, min(1.0, final_sentiment))  # 限制范围

            # 置信度：基于词汇匹配度
            has_market_words = (market_pos_count + market_neg_count) > 0
            confidence = 0.5 + 0.25 * (market_pos_count + market_neg_count) / 10
            confidence = min(1.0, confidence)

            return {
                'sentiment': round(float(final_sentiment), 4),
                'confidence': round(float(confidence), 4),
                'has_market_words': has_market_words,
                'has_industry_words': has_industry_words,
            }

        except Exception as e:
            logger.error(f"情感分析失败: {e}")
            return {
                'sentiment': 0.0,
                'confidence': 0.0,
                'has_market_words': False,
                'has_industry_words': False,
            }

    def analyze_batch_news(
        self, 
        news_list: List[Dict],
        industry: str = None
    ) -> List[Dict]:
        """
        【批量分析】对多条新闻进行情感分析
        
        参数：
        - news_list: 新闻列表，每条新闻应包含 'content' 字段
        - industry: 行业信息
        
        返回：
        增加了 'sentiment_analysis' 字段的新闻列表
        """
        results = []
        for news in news_list:
            analysis = self.analyze_single_news(
                news.get('content', ''),
                industry=industry
            )
            result = news.copy()
            result['sentiment_analysis'] = analysis
            results.append(result)

        return results


class DailySentimentAggregator:
    """日度情感聚合器"""

    @staticmethod
    def aggregate_daily_sentiment(
        news_list: List[Dict],
        sentiment_key: str = 'sentiment_analysis'
    ) -> Dict[str, float]:
        """
        【聚合方法】将多条新闻情感聚合为单个日度评分
        
        参数：
        - news_list: 单日新闻列表
        - sentiment_key: 情感数据所在字段
        
        返回：
        {
            'daily_sentiment': float,      # 日度平均情感
            'weighted_sentiment': float,   # 加权情感（考虑置信度）
            'news_count': int,             # 新闻数量
            'positive_ratio': float,       # 正面新闻占比
        }
        """
        if not news_list:
            return {
                'daily_sentiment': 0.0,
                'weighted_sentiment': 0.0,
                'news_count': 0,
                'positive_ratio': 0.0,
            }

        sentiments = []
        weights = []
        positive_count = 0

        for news in news_list:
            if sentiment_key in news:
                analysis = news[sentiment_key]
                sentiment = analysis.get('sentiment', 0.0)
                confidence = analysis.get('confidence', 0.5)

                sentiments.append(sentiment)
                weights.append(confidence)

                if sentiment > 0.1:
                    positive_count += 1

        if not sentiments:
            return {
                'daily_sentiment': 0.0,
                'weighted_sentiment': 0.0,
                'news_count': len(news_list),
                'positive_ratio': 0.0,
            }

        # 简单平均
        avg_sentiment = sum(sentiments) / len(sentiments)

        # 加权平均（按置信度）
        total_weight = sum(weights)
        weighted_sentiment = sum(s * w for s, w in zip(sentiments, weights)) / total_weight if total_weight > 0 else 0

        positive_ratio = positive_count / len(news_list)

        return {
            'daily_sentiment': round(float(avg_sentiment), 4),
            'weighted_sentiment': round(float(weighted_sentiment), 4),
            'news_count': len(news_list),
            'positive_ratio': round(float(positive_ratio), 4),
        }
