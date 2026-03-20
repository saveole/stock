#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟测试 - 使用模拟数据验证核心逻辑
"""

import sys
sys.path.insert(0, '/data/InStock')

import pandas as pd
import pymysql
import json
from datetime import datetime

print("=" * 60)
print("股息率定投信号系统 - 模拟测试")
print("=" * 60)

# 数据库连接
conn = pymysql.connect(host='InStockDbService', user='root', password='root', database='instockdb')

# 1. 获取符合条件的股票
print("\n[1] 从数据库筛选股票...")
sql = """
SELECT code, name, new_price, total_market_cap, deal_amount, industry
FROM cn_stock_spot 
WHERE date = (SELECT MAX(date) FROM cn_stock_spot)
AND new_price > 0 AND total_market_cap >= 5000000000
AND deal_amount >= 10000000 AND name NOT LIKE '%ST%'
LIMIT 20
"""
stocks = pd.read_sql(sql, conn)
print(f"✅ 筛选出 {len(stocks)} 只股票")

# 2. 模拟股息率数据
print("\n[2] 模拟股息率数据（实际需API获取）...")
mock_dividend = {
    '600000': 6.2, '601318': 5.8, '601398': 6.5, '601939': 5.5,
    '000001': 5.3, '000002': 7.5, '600016': 5.1, '601288': 6.0
}

# 3. 模拟MA120数据
print("[3] 模拟MA120数据...")
mock_ma120 = {
    '600000': {'ma120': 9.20, 'below': True},
    '601318': {'ma120': 48.50, 'below': True},
    '601398': {'ma120': 4.90, 'below': True},
    '000001': {'ma120': 11.50, 'below': True},
}

# 4. 生成信号
print("[4] 生成定投信号...")
signals = []
for code, div_yield in mock_dividend.items():
    if div_yield < 5.0:
        continue
    ma_info = mock_ma120.get(code)
    if not ma_info or not ma_info['below']:
        continue
    
    price_map = {'600000': 8.50, '601318': 45.30, '601398': 4.65, '000001': 10.80}
    price = price_map.get(code, 10.0)
    discount = (price / ma_info['ma120'] - 1) * 100
    
    signals.append({
        'code': code,
        'name': {'600000': '浦发银行', '601318': '中国平安', '601398': '工商银行', '000001': '平安银行'}.get(code, code),
        'price': price, 'ma120': ma_info['ma120'], 'discount': round(discount, 2),
        'dividend_yield': div_yield, 'consecutive_days': 5 if code in ['600000', '601318'] else 3
    })

# 5. 按级别分类
for s in signals:
    s['level'] = 3 if s['consecutive_days'] >= 5 else (2 if s['consecutive_days'] >= 3 else 1)

level_3 = [s for s in signals if s['level'] == 3]
level_2 = [s for s in signals if s['level'] == 2]

# 6. 输出报告
today = datetime.now().strftime("%Y-%m-%d")
print("\n" + "=" * 60)
print(f"📈 股息率定投信号 - {today}")
print("=" * 60)
print(f"\n📊 今日概况: {len(signals)}只信号 (3级:{len(level_3)} 2级:{len(level_2)})")

if level_3:
    print("\n🔥 强信号（3级）")
    for s in level_3:
        print(f"  {s['code']} {s['name']} 价格:{s['price']:.2f} 折扣:{s['discount']:.1f}% 股息率:{s['dividend_yield']:.1f}%")

if level_2:
    print("\n⚠️ 中度信号（2级）")
    for s in level_2:
        print(f"  {s['code']} {s['name']} 价格:{s['price']:.2f} 折扣:{s['discount']:.1f}% 股息率:{s['dividend_yield']:.1f}%")

# 7. 保存状态
state = {s['code']: {'level': s['level'], 'days': s['consecutive_days'], 'date': today} for s in signals}
with open('/data/InStock/dividend_strategy/signal_state.json', 'w') as f:
    json.dump(state, f, indent=2)
print("\n✅ 信号状态已保存")

print("\n" + "=" * 60)
print("✅ 模拟测试完成")
print("=" * 60)

conn.close()
