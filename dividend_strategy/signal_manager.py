#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块4: 信号分级管理
追踪股票连续低于MA120的天数，分级信号
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from dividend_strategy.config import (
    SIGNAL_LEVEL_1_DAYS,
    SIGNAL_LEVEL_2_DAYS,
    SIGNAL_LEVEL_3_DAYS
)

logger = logging.getLogger(__name__)


class SignalManager:
    """信号分级管理器"""
    
    def __init__(self, state_file: str = None):
        """
        初始化
        :param state_file: 状态文件路径
        """
        if state_file is None:
            self.state_file = os.path.join(
                os.path.dirname(__file__), 
                'signal_state.json'
            )
        else:
            self.state_file = state_file
        
        self.state = self._load_state()
    
    def _load_state(self) -> dict:
        """加载状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载状态文件失败: {e}")
        return {}
    
    def _save_state(self):
        """保存状态"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存状态文件失败: {e}")
    
    def calculate_signal_level(self, consecutive_days: int) -> int:
        """
        根据连续天数计算信号级别
        :param consecutive_days: 连续低于MA120的天数
        :return: 信号级别 (0, 1, 2, 3)
        """
        if consecutive_days < SIGNAL_LEVEL_1_DAYS:
            return 0  # 无信号
        elif consecutive_days < SIGNAL_LEVEL_2_DAYS:
            return 1  # 1级信号
        elif consecutive_days < SIGNAL_LEVEL_3_DAYS:
            return 2  # 2级信号
        else:
            return 3  # 3级信号
    
    def update_signal(self, code: str, is_below_ma120: bool, date: str = None) -> dict:
        """
        更新股票信号状态
        :param code: 股票代码
        :param is_below_ma120: 是否低于MA120
        :param date: 当前日期，默认今天
        :return: {
            'signal_level': int,
            'consecutive_days': int,
            'is_new_signal': bool,       # 是否新产生信号
            'is_level_up': bool,         # 是否信号升级
            'first_below_date': str      # 首次低于MA120的日期
        }
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        result = {
            'signal_level': 0,
            'consecutive_days': 0,
            'is_new_signal': False,
            'is_level_up': False,
            'first_below_date': None
        }
        
        # 获取之前的状态
        prev_state = self.state.get(code, {})
        prev_level = prev_state.get('signal_level', 0)
        prev_consecutive = prev_state.get('consecutive_days', 0)
        prev_date = prev_state.get('last_check_date', '')
        
        if is_below_ma120:
            # 当前低于MA120
            if prev_consecutive > 0:
                # 之前也低于，检查日期连续性
                prev_dt = datetime.strptime(prev_date, '%Y-%m-%d')
                curr_dt = datetime.strptime(date, '%Y-%m-%d')
                
                # 如果日期差不超过3天（考虑周末），则连续
                if (curr_dt - prev_dt).days <= 3:
                    consecutive_days = prev_consecutive + 1
                    first_below_date = prev_state.get('first_below_date', date)
                else:
                    # 不连续，重新开始
                    consecutive_days = 1
                    first_below_date = date
            else:
                # 之前不低于是新信号
                consecutive_days = 1
                first_below_date = date
                result['is_new_signal'] = True
            
            # 计算新级别
            new_level = self.calculate_signal_level(consecutive_days)
            
            # 检查是否升级
            if new_level > prev_level:
                result['is_level_up'] = True
            
            result['signal_level'] = new_level
            result['consecutive_days'] = consecutive_days
            result['first_below_date'] = first_below_date
            
            # 更新状态
            self.state[code] = {
                'consecutive_days': consecutive_days,
                'first_below_date': first_below_date,
                'last_check_date': date,
                'signal_level': new_level
            }
        else:
            # 当前不低于MA120，重置状态
            if code in self.state:
                del self.state[code]
        
        # 保存状态
        self._save_state()
        
        return result
    
    def get_active_signals(self, min_level: int = 1) -> list:
        """
        获取当前活跃的信号
        :param min_level: 最小信号级别
        :return: 信号列表
        """
        signals = []
        for code, state in self.state.items():
            level = state.get('signal_level', 0)
            if level >= min_level:
                signals.append({
                    'code': code,
                    **state
                })
        
        # 按信号级别和连续天数排序
        signals.sort(key=lambda x: (x['signal_level'], x['consecutive_days']), reverse=True)
        
        return signals
    
    def get_stats(self) -> dict:
        """
        获取信号统计
        :return: 统计信息
        """
        stats = {
            'total_signals': len(self.state),
            'level_1': 0,
            'level_2': 0,
            'level_3': 0
        }
        
        for state in self.state.values():
            level = state.get('signal_level', 0)
            if level == 1:
                stats['level_1'] += 1
            elif level == 2:
                stats['level_2'] += 1
            elif level == 3:
                stats['level_3'] += 1
        
        return stats
    
    def clear_old_signals(self, days: int = 30):
        """
        清理过期信号
        :param days: 超过多少天没更新的信号视为过期
        """
        today = datetime.now()
        to_remove = []
        
        for code, state in self.state.items():
            last_date = state.get('last_check_date', '')
            if last_date:
                last_dt = datetime.strptime(last_date, '%Y-%m-%d')
                if (today - last_dt).days > days:
                    to_remove.append(code)
        
        for code in to_remove:
            del self.state[code]
            logger.info(f"清理过期信号: {code}")
        
        if to_remove:
            self._save_state()


# 测试代码
if __name__ == "__main__":
    manager = SignalManager()
    
    # 模拟5天数据
    code = "600000"
    for i in range(5):
        date = f"2026-03-0{i+1}"
        result = manager.update_signal(code, True, date)
        print(f"Day {i+1}: level={result['signal_level']}, days={result['consecutive_days']}, new={result['is_new_signal']}, up={result['is_level_up']}")
    
    print(f"\n当前信号: {manager.get_active_signals()}")
    print(f"统计: {manager.get_stats()}")
