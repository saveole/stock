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

### 整体流程图

```mermaid
flowchart TB
    subgraph 定时任务
        CRON["⏰ Cron (每天9:00)"]
    end
    
    subgraph 主调度器
        EXEC["execute_daily_job.py"]
        INIT["init_job.py<br/>创建数据库表"]
        BASIC["basic_data_daily_job.py<br/>实时行情"]
        OTHER["basic_data_other_daily_job.py<br/>其他数据"]
        CLOSE["basic_data_after_close_daily_job.py<br/>收盘后数据"]
    end
    
    subgraph 爬虫层
        HIST["stock_hist_em.py<br/>历史K线"]
        FHPS["stock_fhps_em.py<br/>分红数据"]
        FUND["stock_fund_em.py<br/>资金流向"]
        DZJY["stock_dzjy_em.py<br/>大宗交易"]
        LHB["stock_lhb_em.py<br/>龙虎榜"]
        ETF["fund_etf_em.py<br/>ETF数据"]
    end
    
    subgraph 请求封装
        FETCHER["eastmoney_fetcher.py"]
        COOKIE["Cookie管理"]
        PROXY["代理支持"]
        RETRY["重试机制"]
    end
    
    subgraph 数据存储
        DB[("MariaDB")]
        SPOT["cn_stock_spot<br/>每日股票"]
        BONUS["cn_stock_bonus<br/>分红配送"]
        IND["cn_stock_indicators<br/>技术指标"]
        FLOW["cn_stock_fund_flow<br/>资金流向"]
        ETF_T["cn_etf_spot<br/>ETF数据"]
    end
    
    CRON --> EXEC
    EXEC --> INIT --> BASIC --> OTHER --> CLOSE
    BASIC --> HIST & FHPS & FUND & DZJY & LHB & ETF
    HIST & FHPS & FUND & DZJY & LHB & ETF --> FETCHER
    FETCHER --> COOKIE & PROXY & RETRY
    FETCHER --> DB
    DB --> SPOT & BONUS & IND & FLOW & ETF_T
```

### 数据流向图

```mermaid
flowchart LR
    subgraph 外部数据源
        EM["🌐 东方财富网 API"]
    end
    
    subgraph InStock系统
        FETCH["📡 数据获取"]
        CACHE["💾 缓存层"]
        PROCESS["⚙️ 数据处理"]
        STORE["🗄️ 数据存储"]
    end
    
    subgraph 应用层
        STRATEGY["📈 策略分析"]
        BACKTEST["🔄 回测系统"]
        PUSH["📱 信号推送"]
    end
    
    EM -->|"HTTP请求"| FETCH
    FETCH -->|"pickle缓存"| CACHE
    FETCH -->|"DataFrame"| PROCESS
    PROCESS -->|"SQL"| STORE
    STORE -->|"查询"| STRATEGY & BACKTEST & PUSH
```

---

## 三、核心采集脚本

### 1. 实时行情采集

**文件**: `instock/job/basic_data_daily_job.py`

```python
# 主要函数
save_nph_stock_spot_data(date)  # 股票实时行情
save_nph_etf_spot_data(date)    # ETF实时行情
```

```mermaid
flowchart TD
    A["开始"] --> B["调用 stock_zh_a_spot_em()"]
    B --> C["获取全市场数据"]
    C --> D{"过滤 A股代码?"}
    D -->|"600/000/300开头"| E["✅ 保留"]
    D -->|"其他"| F["❌ 过滤"]
    E --> G{"价格有效?"}
    G -->|"价格 > 0"| H["✅ 保留"]
    G -->|"价格 = NaN"| I["❌ 过滤(退市)"]
    H --> J["存入 cn_stock_spot 表"]
    J --> K["结束"]
```

### 2. 历史K线获取

**文件**: `instock/core/crawling/stock_hist_em.py`

```python
# 主要函数
stock_zh_a_hist(symbol, period, start_date, end_date, adjust)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `symbol` | str | 股票代码，如 "000001" |
| `period` | str | 周期：`daily`, `weekly`, `monthly` |
| `start_date` | str | 开始日期，如 "20240101" |
| `end_date` | str | 结束日期，如 "20250101" |
| `adjust` | str | 复权：`qfq`(前复权), `hfq`(后复权), `""`(不复权) |

**返回字段**：日期、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、涨跌额、换手率

### 3. 分红数据获取

**文件**: `instock/core/crawling/stock_fhps_em.py`

```python
# 主要函数
stock_fhps_em(date="20231231")

# 报告期说明
"20231231"  # 年报
"20230930"  # 三季报
"20230630"  # 半年报
"20230331"  # 一季报
```

---

## 四、缓存机制

### 缓存结构

```
/data/InStock/instock/cache/hist/
├── 202401/
│   ├── 20240101/
│   │   ├── 000001qfq.gzip.pickle
│   │   ├── 000002qfq.gzip.pickle
│   │   └── ...
│   └── 20240102/
│       └── ...
└── 202402/
    └── ...
