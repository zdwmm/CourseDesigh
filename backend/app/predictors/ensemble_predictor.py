"""
综合预测器 - 融合情感分析和技术指标
"""
import logging
from typing import Dict, Optional
from datetime import datetime
from sqlmodel import Session, select
from ..database import get_engine
from ..models import NewsItem, PriceHistory
from ..analyzers.sentiment_analyzer import DailySentimentAggregator
from ..analyzers.technical_analyzer import TechnicalAnalysisReport
import pandas as pd

logger = logging.getLogger(__name__)


class PredictionEnsembler:
    """预测融合器"""

    @staticmethod
    def generate_prediction_signal(
        stock_code: str,
        sentiment_score: float = 0.0,
        technical_score: float = 50.0,
        weight_sentiment: float = 0.4,
        weight_technical: float = 0.6,
    ) -> Dict:
        """
        【核心方法】融合情感和技术指标���成预测信号
        
        参数：
        - sentiment_score: 情感得分 (-1 ~ 1)
        - technical_score: 技术评分 (0 ~ 100)
        - weight_sentiment: 情感权重（默认 40%）
        - weight_technical: 技术权重（默认 60%）
        
        返回：
        {
            'signal': 'BUY' | 'HOLD' | 'SELL',
            'confidence': float (0-1),
            'predicted_direction': 'UP' | 'DOWN' | 'NEUTRAL',
            'recommendation': str,
        }
        """
        try:
            # 标准化情感得分到 0-100
            sentiment_normalized = (sentiment_score + 1) / 2 * 100

            # 融合评分
            ensemble_score = (
                sentiment_normalized * weight_sentiment +
                technical_score * weight_technical
            )

            # 生成信号
            if ensemble_score >= 60:
                signal = 'BUY'
                confidence = (ensemble_score - 50) / 50
                direction = 'UP'
            elif ensemble_score <= 40:
                signal = 'SELL'
                confidence = (50 - ensemble_score) / 50
                direction = 'DOWN'
            else:
                signal = 'HOLD'
                confidence = 0.3
                direction = 'NEUTRAL'

            # 生成建议
            if signal == 'BUY':
                if confidence > 0.7:
                    recommendation = '强烈建议买入'
                else:
                    recommendation = '可以考虑买入'
            elif signal == 'SELL':
                if confidence > 0.7:
                    recommendation = '强烈建议卖出'
                else:
                    recommendation = '可以考虑卖出'
            else:
                if sentiment_score > 0.2:
                    recommendation = '保持持有，关注正面信息'
                elif sentiment_score < -0.2:
                    recommendation = '保持观望，警惕负面信息'
                else:
                    recommendation = '市场处于平衡状态，谨慎操作'

            return {
                'signal': signal,
                'confidence': round(float(confidence), 4),
                'predicted_direction': direction,
                'ensemble_score': round(float(ensemble_score), 2),
                'recommendation': recommendation,
                'timestamp': datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"生成预测信号失败: {e}")
            return {
                'signal': 'HOLD',
                'confidence': 0.0,
                'predicted_direction': 'NEUTRAL',
                'recommendation': '数据异常，无法生成预测',
                'error': str(e),
            }
