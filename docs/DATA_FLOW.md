# InStock 股票数据获取流程详解

本文档详细说明 InStock 系统如何获取股票数据。

---

## 一、数据来源

**主要数据源：东方财富网**

| 数据类型 | API 地址 | 说明 |
|---------|---------|------|
| A股实时行情 | `http://82.push2.eastmoney.com/api/qt/clist/get` | 全市场股票实时数据 |
| 历史K线 | `http://push2his.eastmoney.com/api/qt/stock/kline/get` | 日/周/月K线数据 |
| 分红配送 | `https://datacenter-web.eastmoney.com/api/data/v1/get` | 分红送配数据 |
| 资金流向 | 东方财富资金数据接口 | 主力/大单/中单/小单 |
| ETF数据 | 东方财富ETF接口 | ETF实时行情 |

---

## 二、数据采集架构

```
┌─────────────────────────────────────────────────────────────┐
│                    定时任务调度 (cron)                        │
│                  每天 9:00 自动执行                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              execute_daily_job.py (主调度器)                 │
│                                                             │
│  Step 1: init_job.py          → 创建数据库表                 │
│  Step 2: basic_data_daily_job.py → 股票实时行情              │
│  Step 3: selection_data_daily_job.py → 综合选股数据          │
│  Step 4: basic_data_other_daily_job.py → 其他基础数据        │
│  Step 5: basic_data_after_close_daily_job.py → 收盘后数据    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   core/crawling/ (爬虫层)                    │
│                                                             │
│  stock_hist_em.py    → 历史K线、实时行情                     │
│  stock_fhps_em.py    → 分红配送数据                          │
│  stock_fund_em.py    → 资金流向数据                          │
│  stock_dzjy_em.py    → 大宗交易数据                          │
│  stock_lhb_em.py     → 龙虎榜数据                            │
│  trade_date_hist.py  → 交易日历                              │
│  fund_etf_em.py      → ETF数据                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              eastmoney_fetcher.py (请求封装)                 │
│                                                             │
│  - Cookie 管理 (环境变量/文件/默认)                          │
│  - 代理支持                                                  │
│  - 重试机制 (3次)                                            │
│  - 连接池 (50个连接)                                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  MariaDB 数据库存储                          │
│                                                             │
│  cn_stock_spot      → 每日股票实时数据                       │
│  cn_stock_bonus     → 分红配送数据                           │
│  cn_stock_indicators → 技术指标数据                          │
│  cn_stock_fund_flow  → 资金流向数据                          │
│  cn_etf_spot        → ETF实时数据                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、核心采集脚本

### 1. 实时行情采集

**文件**: `instock/job/basic_data_daily_job.py`

```python
# 主要函数
save_nph_stock_spot_data(date)  # 股票实时行情
save_nph_etf_spot_data(date)    # ETF实时行情

# 数据流程
1. 调用 stock_zh_a_spot_em() 获取全市场数据
2. 过滤 A股代码 (600/000/300开头)
3. 过滤无效价格 (退市股)
4. 存入 cn_stock_spot 表
```

### 2. 历史K线获取

**文件**: `instock/core/crawling/stock_hist_em.py`

```python
# 主要函数
stock_zh_a_hist(symbol, period, start_date, end_date, adjust)

# 参数说明
symbol: 股票代码，如 "000001"
period: 周期 ("daily", "weekly", "monthly")
start_date: 开始日期，如 "20240101"
end_date: 结束日期，如 "20250101"
adjust: 复权方式 ("qfq"前复权, "hfq"后复权, ""不复权)

# 返回字段
日期、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、涨跌额、换手率
```

### 3. 分红数据获取

**文件**: `instock/core/crawling/stock_fhps_em.py`

```python
# 主要函数
stock_fhps_em(date="20231231")

# 参数说明
date: 报告期，如 "20231231"(年报), "20230930"(三季报)

# 返回字段
代码、名称、送转比例、现金分红比例、股息率、每股收益等
```

### 4. 其他数据采集

| 脚本 | 功能 | 数据表 |
|------|------|--------|
| `stock_fund_em.py` | 资金流向 | cn_stock_fund_flow |
| `stock_dzjy_em.py` | 大宗交易 | cn_stock_blocktrade |
| `stock_lhb_em.py` | 龙虎榜 | cn_stock_lhb |
| `fund_etf_em.py` | ETF数据 | cn_etf_spot |

---

## 四、缓存机制

### 缓存路径

```
/data/InStock/instock/cache/hist/{年月}/{日期}/{股票代码}{复权方式}.gzip.pickle
```

### 示例

```
/data/InStock/instock/cache/hist/202401/20240101/000001qfq.gzip.pickle
```

### 缓存优势

- 避免重复请求API
- 提高数据获取速度
- 减少被封风险

### 缓存读取逻辑

```python
# stockfetch.py 中的 stock_hist_cache() 函数
1. 检查缓存文件是否存在
2. 存在：直接读取 pickle 文件返回
3. 不存在：调用API获取，然后保存为 pickle 文件
```

---

## 五、定时任务配置

### Cron 配置

**文件**: `instock/bin/run_cron.sh`

```bash
#!/bin/sh
export PYTHONPATH=/data/InStock
/usr/sbin/cron -f
```

### 运行方式

```bash
# 运行完整作业（当天数据）
docker exec InStock python3 /data/InStock/instock/job/execute_daily_job.py

