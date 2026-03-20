# 股息率定投信号系统

基于股息率和MA120的A股定投信号系统。

## 功能

- 🔄 每日自动扫描A股全市场
- 📊 筛选TTM股息率 >= 5%的股票
- 📉 识别价格低于MA120的价值低估机会
- 🔔 三级信号分级机制
- 📱 飞书消息推送
- 📈 历史回测验证

## 快速开始

### 1. 安装依赖

```bash
cd dividend_strategy
pip install -r requirements.txt
```

### 2. 配置飞书Webhook

编辑 `config.py`，设置飞书机器人Webhook地址：

```python
FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

### 3. 执行扫描

```bash
# 执行一次扫描
python main.py --scan

# 启动定时任务（每天9:00执行）
python main.py --schedule

# 执行回测
python main.py --backtest --sample 50
```

## 模块说明

| 模块 | 文件 | 功能 |
|------|------|------|
| 股息率计算 | `dividend_calculator.py` | 计算TTM股息率 |
| MA120筛选 | `ma120_filter.py` | 筛选低于MA120的股票 |
| 过滤器 | `stock_filter.py` | 过滤ST/停牌/新股等 |
| 信号管理 | `signal_manager.py` | 信号分级和追踪 |
| 飞书推送 | `feishu_pusher.py` | 推送消息到飞书 |
| 定时任务 | `scheduler.py` | 每日扫描调度 |
| 回测系统 | `backtest.py` | 历史数据回测 |

## 信号分级

- **1级信号**：当天收盘价 < MA120（轻度，预警关注）
- **2级信号**：连续3天 < MA120（中度，趋势确认）
- **3级信号**：连续5天 < MA120（强信号，重点关注）

## 过滤规则

系统会自动过滤：
- ST、*ST股票
- 退市整理期股票
- 停牌股票
- 新股（上市不足1年）
- 市值 < 50亿
- 日成交额 < 1000万

## 配置参数

主要配置项（`config.py`）：

```python
# 股息率阈值
DIVIDEND_YIELD_THRESHOLD = 5.0

# MA周期
MA_PERIOD = 120

# 最小市值
MIN_MARKET_CAP = 50 * 100_000_000

# 推送时间
PUSH_HOUR = 9
PUSH_MINUTE = 0
```

## 回测示例

```bash
# 回测采样50只股票
python main.py --backtest --sample 50

# 回测指定股票
python main.py --backtest --codes 600000 601318 000002

# 指定日期范围
python main.py --backtest --start 2022-01-01 --end 2025-12-31
```

## 飞书消息示例

```
📈 股息率定投信号 - 2026-03-05

📊 今日概况
- 新增信号：3只
- 总信号数：15只
- 大盘状态：正常（+0.5%）

🔥 强信号（3级）
代码: 600000 | 名称: 浦发银行 | 价格: 8.50 | MA120: 9.20 | 折扣: -7.6% | 股息率: 6.2% | 连续天数: 5天 | 行业: 银行
```

## 注意事项

⚠️ **本系统是定投信号提醒工具，不是自动交易系统**

- 仅供投资参考，不构成投资建议
- 请结合自身风险承受能力做出决策
- 历史表现不代表未来收益

## License

MIT
