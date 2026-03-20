#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块6: 定时任务调度
每天定时执行扫描任务
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'instock'))

import logging
import schedule
import time
from datetime import datetime, date
from typing import Optional
import pandas as pd

from instock.core.crawling.stock_hist_em import stock_zh_a_spot_em
from instock.lib import trade_time as trd

from dividend_strategy.config import (
    DIVIDEND_YIELD_THRESHOLD,
    PUSH_HOUR,
    PUSH_MINUTE
)
from dividend_strategy.dividend_calculator import DividendCalculator
from dividend_strategy.ma120_filter import MA120Filter
from dividend_strategy.stock_filter import StockFilter
from dividend_strategy.signal_manager import SignalManager
from dividend_strategy.feishu_pusher import FeishuPusher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DailyScheduler:
    """每日扫描调度器"""
    
    def __init__(self):
        self.dividend_calc = DividendCalculator()
        self.ma120_filter = MA120Filter()
        self.stock_filter = StockFilter()
        self.signal_manager = SignalManager()
        self.feishu_pusher = FeishuPusher()
    
    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """
        获取全市场股票列表
        :return: DataFrame
        """
        try:
            df = stock_zh_a_spot_em()
            if df is None or len(df) == 0:
                logger.error("获取股票列表失败")
                return None
            
            # 重命名列
            df.columns = [
                'new_price', 'change_rate', 'ups_downs', 'volume', 'deal_amount',
                'amplitude', 'turnoverrate', 'dtsyl', 'volume_ratio', 'speed_increase_5',
                'code', 'name', 'high_price', 'low_price', 'open_price', 'pre_close_price',
                'total_market_cap', 'free_cap', 'speed_increase', 'pbnewmrq',
                'speed_increase_60', 'speed_increase_all', 'listing_date', 'roe_weight',
                'total_shares', 'free_shares', 'total_operate_income', 'toi_yoy_ratio',
                'parent_netprofit', 'netprofit_yoy_ratio', 'per_unassign_profit',
                'sale_gpr', 'debt_asset_ratio', 'per_capital_reserve', 'industry',
                'basic_eps', 'bvps', 'pe', 'pe9', 'report_date'
            ]
            
            logger.info(f"获取股票列表成功，共 {len(df)} 只")
            return df
            
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return None
    
    def run_daily_scan(self, scan_date: date = None) -> dict:
        """
        执行每日扫描
        :param scan_date: 扫描日期，默认今天
        :return: 扫描结果
        """
        if scan_date is None:
            scan_date = date.today()
        
        date_str = scan_date.strftime("%Y-%m-%d")
        logger.info(f"开始执行每日扫描: {date_str}")
        
        result = {
            'date': date_str,
            'success': False,
            'total_stocks': 0,
            'filtered_stocks': 0,
            'dividend_qualified': 0,
            'ma120_qualified': 0,
            'final_signals': 0,
            'signals': [],
            'stats': {}
        }
        
        try:
            # 1. 获取股票列表
            df = self.get_stock_list()
            if df is None:
                return result
            
            result['total_stocks'] = len(df)
            
            # 2. 应用过滤器
            df = self.stock_filter.apply_all_filters(df)
            result['filtered_stocks'] = len(df)
            
            if len(df) == 0:
                logger.warning("过滤后无股票")
                return result
            
            # 3. 筛选股息率 >= 5% 的股票
            signals = []
            qualified_stocks = []
            
            for _, row in df.iterrows():
                code = row['code']
                price = row['new_price']
                
                # 计算TTM股息率
                dividend_yield = self.dividend_calc.calculate_ttm_dividend_yield(code, price)
                
                if dividend_yield is None or dividend_yield < DIVIDEND_YIELD_THRESHOLD:
                    continue
                
                # 检查是否低于MA120
                ma_result = self.ma120_filter.check_below_ma120(code, price)
                
                if not ma_result['is_below']:
                    continue
                
                # 满足条件，加入候选
                qualified_stocks.append({
                    'code': code,
                    'name': row['name'],
                    'new_price': price,
                    'ma120': ma_result['ma120'],
                    'discount': ma_result['discount'],
                    'dividend_yield': dividend_yield,
                    'industry': row.get('industry', ''),
                    'total_market_cap': row.get('total_market_cap', 0),
                    'deal_amount': row.get('deal_amount', 0)
                })
            
            result['dividend_qualified'] = len([s for s in qualified_stocks if s['dividend_yield'] >= DIVIDEND_YIELD_THRESHOLD])
            result['ma120_qualified'] = len(qualified_stocks)
            
            # 4. 更新信号状态
            new_signals = 0
            for stock in qualified_stocks:
                signal_result = self.signal_manager.update_signal(
                    stock['code'],
                    True,  # is_below_ma120
                    date_str
                )
                
                stock['signal_level'] = signal_result['signal_level']
                stock['consecutive_days'] = signal_result['consecutive_days']
                stock['is_new_signal'] = signal_result['is_new_signal']
                
                if signal_result['is_new_signal']:
                    new_signals += 1
                
                signals.append(stock)
            
            result['signals'] = signals
            result['final_signals'] = len(signals)
            
            # 5. 生成统计信息
            stats = self._generate_stats(signals, new_signals)
            result['stats'] = stats
            
            # 6. 推送飞书
            if signals:
                self.feishu_pusher.push(signals, stats)
            
            result['success'] = True
            logger.info(f"扫描完成: {len(signals)} 个信号")
            
        except Exception as e:
            logger.error(f"扫描失败: {e}", exc_info=True)
        
        return result
    
    def _generate_stats(self, signals: list, new_signals: int) -> dict:
        """生成统计信息"""
        # 行业分布
        industry_dist = {}
        for s in signals:
            industry = s.get('industry', '未知')
            industry_dist[industry] = industry_dist.get(industry, 0) + 1
        
        # 信号级别分布
        level_dist = {1: 0, 2: 0, 3: 0}
        for s in signals:
            level = s.get('signal_level', 0)
            if level in level_dist:
                level_dist[level] += 1
        
        return {
            'new_signals': new_signals,
            'total_signals': len(signals),
            'industry_distribution': industry_dist,
            'level_distribution': level_dist
        }
    
    def start_scheduler(self):
        """启动定时任务"""
        # 每天指定时间执行
        schedule_time = f"{PUSH_HOUR:02d}:{PUSH_MINUTE:02d}"
        schedule.every().day.at(schedule_time).do(self.run_daily_scan)
        
        logger.info(f"定时任务已启动，将在每天 {schedule_time} 执行")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def run_once(self):
        """手动执行一次"""
        return self.run_daily_scan()


# 测试代码
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='股息率定投信号系统')
    parser.add_argument('--schedule', action='store_true', help='启动定时任务')
    parser.add_argument('--once', action='store_true', help='执行一次扫描')
    args = parser.parse_args()
    
    scheduler = DailyScheduler()
    
    if args.schedule:
        scheduler.start_scheduler()
    elif args.once:
        result = scheduler.run_once()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        # 默认执行一次
        result = scheduler.run_once()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