# 批量补数据（指定日期范围）
docker exec InStock python3 /data/InStock/instock/job/execute_daily_job.py 2024-01-01 2024-12-31

# 补充特定日期
docker exec InStock python3 /data/InStock/instock/job/execute_daily_job.py 2026-03-01,2026-03-02,2026-03-03

# 单独运行某个模块
docker exec InStock python3 /data/InStock/instock/job/basic_data_daily_job.py 2024-01-01 2024-12-31
```

### 可用作业脚本

| 脚本 | 说明 |
|------|------|
| `execute_daily_job.py` | 完整作业（推荐） |
| `init_job.py` | 创建数据库表 |
| `basic_data_daily_job.py` | 基础数据实时作业 |
| `basic_data_other_daily_job.py` | 基础数据非实时作业 |
| `basic_data_after_close_daily_job.py` | 收盘后数据作业 |
| `indicators_data_daily_job.py` | 指标数据作业 |
| `strategy_data_daily_job.py` | 策略数据作业 |
| `klinepattern_data_daily_job.py` | K线形态作业 |
| `backtest_data_daily_job.py` | 回测数据作业 |
| `selection_data_daily_job.py` | 综合选股作业 |

---

## 六、数据库表结构

### cn_stock_spot（每日股票数据）

| 字段 | 类型 | 说明 |
|------|------|------|
| date | DATE | 日期 |
| code | VARCHAR(6) | 股票代码 |
| name | VARCHAR(20) | 股票名称 |
| new_price | FLOAT | 最新价 |
| change_rate | FLOAT | 涨跌幅 |
| deal_amount | BIGINT | 成交额 |
| total_market_cap | BIGINT | 总市值 |
| industry | VARCHAR(20) | 所处行业 |
| listing_date | DATE | 上市时间 |
| pe | FLOAT | 市盈率静 |
| pe9 | FLOAT | 市盈率TTM |
| pbnewmrq | FLOAT | 市净率 |
| ... | ... | 更多字段 |

### cn_stock_bonus（分红配送）

| 字段 | 类型 | 说明 |
|------|------|------|
| date | DATE | 日期 |
| code | VARCHAR(6) | 股票代码 |
| name | VARCHAR(20) | 股票名称 |
| bonusaward_yield | FLOAT | 现金分红-股息率 |
| ex_dividend_date | DATE | 除权除息日 |
| ... | ... | 更多字段 |

### cn_stock_indicators（技术指标）

| 字段 | 类型 | 说明 |
|------|------|------|
| date | DATE | 日期 |
| code | VARCHAR(6) | 股票代码 |
| close | FLOAT | 收盘价 |
| macd | FLOAT | MACD指标 |
| kdjk | FLOAT | KDJ-K值 |
| boll | FLOAT | 布林线中轨 |
| rsi | FLOAT | RSI指标 |
| ... | ... | 更多字段 |

---

## 七、请求封装（eastmoney_fetcher.py）

### 功能特性

```python
class eastmoney_fetcher:
    """
    东方财富网数据获取器
    """
    
    # 1. Cookie管理
    - 优先级：环境变量 > 文件 > 默认Cookie
    - 支持动态更新
    
    # 2. 会话管理
    - 连接池大小：50
    - 重试策略：3次，指数退避
    - 超时设置：10秒
    
    # 3. 代理支持
    - 从 proxys 单例获取代理配置
    
    # 4. 请求方法
    make_request(url, params)      # GET请求
    make_post_request(url, data)   # POST请求
```

### 代理配置

**文件**: `instock/core/singleton_proxy.py`

```python
# 代理配置示例
proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
}
```

---

## 八、常见问题

### 1. 网络连接失败

```
错误: Connection aborted, RemoteDisconnected
```

**解决方案**:
- 检查网络连接
- 配置代理
- 更新Cookie

### 2. 数据缺失

```
数据库只有几天数据
```

**解决方案**:
```bash
# 补充历史数据
docker exec InStock python3 /data/InStock/instock/job/execute_daily_job.py 2024-01-01 2024-12-31
```

### 3. API限流

```
请求过于频繁被限制
```

**解决方案**:
- 系统已内置随机延迟（1-1.5秒）
- 使用缓存机制减少请求

---

## 九、相关文件索引

```
instock/
├── bin/
│   ├── run_cron.sh          # Cron启动脚本
│   └── run_job.sh           # 作业运行脚本
├── job/
│   ├── execute_daily_job.py # 主调度器
│   ├── init_job.py          # 数据库初始化
│   ├── basic_data_daily_job.py       # 基础数据
│   ├── basic_data_other_daily_job.py # 其他数据
│   └── ...                  # 更多作业脚本
├── core/
│   ├── crawling/
│   │   ├── stock_hist_em.py   # K线数据
│   │   ├── stock_fhps_em.py   # 分红数据
│   │   ├── stock_fund_em.py   # 资金流向
│   │   └── ...                # 更多爬虫
│   ├── eastmoney_fetcher.py   # 请求封装
│   ├── stockfetch.py          # 数据获取
│   └── singleton_stock.py     # 单例模式
└── cache/
    └── hist/                  # 历史数据缓存
```

---

## 十、参考资料

- [东方财富网数据接口](https://quote.eastmoney.com/)
- [InStock 原项目](https://github.com/myhhub/stock)
