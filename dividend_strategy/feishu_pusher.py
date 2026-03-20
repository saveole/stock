#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块5: 飞书推送
格式化信号并通过飞书推送
"""

import json
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional

from dividend_strategy.config import FEISHU_WEBHOOK_URL

logger = logging.getLogger(__name__)


class FeishuPusher:
    """飞书推送器"""
    
    def __init__(self, webhook_url: str = None):
        """
        初始化
        :param webhook_url: 飞书机器人Webhook地址
        """
        self.webhook_url = webhook_url or FEISHU_WEBHOOK_URL
        
        if not self.webhook_url:
            logger.warning("飞书Webhook未配置，推送功能将不可用")
    
    def format_message(self, signals: List[Dict], stats: Dict, market_status: str = "正常") -> str:
        """
        格式化消息
        :param signals: 信号列表
        :param stats: 统计信息
        :param market_status: 大盘状态
        :return: 格式化后的消息
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        lines = [
            f"📈 **股息率定投信号** - {today}",
            "",
            "📊 **今日概况**",
            f"- 新增信号：{stats.get('new_signals', 0)}只",
            f"- 总信号数：{stats.get('total_signals', 0)}只",
            f"- 大盘状态：{market_status}",
            ""
        ]
        
        # 按信号级别分组
        level_3 = [s for s in signals if s.get('signal_level') == 3]
        level_2 = [s for s in signals if s.get('signal_level') == 2]
        level_1 = [s for s in signals if s.get('signal_level') == 1]
        
        # 强信号
        if level_3:
            lines.append("🔥 **强信号（3级）**")
            for s in level_3:
                lines.append(self._format_stock_line(s))
            lines.append("")
        
        # 中度信号
        if level_2:
            lines.append("⚠️ **中度信号（2级）**")
            for s in level_2:
                lines.append(self._format_stock_line(s))
            lines.append("")
        
        # 轻度信号
        if level_1:
            lines.append("💡 **轻度信号（1级）**")
            for s in level_1:
                lines.append(self._format_stock_line(s))
            lines.append("")
        
        # 行业分布
        if stats.get('industry_distribution'):
            lines.append("📈 **行业分布**")
            for industry, count in stats['industry_distribution'].items():
                lines.append(f"- {industry}：{count}只")
            lines.append("")
        
        # 特殊提醒
        if stats.get('special_notes'):
            lines.append("⚠️ **特殊提醒**")
            for note in stats['special_notes']:
                lines.append(f"- {note}")
        
        return "\n".join(lines)
    
    def _format_stock_line(self, signal: Dict) -> str:
        """格式化单只股票信息"""
        code = signal.get('code', '')
        name = signal.get('name', '')
        price = signal.get('new_price', 0)
        ma120 = signal.get('ma120', 0)
        discount = signal.get('discount', 0)
        dividend_yield = signal.get('dividend_yield', 0)
        consecutive_days = signal.get('consecutive_days', 0)
        industry = signal.get('industry', '')
        
        return (
            f"代码: {code} | 名称: {name} | "
            f"价格: {price:.2f} | MA120: {ma120:.2f} | "
            f"折扣: {discount:.1f}% | 股息率: {dividend_yield:.1f}% | "
            f"连续天数: {consecutive_days}天 | 行业: {industry}"
        )
    
    def format_card_message(self, signals: List[Dict], stats: Dict, market_status: str = "正常") -> dict:
        """
        格式化为飞书卡片消息
        :param signals: 信号列表
        :param stats: 统计信息
        :param market_status: 大盘状态
        :return: 卡片消息结构
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 按级别分组
        level_3 = [s for s in signals if s.get('signal_level') == 3]
        level_2 = [s for s in signals if s.get('signal_level') == 2]
        level_1 = [s for s in signals if s.get('signal_level') == 1]
        
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"📈 股息率定投信号 - {today}"
                    },
                    "template": "blue"
                },
                "elements": [
                    # 今日概况
                    {
                        "tag": "div",
                        "fields": [
                            {"is_short": True, "text": {"tag": "lark_md", "content": f"**新增信号**\n{stats.get('new_signals', 0)}只"}},
                            {"is_short": True, "text": {"tag": "lark_md", "content": f"**总信号数**\n{stats.get('total_signals', 0)}只"}},
                            {"is_short": True, "text": {"tag": "lark_md", "content": f"**大盘状态**\n{market_status}"}},
                            {"is_short": True, "text": {"tag": "lark_md", "content": f"**3级信号**\n{len(level_3)}只"}},
                        ]
                    },
                    {"tag": "hr"}
                ]
            }
        }
        
        # 添加信号详情
        if level_3:
            card["card"]["elements"].append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "🔥 **强信号（3级）**"}
            })
            for s in level_3[:5]:  # 最多显示5个
                card["card"]["elements"].append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": self._format_stock_markdown(s)}
                })
        
        if level_2:
            card["card"]["elements"].append({"tag": "hr"})
            card["card"]["elements"].append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "⚠️ **中度信号（2级）**"}
            })
            for s in level_2[:3]:
                card["card"]["elements"].append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": self._format_stock_markdown(s)}
                })
        
        return card
    
    def _format_stock_markdown(self, signal: Dict) -> str:
        """格式化股票Markdown"""
        code = signal.get('code', '')
        name = signal.get('name', '')
        price = signal.get('new_price', 0)
        ma120 = signal.get('ma120', 0)
        discount = signal.get('discount', 0)
        dividend_yield = signal.get('dividend_yield', 0)
        consecutive_days = signal.get('consecutive_days', 0)
        
        return (
            f"**{name}** ({code})\n"
            f"价格: {price:.2f} | MA120: {ma120:.2f} | 折扣: {discount:.1f}%\n"
            f"股息率: {dividend_yield:.1f}% | 连续: {consecutive_days}天"
        )
    
    def push(self, signals: List[Dict], stats: Dict, market_status: str = "正常", use_card: bool = True) -> bool:
        """
        推送消息到飞书
        :param signals: 信号列表
        :param stats: 统计信息
        :param market_status: 大盘状态
        :param use_card: 是否使用卡片格式
        :return: 是否推送成功
        """
        if not self.webhook_url:
            logger.error("飞书Webhook未配置")
            return False
        
        if not signals:
            logger.info("无信号，跳过推送")
            return True
        
        try:
            if use_card:
                payload = self.format_card_message(signals, stats, market_status)
            else:
                text = self.format_message(signals, stats, market_status)
                payload = {
                    "msg_type": "text",
                    "content": {"text": text}
                }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('StatusCode') == 0 or result.get('code') == 0:
                    logger.info("飞书推送成功")
                    return True
                else:
                    logger.error(f"飞书推送失败: {result}")
            else:
                logger.error(f"飞书推送失败: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"飞书推送异常: {e}")
        
        return False


# 测试代码
if __name__ == "__main__":
    pusher = FeishuPusher()
    
    # 测试数据
    test_signals = [
        {
            'code': '600000', 'name': '浦发银行', 'new_price': 8.5,
            'ma120': 9.2, 'discount': -7.6, 'dividend_yield': 6.2,
            'consecutive_days': 5, 'signal_level': 3, 'industry': '银行'
        },
        {
            'code': '000002', 'name': '万科A', 'new_price': 15.2,
            'ma120': 16.5, 'discount': -7.9, 'dividend_yield': 7.5,
            'consecutive_days': 3, 'signal_level': 2, 'industry': '房地产'
        },
    ]
    
    test_stats = {
        'new_signals': 2,
        'total_signals': 10,
        'industry_distribution': {'银行': 5, '房地产': 3, '保险': 2}
    }
    
    # 格式化消息
    msg = pusher.format_message(test_signals, test_stats)
    print(msg)