```

### 缓存读取流程

```mermaid
flowchart TD
    A["请求历史K线"] --> B{"缓存文件存在?"}
    B -->|"是"| C["读取 pickle 文件"]
    B -->|"否"| D["调用 API 获取"]
    D --> E["保存为 pickle 文件"]
    C --> F["返回 DataFrame"]
    E --> F
```

### 缓存优势

| 优势 | 说明 |
|------|------|
| ⚡ 速度 | 本地读取比API快10倍+ |
| 🔒 稳定 | 避免API限流 |
| 💰 成本 | 减少网络请求 |

---

## 五、定时任务配置

### 作业执行流程

```mermaid
sequenceDiagram
    participant C as Cron
    participant E as execute_daily_job
    participant I as init_job
    participant B as basic_data_daily
    participant O as basic_data_other
    participant A as after_close
    participant DB as MariaDB
    
    C->>E: 每天9:00触发
    E->>I: Step1: 创建数据库表
    I->>DB: CREATE TABLE IF NOT EXISTS
    E->>B: Step2: 获取实时行情
    B->>DB: INSERT INTO cn_stock_spot
    E->>O: Step3: 获取其他数据
    O->>DB: INSERT INTO cn_stock_*
    E->>A: Step4: 收盘后数据
    A->>DB: INSERT INTO cn_stock_*
```

### 运行命令

```bash
# 完整作业（当天数据）
docker exec InStock python3 /data/InStock/instock/job/execute_daily_job.py

# 批量补数据（日期范围）
docker exec InStock python3 /data/InStock/instock/job/execute_daily_job.py 2024-01-01 2024-12-31

