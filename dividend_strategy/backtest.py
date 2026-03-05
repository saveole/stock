#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块7: 回测系统
对过去5年的数据进行回测
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'instock'))

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import pandas as pd
import numpy as np

from instock.core.crawling.stock_hist_em import stock_zh_a_hist
from instock.lib import trade_time as trd

from dividend_strategy.config import (
    BACKTEST_START_DATE,
    BACKTEST_END_DATE,
    DIVIDEND_YIELD_THRESHOLD,
    MA_PERIOD,
    SIGNAL_LEVEL_2_DAYS,
    SIGNAL_LEVEL_3_DAYS
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Backtester:
    """回测系统"""
    
    def __init__(self):
        self.results = {}
        self.signal_records = []
    
    def get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """
        获取交易日列表
        :param start_date: 开始日期 YYYY-MM-DD
        :param end_date: 结束日期 YYYY-MM-DD
        :return: 交易日列表
        """
        try:
            # 获取交易日历
            trade_dates = trd.tool_trade_date_hist_sina()
            if trade_dates is None:
                return []
            
            # 筛选日期范围
            dates = trade_dates[
                (trade_dates['trade_date'] >= start_date) & 
                (trade_dates['trade_date'] <= end_date)
            ]['trade_date'].tolist()
            
            return dates
            
        except Exception as e:
            logger.error(f"获取交易日失败: {e}")
            return []
    
    def get_stock_hist_batch(self, codes: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """
        批量获取股票历史数据
        :param codes: 股票代码列表
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: {code: DataFrame}
        """
        results = {}
        total = len(codes)
        
        for i, code in enumerate(codes):
            if (i + 1) % 100 == 0:
                logger.info(f"获取历史数据进度: {i+1}/{total}")
            
            try:
                df = stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                    adjust="qfq"
                )
                
                if df is not None and len(df) >= MA_PERIOD:
                    results[code] = df
                    
            except Exception as e:
                logger.debug(f"获取 {code} 历史数据失败: {e}")
        
        logger.info(f"成功获取 {len(results)}/{total} 只股票的历史数据")
        return results
    
    def calculate_ma120(self, df: pd.DataFrame) -> pd.Series:
        """计算MA120"""
        import talib as tl
        close = df['收盘'].values.astype(float)
        ma = tl.MA(close, timeperiod=MA_PERIOD)
        return pd.Series(ma, index=df.index)
    
    def calculate_dividend_yield_ttm(self, dividends: List[float], price: float) -> float:
        """
        计算TTM股息率
        :param dividends: 过去12个月的每股分红
        :param price: 当前股价
        :return: 股息率百分比
        """
        if price <= 0:
            return 0
        total_div = sum(dividends)
        return (total_div / price) * 100
    
    def simulate_signal(
        self, 
        code: str, 
        hist_df: pd.DataFrame,
        dividend_data: Dict[str, float] = None
    ) -> List[Dict]:
        """
        模拟单只股票的信号
        :param code: 股票代码
        :param hist_df: 历史K线
        :param dividend_data: 分红数据 {date: yield}
        :return: 信号列表
        """
        signals = []
        
        # 计算MA120
        hist_df['ma120'] = self.calculate_ma120(hist_df)
        
        # 追踪连续天数
        consecutive_days = 0
        last_signal_date = None
        
        for idx, row in hist_df.iterrows():
            date = row['日期']
            close = row['收盘']
            ma120 = row['ma120']
            
            # 跳过无效数据
            if pd.isna(ma120) or ma120 <= 0:
                consecutive_days = 0
                continue
            
            # 检查是否低于MA120
            is_below = close < ma120
            
            if is_below:
                consecutive_days += 1
                
                # 获取股息率（模拟数据）
                div_yield = dividend_data.get(date, 0) if dividend_data else 5.0
                
                # 只有股息率 >= 5% 才产生信号
                if div_yield >= DIVIDEND_YIELD_THRESHOLD:
                    # 计算信号级别
                    if consecutive_days >= SIGNAL_LEVEL_3_DAYS:
                        level = 3
                    elif consecutive_days >= SIGNAL_LEVEL_2_DAYS:
                        level = 2
                    else:
                        level = 1
                    
                    signal = {
                        'code': code,
                        'date': date,
                        'close': close,
                        'ma120': ma120,
                        'discount': round((close / ma120 - 1) * 100, 2),
                        'consecutive_days': consecutive_days,
                        'signal_level': level,
                        'dividend_yield': div_yield
                    }
                    
                    signals.append(signal)
                    last_signal_date = date
            else:
                # 不再低于MA120，重置
                consecutive_days = 0
        
        return signals
    
    def calculate_returns(
        self, 
        signal: Dict, 
        hist_df: pd.DataFrame,
        holding_days: List[int] = [5, 20, 60]
    ) -> Dict[int, float]:
        """
        计算信号后的收益率
        :param signal: 信号信息
        :param hist_df: 历史K线
        :param holding_days: 持有天数列表 [5, 20, 60]
        :return: {天数: 收益率}
        """
        returns = {}
        signal_date = signal['date']
        signal_price = signal['close']
        
        # 找到信号日期在DataFrame中的位置
        try:
            signal_idx = hist_df[hist_df['日期'] == signal_date].index[0]
        except (IndexError, KeyError):
            return returns
        
        for days in holding_days:
            target_idx = signal_idx + days
            if target_idx < len(hist_df):
                target_price = hist_df.iloc[target_idx]['收盘']
                ret = (target_price / signal_price - 1) * 100
                returns[days] = round(ret, 2)
        
        return returns
    
    def run_backtest(
        self, 
        codes: List[str],
        start_date: str = BACKTEST_START_DATE,
        end_date: str = BACKTEST_END_DATE,
        sample_size: int = 100
    ) -> Dict:
        """
        执行回测
        :param codes: 股票代码列表
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param sample_size: 采样数量（用于快速测试）
        :return: 回测结果
        """
        logger.info(f"开始回测: {start_date} ~ {end_date}")
        logger.info(f"股票数量: {len(codes)}")
        
        # 采样（如果需要）
        if sample_size and len(codes) > sample_size:
            import random
            codes = random.sample(codes, sample_size)
            logger.info(f"采样 {sample_size} 只股票进行回测")
        
        # 获取历史数据
        logger.info("正在获取历史数据...")
        hist_data = self.get_stock_hist_batch(codes, start_date, end_date)
        
        # 模拟信号
        logger.info("正在模拟信号...")
        all_signals = []
        
        for code, df in hist_data.items():
            signals = self.simulate_signal(code, df)
            
            # 计算后续收益
            for signal in signals:
                returns = self.calculate_returns(signal, df)
                signal['returns'] = returns
                all_signals.append(signal)
        
        # 统计分析
        stats = self._analyze_signals(all_signals)
        
        self.signal_records = all_signals
        self.results = {
            'start_date': start_date,
            'end_date': end_date,
            'total_stocks': len(hist_data),
            'total_signals': len(all_signals),
            'stats': stats
        }
        
        logger.info("回测完成!")
        self._print_summary()
        
        return self.results
    
    def _analyze_signals(self, signals: List[Dict]) -> Dict:
        """分析信号统计"""
        if not signals:
            return {}
        
        stats = {
            'total_count': len(signals),
            'by_level': defaultdict(int),
            'by_year': defaultdict(int),
            'by_discount_range': defaultdict(int),
            'avg_returns': {5: [], 20: [], 60: []},
            'win_rate': {5: [], 20: [], 60: []}
        }
        
        for s in signals:
            # 按级别统计
            stats['by_level'][s['signal_level']] += 1
            
            # 按年份统计
            year = s['date'][:4]
            stats['by_year'][year] += 1
            
            # 按折扣范围统计
            discount = s['discount']
            if discount >= -5:
                range_key = '0~-5%'
            elif discount >= -10:
                range_key = '-5%~-10%'
            elif discount >= -20:
                range_key = '-10%~-20%'
            else:
                range_key = '<-20%'
            stats['by_discount_range'][range_key] += 1
            
            # 收益统计
            for days, ret in s.get('returns', {}).items():
                if days in stats['avg_returns']:
                    stats['avg_returns'][days].append(ret)
                    stats['win_rate'][days].append(1 if ret > 0 else 0)
        
        # 计算平均收益和胜率
        for days in [5, 20, 60]:
            returns = stats['avg_returns'][days]
            wins = stats['win_rate'][days]
            if returns:
                stats[f'avg_return_{days}d'] = round(np.mean(returns), 2)
                stats[f'win_rate_{days}d'] = round(np.mean(wins) * 100, 1)
        
        return stats
    
    def _print_summary(self):
        """打印回测摘要"""
        stats = self.results.get('stats', {})
        
        print("\n" + "="*50)
        print("回测结果摘要")
        print("="*50)
        print(f"回测区间: {self.results['start_date']} ~ {self.results['end_date']}")
        print(f"测试股票: {self.results['total_stocks']} 只")
        print(f"信号总数: {self.results['total_signals']} 次")
        print()
        
        print("信号级别分布:")
        for level, count in sorted(stats.get('by_level', {}).items()):
            print(f"  {level}级信号: {count} 次")
        print()
        
        print("年度分布:")
        for year, count in sorted(stats.get('by_year', {}).items()):
            print(f"  {year}年: {count} 次")
        print()
        
        print("后续表现:")
        for days in [5, 20, 60]:
            avg_ret = stats.get(f'avg_return_{days}d', 'N/A')
            win_rate = stats.get(f'win_rate_{days}d', 'N/A')
            print(f"  {days}日后: 平均收益 {avg_ret}%, 胜率 {win_rate}%")
        
        print("="*50 + "\n")
    
    def export_results(self, output_file: str = "backtest_results.csv"):
        """导出结果到CSV"""
        if not self.signal_records:
            logger.warning("无信号记录可导出")
            return
        
        df = pd.DataFrame(self.signal_records)
        
        # 展开returns字典
        for days in [5, 20, 60]:
            df[f'return_{days}d'] = df['returns'].apply(lambda x: x.get(days, None))
        
        df = df.drop(columns=['returns'])
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        logger.info(f"结果已导出到: {output_file}")


# 测试代码
if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='股息率定投策略回测')
    parser.add_argument('--codes', nargs='+', help='股票代码列表')
    parser.add_argument('--start', default=BACKTEST_START_DATE, help='开始日期')
    parser.add_argument('--end', default=BACKTEST_END_DATE, help='结束日期')
    parser.add_argument('--sample', type=int, default=50, help='采样数量')
    parser.add_argument('--export', default='backtest_results.csv', help='导出文件')
    args = parser.parse_args()
    
    backtester = Backtester()
    
    # 如果没有指定股票代码，使用一些示例
    if not args.codes:
        args.codes = [
            '600000', '600016', '600028', '600030', '600036',
            '600519', '600887', '601318', '601398', '601939'
        ]
    
    result = backtester.run_backtest(
        codes=args.codes,
        start_date=args.start,
        end_date=args.end,
        sample_size=args.sample
    )
    
    # 导出结果
    backtester.export_results(args.export)
