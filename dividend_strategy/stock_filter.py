#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块3: 过滤器
过滤不符合条件的股票
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'instock'))

import logging
from datetime import datetime, timedelta
from typing import List
import numpy as np
import pandas as pd

from dividend_strategy.config import (
    MIN_MARKET_CAP,
    MIN_DEAL_AMOUNT,
    MIN_LISTING_DAYS
)

logger = logging.getLogger(__name__)


class StockFilter:
    """股票过滤器"""
    
    def __init__(self):
        self.filter_stats = {}  # 记录过滤统计
    
    def filter_st_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        过滤ST股票
        :param df: 股票数据
        :return: 过滤后的数据
        """
        before_count = len(df)
        
        # 过滤名称包含ST的股票
        df = df[~df['name'].str.contains('ST', case=False, na=False)]
        
        filtered = before_count - len(df)
        self.filter_stats['ST股票'] = filtered
        logger.info(f"过滤ST股票: {filtered}只")
        
        return df
    
    def filter_suspended_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        过滤停牌股票（成交额为0）
        :param df: 股票数据
        :return: 过滤后的数据
        """
        before_count = len(df)
        
        # 成交额大于0表示在交易
        df = df[df['deal_amount'] > 0]
        
        filtered = before_count - len(df)
        self.filter_stats['停牌股票'] = filtered
        logger.info(f"过滤停牌股票: {filtered}只")
        
        return df
    
    def filter_new_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        过滤新股（上市不足1年）
        :param df: 股票数据
        :return: 过滤后的数据
        """
        before_count = len(df)
        
        today = datetime.now().date()
        min_listing_date = today - timedelta(days=MIN_LISTING_DAYS)
        
        # 上市日期早于最小上市日期
        df = df[df['listing_date'] < min_listing_date]
        
        filtered = before_count - len(df)
        self.filter_stats['新股'] = filtered
        logger.info(f"过滤新股: {filtered}只")
        
        return df
    
    def filter_small_cap(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        过滤市值过小的股票
        :param df: 股票数据
        :return: 过滤后的数据
        """
        before_count = len(df)
        
        # 总市值 >= 最小市值
        df = df[df['total_market_cap'] >= MIN_MARKET_CAP]
        
        filtered = before_count - len(df)
        self.filter_stats['市值过小'] = filtered
        logger.info(f"过滤市值过小: {filtered}只")
        
        return df
    
    def filter_low_liquidity(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        过滤流动性差的股票
        :param df: 股票数据
        :return: 过滤后的数据
        """
        before_count = len(df)
        
        # 成交额 >= 最小成交额
        df = df[df['deal_amount'] >= MIN_DEAL_AMOUNT]
        
        filtered = before_count - len(df)
        self.filter_stats['流动性差'] = filtered
        logger.info(f"过滤流动性差: {filtered}只")
        
        return df
    
    def filter_invalid_price(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        过滤价格无效的股票（可能退市）
        :param df: 股票数据
        :return: 过滤后的数据
        """
        before_count = len(df)
        
        # 价格必须大于0且不是NaN
        df = df[df['new_price'].notna() & (df['new_price'] > 0)]
        
        filtered = before_count - len(df)
        self.filter_stats['价格无效'] = filtered
        logger.info(f"过滤价格无效: {filtered}只")
        
        return df
    
    def apply_all_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        应用所有过滤器
        :param df: 原始股票数据
        :return: 过滤后的数据
        """
        self.filter_stats = {}
        initial_count = len(df)
        
        logger.info(f"开始过滤，原始数量: {initial_count}")
        
        # 按顺序应用所有过滤器
        df = self.filter_invalid_price(df)
        df = self.filter_st_stocks(df)
        df = self.filter_suspended_stocks(df)
        df = self.filter_new_stocks(df)
        df = self.filter_small_cap(df)
        df = self.filter_low_liquidity(df)
        
        final_count = len(df)
        self.filter_stats['总计过滤'] = initial_count - final_count
        
        logger.info(f"过滤完成，剩余数量: {final_count}")
        logger.info(f"过滤统计: {self.filter_stats}")
        
        return df
    
    def get_filter_stats(self) -> dict:
        """获取过滤统计"""
        return self.filter_stats


# 测试代码
if __name__ == "__main__":
    # 创建测试数据
    test_data = pd.DataFrame([
        {'code': '600000', 'name': '浦发银行', 'new_price': 8.5, 'deal_amount': 100000000, 'total_market_cap': 200000000000, 'listing_date': datetime(2000, 1, 1).date()},
        {'code': '000001', 'name': 'ST平安', 'new_price': 10.0, 'deal_amount': 50000000, 'total_market_cap': 300000000000, 'listing_date': datetime(2000, 1, 1).date()},
        {'code': '000002', 'name': '万科A', 'new_price': 15.0, 'deal_amount': 0, 'total_market_cap': 150000000000, 'listing_date': datetime(2000, 1, 1).date()},
    ])
    
    filter_obj = StockFilter()
    result = filter_obj.apply_all_filters(test_data)
    print(f"过滤后: {len(result)}只")
    print(f"统计: {filter_obj.get_filter_stats()}")