# 补充特定日期
docker exec InStock python3 /data/InStock/instock/job/execute_daily_job.py 2026-03-01,2026-03-02,2026-03-03
```

### 作业脚本列表

| 脚本 | 说明 | 依赖 |
|------|------|------|
| `execute_daily_job.py` | 🎯 **主调度器** | 所有作业 |
| `init_job.py` | 创建数据库表 | 无 |
| `basic_data_daily_job.py` | 实时行情 | 网络 |
| `basic_data_other_daily_job.py` | 其他基础数据 | 网络 |
| `basic_data_after_close_daily_job.py` | 收盘后数据 | 网络 |
| `indicators_data_daily_job.py` | 技术指标 | 历史数据 |
| `strategy_data_daily_job.py` | 策略数据 | 技术指标 |
| `klinepattern_data_daily_job.py` | K线形态 | 历史数据 |
| `backtest_data_daily_job.py` | 回测数据 | 策略数据 |
| `selection_data_daily_job.py` | 综合选股 | 所有数据 |

---

## 六、数据库表结构

### ER 图

```mermaid
erDiagram
    cn_stock_spot {
        date date PK
        code varchar PK
        name varchar
        new_price float
        change_rate float
        deal_amount bigint
        total_market_cap bigint
        industry varchar
        listing_date date
        pe float
        pe9 float
        pbnewmrq float
    }
    
    cn_stock_bonus {
        date date PK
        code varchar PK
        name varchar
        bonusaward_yield float
        ex_dividend_date date
    }
    
    cn_stock_indicators {
        date date PK
        code varchar PK
        close float
        macd float
        kdjk float
        boll float
        rsi float
    }
    
    cn_stock_fund_flow {
        date date PK
        code varchar PK
        fund_amount bigint
        fund_rate float
    }
    
    cn_stock_spot ||--o{ cn_stock_bonus : "has"
    cn_stock_spot ||--o{ cn_stock_indicators : "has"
    cn_stock_spot ||--o{ cn_stock_fund_flow : "has"
```

### 主要表字段说明

#### cn_stock_spot（每日股票数据）

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `date` | DATE | 日期 (PK) | 2024-01-15 |
| `code` | VARCHAR(6) | 股票代码 (PK) | 000001 |
| `name` | VARCHAR(20) | 股票名称 | 平安银行 |
| `new_price` | FLOAT | 最新价 | 12.50 |
| `change_rate` | FLOAT | 涨跌幅(%) | 2.35 |
| `deal_amount` | BIGINT | 成交额(元) | 1234567890 |
| `total_market_cap` | BIGINT | 总市值(元) | 250000000000 |
| `industry` | VARCHAR(20) | 所处行业 | 银行 |
| `listing_date` | DATE | 上市时间 | 1991-04-03 |
| `pe` | FLOAT | 市盈率(静) | 6.5 |
| `pe9` | FLOAT | 市盈率(TTM) | 6.2 |
| `pbnewmrq` | FLOAT | 市净率 | 0.65 |

---

## 七、请求封装

### eastmoney_fetcher 类结构

```mermaid
classDiagram
    class eastmoney_fetcher {
        -session: requests.Session
        -proxies: dict
        +__init__()
        +make_request(url, params, retry, timeout) Response
        +make_post_request(url, data, json) Response
        +update_cookie(new_cookie) void
        -_get_cookie() str
        -_create_session() Session
    }
    
    class CookieManager {
        +环境变量
        +文件配置
        +默认Cookie
    }
    
    class RetryStrategy {
        +total: 3
        +backoff_factor: 0.1
        +status_forcelist: 429,500,502,503,504
    }
    
    class ConnectionPool {
        +pool_connections: 50
        +pool_maxsize: 50
    }
    
    eastmoney_fetcher --> CookieManager
    eastmoney_fetcher --> RetryStrategy
    eastmoney_fetcher --> ConnectionPool
```

### Cookie 管理优先级

```mermaid
flowchart TD
    A["获取Cookie"] --> B{"环境变量<br/>EAST_MONEY_COOKIE?"}
    B -->|"是"| C["✅ 使用环境变量"]
    B -->|"否"| D{"文件存在?<br/>config/eastmoney_cookie.txt"}
    D -->|"是"| E["✅ 使用文件Cookie"]
    D -->|"否"| F["⚠️ 使用默认Cookie"]
```

### 代理配置

```python
# 文件: instock/core/singleton_proxy.py
proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
}
```

---

## 八、常见问题

### 问题诊断流程

```mermaid
flowchart TD
    A["数据采集失败"] --> B{"网络连接?"}
    B -->|"失败"| C["检查网络/代理"]
    B -->|"成功"| D{"API返回?"}
    D -->|"错误"| E["检查Cookie/限流"]
    D -->|"正常"| F{"数据解析?"}
    F -->|"失败"| G["检查API格式变化"]
    F ->|"成功"| H["✅ 完成"]
    C --> I["配置代理或换网络"]
    E --> J["更新Cookie"]
    G --> K["更新解析代码"]
    I & J & K --> A
```

### 问题1: 网络连接失败

```
错误: Connection aborted, RemoteDisconnected
```

**解决方案**:
```bash
# 1. 检查网络
ping baidu.com

# 2. 配置代理
# 编辑 instock/core/singleton_proxy.py
proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
}

# 3. 检查DNS
cat /etc/resolv.conf
```

### 问题2: 数据缺失

```
数据库只有几天数据
```

**解决方案**:
```bash
# 补充历史数据
docker exec InStock python3 /data/InStock/instock/job/execute_daily_job.py 2024-01-01 2024-12-31
```

### 问题3: API限流

```
请求过于频繁被限制
```

**解决方案**:
- 系统已内置随机延迟（1-1.5秒）
- 使用缓存机制减少请求
- 更新Cookie

---

## 九、文件索引

### 目录结构

```
instock/
├── bin/
│   ├── run_cron.sh          # 🔧 Cron启动脚本
│   └── run_job.sh           # 🔧 作业运行脚本
│
├── job/                     # 📋 定时作业
│   ├── execute_daily_job.py # 🎯 主调度器
│   ├── init_job.py          # 数据库初始化
│   ├── basic_data_daily_job.py
│   ├── basic_data_other_daily_job.py
│   ├── indicators_data_daily_job.py
│   ├── strategy_data_daily_job.py
│   └── ...
│
├── core/
│   ├── crawling/            # 🕷️ 爬虫模块
│   │   ├── stock_hist_em.py   # K线数据
│   │   ├── stock_fhps_em.py   # 分红数据
│   │   ├── stock_fund_em.py   # 资金流向
│   │   ├── stock_dzjy_em.py   # 大宗交易
│   │   ├── stock_lhb_em.py    # 龙虎榜
│   │   ├── fund_etf_em.py     # ETF数据
│   │   └── trade_date_hist.py # 交易日历
│   │
│   ├── eastmoney_fetcher.py # 🌐 请求封装
│   ├── stockfetch.py        # 📊 数据获取
│   ├── singleton_stock.py   # 🔄 单例模式
│   └── tablestructure.py    # 📝 表结构定义
│
├── cache/
│   └── hist/                # 💾 历史数据缓存
│
└── config/
    └── eastmoney_cookie.txt # 🔑 Cookie配置
```

---

## 十、快速参考

### 常用命令速查

| 任务 | 命令 |
|------|------|
| 运行当天采集 | `docker exec InStock python3 /data/InStock/instock/job/execute_daily_job.py` |
| 补历史数据 | `docker exec InStock python3 .../execute_daily_job.py 2024-01-01 2024-12-31` |
| 查看数据库 | `docker exec InStockDbService mariadb -uroot -proot instockdb -e "SELECT * FROM cn_stock_spot LIMIT 5;"` |
| 查看日志 | `docker exec InStock cat /data/InStock/instock/log/stock_execute_job.log` |

### API 端点速查

| 数据 | 端点 |
|------|------|
| 实时行情 | `http://82.push2.eastmoney.com/api/qt/clist/get` |
| 历史K线 | `http://push2his.eastmoney.com/api/qt/stock/kline/get` |
| 分红数据 | `https://datacenter-web.eastmoney.com/api/data/v1/get` |

---

## 十一、参考资料

- [东方财富网数据接口](https://quote.eastmoney.com/)
- [InStock 原项目](https://github.com/myhhub/stock)
- [Mermaid 流程图语法](https://mermaid.js.org/)
