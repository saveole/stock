#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股息率定投信号系统 - 主入口

使用方法:
    # 执行一次扫描
    python main.py --scan
    
    # 启动定时任务
    python main.py --schedule
    
    # 执行回测
    python main.py --backtest --sample 50
    
    # 指定配置文件
    python main.py --scan --config config.yaml
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'instock'))

import argparse
import json
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'dividend_strategy.log'))
    ]
)
logger = logging.getLogger(__name__)


def run_scan(args):
    """执行扫描"""
    from dividend_strategy.scheduler import DailyScheduler
    
    scheduler = DailyScheduler()
    result = scheduler.run_once()
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"结果已保存到: {args.output}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    
    return result


def run_schedule(args):
    """启动定时任务"""
    from dividend_strategy.scheduler import DailyScheduler
    
    scheduler = DailyScheduler()
    logger.info("启动定时任务模式...")
    scheduler.start_scheduler()


def run_backtest(args):
    """执行回测"""
    from dividend_strategy.backtest import Backtester
    
    backtester = Backtester()
    
    # 获取股票代码列表
    codes = args.codes if args.codes else None
    
    # 如果没有指定代码，从当前市场获取
    if not codes:
        from instock.core.crawling.stock_hist_em import stock_zh_a_spot_em
        df = stock_zh_a_spot_em()
        if df is not None:
            codes = df['代码'].tolist()
            logger.info(f"从市场获取 {len(codes)} 只股票")
    
    if not codes:
        logger.error("无法获取股票代码列表")
        return
    
    result = backtester.run_backtest(
        codes=codes,
        start_date=args.start,
        end_date=args.end,
        sample_size=args.sample
    )
    
    # 导出结果
    if args.export:
        backtester.export_results(args.export)
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description='股息率定投信号系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 执行一次扫描
  python main.py --scan
  
  # 启动定时任务（每天9:00执行）
  python main.py --schedule
  
  # 执行回测（采样50只股票）
  python main.py --backtest --sample 50
  
  # 回测指定股票
  python main.py --backtest --codes 600000 601318 000002
        """
    )
    
    # 模式选择
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--scan', action='store_true', help='执行一次扫描')
    mode_group.add_argument('--schedule', action='store_true', help='启动定时任务')
    mode_group.add_argument('--backtest', action='store_true', help='执行回测')
    
    # 通用参数
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--output', '-o', type=str, help='输出文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    # 回测参数
    parser.add_argument('--codes', nargs='+', help='股票代码列表（用于回测）')
    parser.add_argument('--start', default='2021-01-01', help='回测开始日期')
    parser.add_argument('--end', default='2026-03-05', help='回测结束日期')
    parser.add_argument('--sample', type=int, default=50, help='回测采样数量')
    parser.add_argument('--export', default='backtest_results.csv', help='回测结果导出文件')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 执行对应模式
    try:
        if args.scan:
            run_scan(args)
        elif args.schedule:
            run_schedule(args)
        elif args.backtest:
            run_backtest(args)
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
