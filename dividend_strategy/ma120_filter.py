#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块2: MA120筛选器
筛选收盘价低于120日均线的股票
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'instock'))

import logging
from typing import Optional, Dict
import numpy as np
import pandas as pd
import talib as tl

from instock.core.crawling.stock_hist_em import stock_zh_a_hist
from dividend_strategy.config import MA_PERIOD

logger = logging.getLogger(__name__)


class MA120Filter:
    """MA120筛选器"""
    
    def __init__(self, period: int = MA_PERIOD):
        self.period = period
    
    def get_stock_hist(self, code: str, days: int = 200) -> Optional[pd.DataFrame]:
        """
        获取股票历史K线数据
        :param code: 股票代码
        :param days: 需要的交易日数量
        :return: DataFrame 或 None
        """
        try:
            # 计算开始日期（往前推足够多的天数确保有足够的交易日）
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=days * 1.5)).strftime("%Y%m%d")
            
            df = stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                adjust="qfq"  # 前复权
            )
            
            if df is None or len(df) < self.period:
                return None
            
            return df
            
        except Exception as e:
            logger.error(f"获取历史K线失败: code={code}, error={e}")
            return None
    
    def calculate_ma120(self, df: pd.DataFrame) -> Optional[float]:
        """
        计算MA120
        :param df: 历史K线DataFrame
        :return: MA120值
        """
        if df is None or len(df) < self.period:
            return None
        
        try:
            close_prices = df['收盘'].values.astype(float)
            ma_values = tl.MA(close_prices, timeperiod=self.period)
            
            # 返回最新的MA120值
            ma120 = ma_values[-1]
            
            if np.isnan(ma120):
                return None
            
            return round(ma120, 2)
            
        except Exception as e:
            logger.error(f"计算MA120失败: error={e}")
            return None
    
    def check_below_ma120(self, code: str, current_price: float) -> Dict:
        """
        检查股票是否低于MA120
        :param code: 股票代码
        :param current_price: 当前股价
        :return: {
            'is_below': bool,
            'ma120': float,
            'discount': float,  # 折扣率，负数表示低于MA120
            'distance': float   # 距离MA120的百分比
        }
        """
        result = {
            'is_below': False,
            'ma120': None,
            'discount': None,
            'distance': None
        }
        
        if current_price <= 0:
            return result
        
        # 获取历史数据
        df = self.get_stock_hist(code)
        if df is None:
            return result
        
        # 计算MA120
        ma120 = self.calculate_ma120(df)
        if ma120 is None:
            return result
        
        result['ma120'] = ma120
        
        # 计算折扣率
        result['distance'] = round((current_price / ma120 - 1) * 100, 2)
        result['discount'] = result['distance']
        
        # 判断是否低于MA120
        result['is_below'] = current_price < ma120
        
        return result
    
    def batch_check(self, stocks: list) -> dict:
        """
        批量检查
        :param stocks: [{'code': '600000', 'price': 8.5}, ...]
        :return: {
            '600000': {'is_below': True, 'ma120': 9.2, 'discount': -7.6, ...},
            ...
        }
        """
        results = {}
        for stock in stocks:
            code = stock['code']
            price = stock['price']
            result = self.check_below_ma120(code, price)
            if result['ma120'] is not None:
                results[code] = result
        return results


# 测试代码
if __name__ == "__main__":
    filter_ma = MA120Filter()
    
    # 测试单只股票
    code = "600000"  # 浦发银行
    price = 8.5
    result = filter_ma.check_below_ma120(code, price)
    print(f"{code}: MA120={result['ma120']}, 低于MA120={result['is_below']}, 折扣={result['discount']}%")
