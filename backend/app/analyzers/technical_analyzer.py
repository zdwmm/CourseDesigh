"""
技术指标分析模块
计算 MA、RSI、MACD、布林带等指标
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class TechnicalIndicatorCalculator:
    """技术指标计算器"""

    @staticmethod
    def calculate_sma(series: pd.Series, period: int = 20) -> pd.Series:
        """
        计算简单移动平均（SMA）
        
        SMA = 过去 N 天收盘价的平均值
        【用途】：识别长期趋势，平滑价格波动
        """
        return series.rolling(window=period).mean()

    @staticmethod
    def calculate_ema(series: pd.Series, period: int = 12) -> pd.Series:
        """
        计算指数移动平均（EMA）
        
        EMA 对最近的价格赋予更高权重
        【用途】：比 SMA 更快反映价格变化
        """
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """
        计算相对强弱指数（RSI）
        
        RSI = 100 - (100 / (1 + RS))
        其中 RS = 平均涨幅 / 平均跌幅
        
        【范围】：0-100
        【解释】：
        - > 70: 超买（可能下跌）
        - < 30: 超卖（可能上涨）
        """
        delta = series.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)

        ema_up = up.ewm(span=period, adjust=False).mean()
        ema_down = down.ewm(span=period, adjust=False).mean()

        rs = ema_up / ema_down
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_macd(
        series: pd.Series, 
        fast: int = 12, 
        slow: int = 26, 
        signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        计算 MACD 指标（动量指标）
        
        MACD = 12日EMA - 26日EMA
        Signal = 9日EMA(MACD)
        Histogram = MACD - Signal
        
        【信号】：
        - MACD > Signal: 买入信号
        - MACD < Signal: 卖出信号
        - Histogram 为正且扩大：上升动力强
        """
        fast_ema = series.ewm(span=fast, adjust=False).mean()
        slow_ema = series.ewm(span=slow, adjust=False).mean()

        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def calculate_bollinger_bands(
        series: pd.Series, 
        window: int = 20, 
        std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        计算布林带（波动率指标）
        
        中轨 = 20日SMA
        上轨 = 中轨 + (2 × 标准差)
        下轨 = 中轨 - (2 × 标准差)
        
        【用途】：
        - 价格触及上轨：可能超买
        - 价格触及下���：可能超卖
        """
        middle = series.rolling(window=window).mean()
        std = series.rolling(window=window).std()

        upper = middle + std_dev * std
        lower = middle - std_dev * std

        return upper, middle, lower

    @staticmethod
    def calculate_stochastic(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_window: int = 14,
        d_window: int = 3
    ) -> Tuple[pd.Series, pd.Series]:
        """
        计算随机指标（KDJ）
        
        K = 100 × ((当前收盘价 - 最低价) / (最高价 - 最低价))
        D = K 的 3 日移动平均
        
        【范围】：0-100
        【解释】：
        - K > 80: 超买
        - K < 20: 超卖
        """
        lowest_low = low.rolling(window=k_window).min()
        highest_high = high.rolling(window=k_window).max()

        denom = highest_high - lowest_low
        # 避免除以零
        denom = denom.replace(0, 0.001)

        k_line = 100 * ((close - lowest_low) / denom)
        d_line = k_line.rolling(window=d_window).mean()

        return k_line, d_line

    @staticmethod
    def calculate_atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        计算真实波幅（ATR）
        
        【用途】：衡量价格波动的幅度
        【应用】：设置止损点、判断市场波动性
        """
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        return atr


class TechnicalAnalysisReport:
    """技术分析报告生成器"""

    @staticmethod
    def generate_report(df: pd.DataFrame) -> Dict:
        """
        【综合分析】生成技术面分析报告
        
        参数：
        - df: 包含 high, low, close, volume 的价格数据
        
        返回：
        {
            'current_price': float,
            'trend': 'bullish' | 'bearish' | 'neutral',
            'momentum': 'strong' | 'weak' | 'neutral',
            'volatility': 'high' | 'low',
            'support_levels': [float, ...],
            'resistance_levels': [float, ...],
            'technical_score': float (0-100),
        }
        """
        if df.empty or len(df) < 26:
            return {'error': '数据不足'}

        try:
            current_price = df['close'].iloc[-1]

            # 计算所有指标
            calc = TechnicalIndicatorCalculator()
            
            sma20 = calc.calculate_sma(df['close'], 20).iloc[-1]
            sma50 = calc.calculate_sma(df['close'], 50).iloc[-1] if len(df) >= 50 else sma20
            
            rsi = calc.calculate_rsi(df['close']).iloc[-1]
            
            macd, signal, hist = calc.calculate_macd(df['close'])
            macd_val = macd.iloc[-1]
            hist_val = hist.iloc[-1]

            upper, middle, lower = calc.calculate_bollinger_bands(df['close'])
            bb_upper = upper.iloc[-1]
            bb_lower = lower.iloc[-1]

            # 趋势判断
            if current_price > sma20 > sma50:
                trend = 'bullish'
            elif current_price < sma20 < sma50:
                trend = 'bearish'
            else:
                trend = 'neutral'

            # 动能判断
            if macd_val > signal.iloc[-1] and hist_val > 0:
                momentum = 'strong'
            elif macd_val < signal.iloc[-1] and hist_val < 0:
                momentum = 'weak'
            else:
                momentum = 'neutral'

            # 波动率判断
            atr = calc.calculate_atr(df['high'], df['low'], df['close']).iloc[-1]
            volatility = 'high' if atr > current_price * 0.02 else 'low'

            # 支撑阻力位
            support_levels = [lower.iloc[-1], bb_lower]
            resistance_levels = [upper.iloc[-1], bb_upper]

            # 技术评分（0-100）
            score = 50
            if trend == 'bullish':
                score += 20
            elif trend == 'bearish':
                score -= 20

            if rsi > 70:
                score -= 10
            elif rsi < 30:
                score += 10

            if momentum == 'strong':
                score += 10
            elif momentum == 'weak':
                score -= 10

            score = max(0, min(100, score))

            return {
                'current_price': round(float(current_price), 2),
                'trend': trend,
                'momentum': momentum,
                'volatility': volatility,
                'rsi': round(float(rsi), 2),
                'macd': round(float(macd_val), 4),
                'signal': round(float(signal.iloc[-1]), 4),
                'support_level': round(float(min(support_levels)), 2),
                'resistance_level': round(float(max(resistance_levels)), 2),
                'technical_score': round(float(score), 2),
            }

        except Exception as e:
            logger.error(f"技术分析失败: {e}")
            return {'error': str(e)}
