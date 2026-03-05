#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块1: TTM股息率计算器
计算股票过去12个月（TTM）的股息率
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'instock'))

import logging
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

from instock.core.crawling.stock_fhps_em import stock_fhps_em

logger = logging.getLogger(__name__)


class DividendCalculator:
    """TTM股息率计算器"""
    
    # 分红报告期（年报+3个季报）
    REPORT_PERIODS = ['1231', '0930', '0630', '0331']
    
    def __init__(self):
        self._cache = {}  # 缓存分红数据
    
    def get_dividend_data(self, period: str) -> Optional[pd.DataFrame]:
        """
        获取指定报告期的分红数据
        :param period: 报告期，如 '20231231'
        :return: DataFrame 或 None
        """
        if period in self._cache:
            return self._cache[period]
        
        try:
            df = stock_fhps_em(date=period)
            if df is not None and len(df) > 0:
                self._cache[period] = df
                return df
        except Exception as e:
            logger.error(f"获取分红数据失败: period={period}, error={e}")
        
        return None
    
    def get_ttm_dividend(self, code: str) -> float:
        """
        获取股票过去12个月的累计分红（每股）
        :param code: 股票代码
        :return: TTM每股分红（元）
        """
        total_dividend = 0.0
        
        # 获取最近4个报告期的数据
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # 确定需要查询的报告期
        periods_to_check = []
        
        # 当前年份的报告期
        if current_month >= 4:
            periods_to_check.append(f"{current_year}1231")
        if current_month >= 10:
            periods_to_check.append(f"{current_year}0930")
        if current_month >= 7:
            periods_to_check.append(f"{current_year}0630")
        if current_month >= 4:
            periods_to_check.append(f"{current_year}0331")
        
        # 如果当前月份较早，需要查去年的数据
        if current_month < 4:
            periods_to_check.extend([
                f"{current_year-1}1231",
                f"{current_year-1}0930",
                f"{current_year-1}0630",
                f"{current_year-1}0331"
            ])
        elif current_month < 7:
            periods_to_check.extend([
                f"{current_year-1}1231",
                f"{current_year-1}0930",
                f"{current_year-1}0630"
            ])
        elif current_month < 10:
            periods_to_check.extend([
                f"{current_year-1}1231",
                f"{current_year-1}0930"
            ])
        else:
            periods_to_check.extend([
                f"{current_year-1}1231"
            ])
        
        # 累计分红
        for period in periods_to_check[:4]:  # 最多查4个报告期
            df = self.get_dividend_data(period)
            if df is None:
                continue
            
            # 查找该股票的分红记录
            stock_dividend = df[df['代码'] == code]
            if len(stock_dividend) > 0:
                # 获取现金分红比例（每10股分红）
                cash_div = stock_dividend['现金分红-现金分红比例'].values[0]
                if pd.notna(cash_div) and cash_div > 0:
                    # 转换为每股分红（元）
                    total_dividend += cash_div / 10.0
        
        return total_dividend
    
    def calculate_ttm_dividend_yield(self, code: str, current_price: float) -> Optional[float]:
        """
        计算TTM股息率
        :param code: 股票代码
        :param current_price: 当前股价
        :return: TTM股息率（百分比），如 5.5 表示 5.5%
        """
        if current_price <= 0:
            return None
        
        total_dividend = self.get_ttm_dividend(code)
        
        if total_dividend <= 0:
            return None
        
        # TTM股息率 = 过去12个月累计分红 / 当前股价 * 100%
        dividend_yield = (total_dividend / current_price) * 100
        
        return round(dividend_yield, 2)
    
    def batch_calculate(self, stocks: list) -> dict:
        """
        批量计算股息率
        :param stocks: [{'code': '600000', 'price': 8.5}, ...]
        :return: {'600000': 6.2, ...}
        """
        results = {}
        for stock in stocks:
            code = stock['code']
            price = stock['price']
            yield_rate = self.calculate_ttm_dividend_yield(code, price)
            if yield_rate is not None:
                results[code] = yield_rate
        return results


# 测试代码
if __name__ == "__main__":
    calc = DividendCalculator()
    
    # 测试单只股票
    code = "601318"  # 中国平安
    price = 45.0
    result = calc.calculate_ttm_dividend_yield(code, price)
    print(f"{code} TTM股息率: {result}%")
