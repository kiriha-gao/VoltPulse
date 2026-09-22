# VoltPulse V1 项目实施规格书

## 0. 项目定义

项目名称：

**VoltPulse（电脉）**

中文名称：

**中国电力现货市场与新型电力系统运行分析平台**

英文名称：

**VoltPulse — China Power Spot Market & Battery Storage Analytics Platform**

项目定位：

> 一个持续采集公开电力市场数据、自动完成数据清洗与质量检测、分析现货电价特征，并通过储能优化模型评估市场套利价值和系统调节价值的开源自动化研究平台。

本项目不是商业交易系统，不承担真实交易决策，不追求毫秒级实时性。

V1 核心目标只有四个：

1. 真实数据能够持续进入系统；
2. 储能优化模型能够稳定运行；
3. 每天能够自动生成新的分析结果；
4. 有一个任何人通过手机链接即可访问的 Dashboard。

---

# 1. 项目最高原则

整个 AI 开发流程必须遵循以下原则。

## 1.1 可运行优先于复杂

禁止为了追求高级技术而破坏稳定性。

优先级：

```text
能跑
>
数据可信
>
模型正确
>
自动更新
>
页面好看
>
复杂算法
```

任何高级功能如果导致主流程不稳定，立即删除或降级。

---

## 1.2 一个省做深，不追求多省

V1 只要求：

```text
Primary Market:
1 个省级现货市场

Secondary Market:
最多增加 1 个省作为对比
```

不要一开始支持全国。

系统架构需要支持未来增加省份，但 V1 不要求实现。

---

## 1.3 真实数据和模拟数据必须严格区分

所有数据必须带：

```text
source
source_url
market
date
retrieved_at
data_type
is_simulated
schema_version
```

网页中不得把模拟数据伪装成真实数据。

如果真实数据获取失败：

```text
显示 DATA UNAVAILABLE
```

而不是自动制造一份假数据。

开发环境允许使用 fixture / sample data，但必须明确标记。

---

## 1.4 不绕过访问限制

数据采集模块不得：

* 绕过登录；
* 绕过验证码；
* 破解接口；
* 绕过付费墙；
* 高频请求影响网站；
* 使用来源不明的数据。

只使用：

* 官方公开网页；
* 官方公开文件；
* 官方公开 API；
* 合法公开数据源。

如果某个站点无法稳定自动采集，应设计手动上传或备用数据适配器，而不是使用高风险方案。

---

# 2. V1 最终用户看到什么

最终 Dashboard 首页必须回答五个问题：

```text
1. 今天电价怎么样？
2. 有没有出现负电价？
3. 今天峰谷价差是多少？
4. 如果有一座 100MW / 200MWh 储能，理论上应该怎么充放？
5. 过去 30 天储能套利环境怎么样？
```

首页建议呈现：

```text
VoltPulse
China Power Spot Market Analytics

Market: XXXXX
Date: YYYY-MM-DD

────────────────────────

平均现货价格
xxx RMB/MWh

最高价格
xxx RMB/MWh

最低价格
xxx RMB/MWh

峰谷价差
xxx RMB/MWh

负电价时段
x periods

────────────────────────

[24h Spot Price Chart]

────────────────────────

100MW / 200MWh BESS

Gross Profit
¥ xxx,xxx

Degradation Cost
¥ xx,xxx

Net Profit
¥ xxx,xxx

Equivalent Cycles
x.xx

────────────────────────

[Price + Charge/Discharge + SOC Chart]

────────────────────────

30-Day Storage Profit

[Historical PnL Chart]
```

---

# 3. 总体技术架构

采用模块化单体架构。

不要微服务。

建议技术栈：

```text
Language:
Python 3.11+

Data:
Pandas
Polars 可选

Storage:
Parquet + SQLite

Optimization:
scipy.optimize / PuLP
优先使用简单可靠 LP Solver

Visualization:
Plotly

Dashboard:
Streamlit
或
静态 HTML + Plotly

Automation:
GitHub Actions

Hosting:
GitHub Pages
或 Streamlit Community Cloud

Tests:
pytest

Formatting:
ruff
black 可选

Configuration:
YAML

Documentation:
Markdown
```

原则：

```text
少依赖
可本地运行
可 GitHub Actions 运行
无商业 API 强依赖
```

---

# 4. 推荐目录结构

```text
voltpulse/
│
├── README.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── .env.example
│
├── config/
│   ├── markets.yaml
│   ├── storage.yaml
│   └── app.yaml
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── features/
│   ├── results/
│   └── metadata/
│
├── src/
│   └── voltpulse/
│       ├── __init__.py
│       │
│       ├── ingestion/
│       │   ├── base.py
│       │   ├── market_x.py
│       │   ├── downloader.py
│       │   └── validators.py
│       │
│       ├── processing/
│       │   ├── cleaning.py
│       │   ├── normalization.py
│       │   └── quality.py
│       │
│       ├── storage/
│       │   ├── database.py
│       │   └── schemas.py
│       │
│       ├── analytics/
│       │   ├── price_metrics.py
│       │   ├── negative_price.py
│       │   ├── volatility.py
│       │   └── grid_metrics.py
│       │
│       ├── optimization/
│       │   ├── bess_model.py
│       │   ├── benchmark.py
│       │   └── degradation.py
│       │
│       ├── backtest/
│       │   ├── engine.py
│       │   └── metrics.py
│       │
│       ├── reporting/
│       │   ├── daily_report.py
│       │   └── summary.py
│       │
│       └── utils/
│           ├── logging.py
│           └── dates.py
│
├── app/
│   ├── app.py
│   ├── pages/
│   └── components/
│
├── scripts/
│   ├── update_data.py
│   ├── run_analysis.py
│   ├── run_backtest.py
│   ├── build_report.py
│   └── pipeline.py
│
├── tests/
│   ├── test_ingestion.py
│   ├── test_cleaning.py
│   ├── test_bess_model.py
│   ├── test_metrics.py
│   └── fixtures/
│
├── reports/
│   ├── daily/
│   └── research/
│
├── docs/
│   ├── architecture.md
│   ├── methodology.md
│   ├── data_sources.md
│   └── project_brief.md
│
└── .github/
    └── workflows/
        ├── daily.yml
        └── test.yml
```

---

# 5. 模块 M00：项目骨架

优先级：

**P0 / 必须**

目标：

创建一个可以安装、运行、测试的 Python 项目。

必须实现：

```text
pip install -e .
```

能够成功安装。

必须支持：

```text
python scripts/pipeline.py
```

运行完整 pipeline。

配置不得硬编码进业务代码。

例如：

```yaml
market:
  name: shandong
  timezone: Asia/Shanghai

storage:
  power_mw: 100
  energy_mwh: 200
  round_trip_efficiency: 0.85
  soc_min: 0.1
  soc_max: 0.9
```

验收：

```text
pytest
```

可以正常执行。

---

# 6. 模块 M01：数据源适配层

优先级：

**P0**

这是整个项目最重要的模块之一。

必须创建统一接口：

```python
class MarketDataSource:
    def fetch(self, date):
        ...

    def parse(self, raw):
        ...

    def validate(self, df):
        ...

    def normalize(self, df):
        ...
```

不同市场的数据获取逻辑必须封装在独立 Adapter。

例如：

```text
ShandongAdapter
ShanxiAdapter
```

上层业务代码不得知道网页结构。

---

## 6.1 标准电价 Schema

所有市场最后必须转换成：

```text
market
date
timestamp
interval
price_type
price_rmb_mwh
source
source_url
retrieved_at
is_simulated
schema_version
```

price_type：

```text
day_ahead
real_time
```

如果只有日前价格，也允许：

```text
day_ahead
```

V1 不要求必须同时存在 DA 和 RT。

---

## 6.2 原始数据永久保留

原始数据不得被覆盖。

推荐：

```text
data/raw/{market}/{YYYY}/{MM}/{YYYY-MM-DD}/
```

保存：

```text
original.xlsx
original.csv
original.json
metadata.json
```

metadata 至少包括：

```json
{
  "source": "",
  "source_url": "",
  "retrieved_at": "",
  "sha256": "",
  "status": ""
}
```

这样未来数据源发生变化，也能追溯。

---

# 7. 模块 M02：数据质量系统

优先级：

**P0**

不要只做数据采集。

每批数据进入系统之前必须检查。

检查内容：

```text
row_count
missing_values
duplicate_timestamp
timestamp_continuity
invalid_price
extreme_price
schema_mismatch
timezone
```

输出：

```text
data/metadata/quality/YYYY-MM-DD.json
```

例如：

```json
{
  "status": "PASS",
  "rows": 96,
  "missing": 0,
  "duplicates": 0,
  "continuity": 1.0
}
```

如果检测失败：

```text
不得自动覆盖上一批正确数据。
```

Pipeline 应返回 non-zero exit code。

---

# 8. 模块 M03：数据库与历史资产

优先级：

**P0**

建议采用：

```text
Raw:
原始文件

Processed:
Parquet

Index / metadata:
SQLite
```

不需要 PostgreSQL。

历史价格数据建议：

```text
data/processed/spot_prices.parquet
```

每次更新必须：

```text
append
deduplicate
sort
validate
```

唯一键：

```text
market
timestamp
price_type
```

---

# 9. 模块 M04：基础电价分析

优先级：

**P0**

每天计算：

```text
mean_price
median_price
max_price
min_price
peak_valley_spread
std_price
negative_price_count
negative_price_ratio
low_price_duration
high_price_duration
```

推荐增加：

```text
P05
P25
P75
P95
```

输出：

```text
data/results/daily_metrics.parquet
```

Dashboard 首页直接读取这些结果，不要每次前端重新计算。

---

# 10. 模块 M05：负电价分析

优先级：

**P0**

计算：

```text
负电价次数
连续负电价最长时长
最低负电价
负电价发生时间分布
过去 30 天负电价天数
```

如果没有负电价：

```text
Negative price periods: 0
```

不要为了展示效果制造所谓“预警”。

---

# 11. 模块 M06：储能优化模型

优先级：

**P0 / 核心模块**

默认储能参数：

```text
Power:
100 MW

Energy:
200 MWh

Duration:
2 h

SOC initial:
50%

SOC min:
10%

SOC max:
90%

Round-trip efficiency:
85%
```

建议拆分：

```text
charge_efficiency
discharge_efficiency
```

满足：

```text
η_charge × η_discharge ≈ 0.85
```

---

## 11.1 基础优化问题

目标函数：

最大化：

```text
Energy Revenue
-
Charging Cost
-
Battery Degradation Cost
```

数学表达：

```text
max Σ[
price(t) × discharge(t)
-
price(t) × charge(t)
-
degradation_cost(t)
]
```

SOC：

```text
SOC(t+1)
=
SOC(t)
+
η_charge × charge(t) × Δt
-
discharge(t) × Δt / η_discharge
```

约束：

```text
0 <= charge(t) <= Pmax

0 <= discharge(t) <= Pmax

SOCmin <= SOC(t) <= SOCmax
```

终端 SOC 默认：

```text
SOC_final = SOC_initial
```

防止模型在最后一时段把电池彻底放空，从而高估利润。

---

## 11.2 充放同时发生

模型不得因为 LP 缺陷出现大量：

```text
charge > 0
AND
discharge > 0
```

如果出现，需要：

方案 A：

通过效率、成本使同时充放在经济上无意义。

如果仍出现异常：

方案 B：

升级 MILP，引入 binary state。

但：

```text
优先保持 LP。
```

除非确有必要，不使用 MILP。

---

# 12. 模块 M07：电池衰减模型

优先级：

**P1**

V1 不需要复杂电化学模型。

采用简单 Throughput-based degradation。

例如：

```text
degradation cost
=
energy throughput
× degradation_cost_per_mwh
```

配置：

```yaml
degradation_cost_rmb_per_mwh: 30
```

必须在文档说明：

> 该模型用于策略比较，不代表具体电芯厂商实际寿命模型。

同时计算：

```text
Equivalent Full Cycles
```

近似：

```text
EFC
=
total_discharge_energy
/
usable_energy_capacity
```

---

# 13. 模块 M08：Benchmark 策略

优先级：

**P0**

至少实现两个策略。

### Strategy 1

Perfect Foresight Optimal Dispatch

使用当天真实完整价格序列。

明确标记：

```text
Ex-post theoretical optimum
```

不得描述成可直接执行的真实交易策略。

### Strategy 2

Fixed Peak-Valley Strategy

使用固定时段：

```text
low-price charging window
high-price discharge window
```

具体时段由 config 控制。

---

# 14. 模块 M09：回测系统

优先级：

**P0**

必须支持：

```text
start_date
end_date
market
strategy
storage_config
```

逐日运行模型。

输出：

```text
date
strategy
gross_profit
charging_cost
degradation_cost
net_profit
charge_energy
discharge_energy
efc
max_soc
min_soc
```

生成：

```text
Daily PnL
Cumulative PnL
30D Moving Average
Profit per MWh
Profit per Cycle
```

不要在 V1 使用 IRR。

---

# 15. 模块 M10：Grid Insight

优先级：

**P1**

这是国网方向的重要增强模块。

如果能够获得可靠公开数据，则接入：

```text
load
wind
solar
renewable generation
```

计算：

```text
net_load
=
load
-
wind
-
solar
```

分析：

```text
spot price vs load
spot price vs net load
spot price vs renewable generation
```

如果数据粒度不同：

允许 resample。

必须记录：

```text
original frequency
resampled frequency
```

不得虚构新能源出力数据。

如果无法稳定获取真实数据：

**整个 Grid Insight 模块自动隐藏。**

不要阻塞 V1 发布。

---

# 16. 模块 M11：Storage Grid Value

优先级：

**P1**

如果存在 load / net load 数据，增加：

```text
Without Storage
vs
With Storage
```

计算：

```text
peak load
minimum load
peak-valley difference
maximum ramp
net-load variance
```

形成：

```text
Storage Market Value

+

Storage Grid Value
```

注意：

不要声称储能真实改变了整个省级电网负荷。

因为模拟的 100MW 储能只是模型场景。

网页中必须写：

```text
Illustrative 100 MW / 200 MWh BESS simulation
```

---

# 17. 模块 M12：Trading Lab

优先级：

**P2**

这是电力交易求职增强模块。

不要影响国网版主流程。

如果同时具有：

```text
Day-ahead Price
Real-time Price
```

计算：

```text
Spread
=
RT
-
DA
```

分析：

```text
mean spread
median spread
spread volatility
positive spread frequency
negative spread frequency
hourly spread distribution
```

Dashboard 增加：

```text
Trading Lab
```

页面。

---

# 18. 模块 M13：预测模块

优先级：

**P3 / 非必须**

除非所有 P0、P1 已稳定，否则不要开发。

如果开发：

第一版只使用：

```text
Naive
Linear Regression
LightGBM / XGBoost
```

禁止直接做：

```text
Transformer
LSTM
复杂深度学习
```

必须严格按照时间划分训练集、验证集、测试集。

不得 random split。

评估：

```text
MAE
RMSE
Directional Accuracy
```

最重要的是增加：

```text
Forecast-driven Storage Strategy
```

然后与：

```text
Fixed
Forecast
Perfect Foresight
```

比较。

---

# 19. 模块 M14：策略评价

优先级：

**P2**

交易版可增加：

```text
Net PnL
Daily PnL Volatility
Positive Day Ratio
Worst Day
Maximum Drawdown
Profit per Cycle
```

定义：

```text
Capture Ratio
=
Forecast Strategy Profit
/
Perfect Foresight Profit
```

必须注明：

Perfect Foresight 是理论上限参考。

---

# 20. Dashboard 页面结构

V1 控制在 4–5 个页面。

## Page 1：Overview

展示：

```text
Latest Date

Average Price
Maximum Price
Minimum Price
Peak-Valley Spread
Negative Price Periods

Spot Price Chart

BESS Daily Net Profit
```

这是手机展示核心页面。

---

## Page 2：Market

展示：

```text
24h Price Curve
Historical Price Distribution
Hourly Heatmap
Negative Price Statistics
Peak-Valley Spread Trend
```

---

## Page 3：Storage

展示：

```text
Price
Charge
Discharge
SOC
```

推荐一个 Plotly 图中：

上半：

```text
Price
```

下半：

```text
Charge / Discharge / SOC
```

同时展示：

```text
Gross Revenue
Charging Cost
Degradation Cost
Net Profit
EFC
```

---

## Page 4：Backtest

展示：

```text
Daily Profit
Cumulative Profit
30-Day Average
Profit Distribution
```

策略比较：

```text
Fixed
Perfect Foresight
```

---

## Page 5：Grid / Trading

根据数据可用性动态出现。

如果没有真实数据：

不要出现空页面。

---

# 21. 手机端设计要求

这是重点。

必须测试：

```text
375 px width
390 px width
430 px width
```

要求：

```text
无横向滚动
指标卡自动换行
图表可以触控
字体足够大
首页 10 秒内能理解项目
```

不要：

```text
大量代码
大量技术术语
超宽表格
```

---

# 22. UI 风格

目标：

```text
研究平台
能源分析
专业
克制
```

不要：

```text
赛博朋克
霓虹
过量渐变
花哨动画
金融诈骗风格
```

首页重点突出：

```text
数据
趋势
模型结果
```

---

# 23. GitHub Actions 自动化

优先级：

**P0**

建立：

```text
.github/workflows/daily.yml
```

流程：

```text
Checkout

↓

Install

↓

Fetch Latest Data

↓

Validate Data

↓

Update Database

↓

Run Analytics

↓

Run Storage Model

↓

Update Backtest

↓

Build Dashboard Data

↓

Run Tests

↓

Commit Data/Results

↓

Deploy
```

如果获取数据失败：

```text
workflow FAILED
```

不要伪造成功。

---

# 24. 自动提交策略

避免每天 commit 大量原始二进制文件。

推荐提交：

```text
processed datasets
results
metadata
dashboard assets
```

大型 raw 文件视情况：

```text
GitHub Release
或
压缩保存
或
定期归档
```

不要让仓库无限膨胀。

---

# 25. Status 文件

每次 pipeline 生成：

```text
data/results/status.json
```

例如：

```json
{
  "pipeline": "healthy",
  "last_successful_update": "2026-10-15T08:10:00+08:00",
  "market": "xxx",
  "latest_market_date": "2026-10-14",
  "data_quality": 1.0,
  "days_tracked": 37
}
```

Dashboard 和 README 可以读取它。

---

# 26. README 结构

README 不要写成长论文。

顶部：

```text
VoltPulse

China Power Spot Market
&
Battery Storage Analytics
```

然后：

```text
Live Dashboard

Pipeline Status

Latest Data

Tracked Days
```

再展示一张最漂亮的 Dashboard 截图。

随后：

```text
What is VoltPulse?

Architecture

Data Sources

Storage Model

Example Results

Methodology

Limitations

How to Run

Roadmap
```

---

# 27. Methodology 文档

必须单独建立：

```text
docs/methodology.md
```

需要解释：

```text
数据处理
电价指标
储能模型
SOC 方程
效率
衰减模型
Benchmark
Perfect Foresight
回测
局限性
```

目标：

让面试官能够验证模型逻辑。

---

# 28. Data Sources 文档

建立：

```text
docs/data_sources.md
```

对每个数据集记录：

```text
Dataset Name
Provider
URL
Data Type
Frequency
Coverage
Access Method
Update Frequency
License / Public Availability
Known Limitations
```

---

# 29. 测试模块

优先级：

**P0**

必须测试：

## Data

```text
missing timestamp
duplicate timestamp
empty dataframe
invalid price
```

## Storage Model

至少测试以下人工场景：

### Case A

所有价格完全相同。

理论：

套利收益应接近 0 或负。

### Case B

前半天价格 0，后半天 1000。

理论：

模型应低价充电，高价放电。

### Case C

全部负价格。

验证模型行为合理。

### Case D

极端正负价格。

验证 SOC / Power constraint 永远不被突破。

---

# 30. 模型 sanity check

每次运行后必须检查：

```text
SOC >= SOCmin

SOC <= SOCmax

charge <= Pmax

discharge <= Pmax

energy conservation approximately valid

final SOC constraint satisfied
```

如果违反：

```text
模型结果不得发布。
```

---

# 31. Logging

所有 pipeline 使用统一 logging。

输出：

```text
logs/
```

每一步记录：

```text
START
SUCCESS
FAILED
duration
rows
date
```

不要用大量 print。

---

# 32. Error Handling

数据源失败时：

```text
retry 3 times
```

采用：

```text
exponential backoff
```

仍失败：

```text
保存错误
停止当日数据更新
保持历史数据库不变
```

Dashboard 显示：

```text
Latest available data:
YYYY-MM-DD
```

而不是报错白屏。

---

# 33. 配置驱动

以下全部不得硬编码：

```text
market
battery power
battery energy
efficiency
SOC range
degradation cost
benchmark periods
data paths
```

全部从：

```text
config/
```

读取。

---

# 34. 性能要求

项目不是大数据平台。

目标：

普通 GitHub Actions Runner 能运行。

建议：

```text
Daily Pipeline:
< 10 min

Dashboard load:
< 5 sec

Storage optimization:
< 5 sec/day
```

如果模型明显超出：

优先简化模型。

---

# 35. AI 开发工作流建议

不要让一个 Agent 从头到尾全部写。

建议分角色。

## Agent A：Architect

负责：

```text
项目结构
接口
Schema
Config
Dependency
```

不写复杂业务代码。

---

## Agent B：Data Engineer

负责：

```text
数据源
ETL
Data Quality
Parquet
SQLite
```

---

## Agent C：Optimization Engineer

负责：

```text
BESS model
SOC
Efficiency
Degradation
Benchmark
Backtest
```

---

## Agent D：Frontend / Dashboard

负责：

```text
Streamlit
Plotly
Mobile layout
Metrics
Charts
```

---

## Agent E：DevOps

负责：

```text
GitHub Actions
Deployment
Logs
Failure Handling
```

---

## Agent F：Reviewer

不得新增功能。

只负责：

```text
运行 pytest
运行 pipeline
检查 Schema
检查模型约束
检查页面
检查 README
检查假数据
找 bug
```

---

# 36. Agent 依赖顺序

严格按照：

```text
M00
↓
M01
↓
M02
↓
M03
↓
M04
↓
M06
↓
M08
↓
M09
↓
Dashboard
↓
GitHub Actions
↓
Reviewer
```

这些完成后，才做：

```text
M05
M07
M10
M11
M12
```

预测：

```text
M13
```

最后再考虑。

---

# 37. 每个 Agent 的完成条件

Agent 不允许只说：

```text
Done
```

必须提交：

```text
Changed Files

Why

How to Run

Tests

Known Issues

Next Dependency
```

并实际运行：

```text
pytest
```

和相关脚本。

---

# 38. 禁止 AI 做的事情

明确禁止：

```text
为了页面漂亮制造随机真实感数据

虚构数据来源

虚构 API

虚构官方接口

虚构历史数据

把模拟结果说成真实收益

把 Perfect Foresight 说成真实策略

使用 IRR 但没有 CAPEX/OPEX/Cash Flow

用大量复杂框架增加维护成本

为了显得高级引入 Kafka / Spark / Kubernetes

无必要引入 Docker Compose 多服务架构

未经测试直接提交大量代码

偷偷 catch Exception 然后继续标记成功
```

---

# 39. V1 暂时不要做

以下全部进入 Backlog：

```text
Transformer
LSTM
强化学习
多智能体
复杂 AI Agent
全国所有省
辅助服务联合出清
容量市场完整建模
真实自动交易
实时 websocket
分钟级在线预测
云数据库
用户注册
账号系统
付费系统
```

这些在初版中不做展开。

---

# 40. 国网展示版本

国网方向首页重点：

```text
Power System View
```

强调：

```text
现货价格
负荷
新能源
净负荷
新能源消纳
储能调节
削峰填谷
爬坡
```

储能盈利：

放在第二层。

推荐描述：

> 基于公开电力市场数据构建自动化分析平台，研究现货价格与系统供需关系，并建立储能优化调度模型评估其市场价值和电网调节价值。

---

# 41. 电力交易展示版本

交易方向重点：

```text
Market View
```

强调：

```text
DA
RT
Spread
Negative Price
Volatility
Strategy
Backtest
PnL
Risk
```

推荐描述：

> 构建电力现货市场自动化数据与回测框架，研究日前/实时价格特征及储能交易策略，并比较固定策略与理论最优策略的收益差异。

未来加入预测后：

```text
Forecast Strategy
vs
Perfect Foresight
```

---

# 42. 技术要点与答辩解析

项目整理核心要点文档：

```text
docs/project_brief.md
```

自动整理以下问题：

```text
1. 项目解决什么问题？
2. 数据从哪里来？
3. Pipeline 怎么运行？
4. 为什么用 Parquet？
5. 为什么使用 LP？
6. SOC 方程是什么？
7. 为什么要限制 terminal SOC？
8. 为什么 Perfect Foresight 不是实际交易策略？
9. 为什么要算 degradation？
10. 出现负电价意味着什么？
11. 固定策略和最优策略区别？
12. 模型最大的局限性是什么？
13. 数据源断了怎么办？
14. 为什么没有做复杂深度学习？
15. 如果继续开发下一步做什么？
```

每个问题准备：

```text
30 秒回答
+
2 分钟深入回答
```

目标不是让用户背代码。

目标是让用户能够解释：

```text
问题
方法
模型
结果
限制
```

---

# 43. 最终交付物

V1 完成后必须同时存在：

```text
1. GitHub Repository

2. Public Dashboard URL

3. README

4. Real historical dataset

5. Daily automated pipeline

6. Data quality report

7. BESS optimization model

8. Strategy backtest

9. Historical PnL

10. Methodology documentation

11. Data source documentation

12. Technical report

13. Project brief

14. Dashboard screenshots
```

---

# 44. 最低可发布标准

以下条件全部满足才能称为：

```text
VoltPulse V1.0
```

必须：

```text
真实公开数据成功采集

至少拥有 14 天有效历史数据
或成功回填一批历史数据

自动更新正常

数据质量检测存在

储能模型通过测试

回测能够运行

网页公网可访问

手机可以正常查看

README 完整

来源可追溯

模拟和真实数据明确区分
```

---

# 45. 推荐开发阶段

## Phase 1：MVP

目标：

```text
Real Data
→
ETL
→
Price Chart
```

完成模块：

```text
M00
M01
M02
M03
M04
```

---

## Phase 2：核心技术

目标：

```text
Price
→
BESS Optimization
→
Profit
```

完成：

```text
M06
M07
M08
```

---

## Phase 3：资产化

目标：

```text
Daily Data
→
Historical Backtest
```

完成：

```text
M09
```

---

## Phase 4：展示

目标：

```text
Phone-accessible Dashboard
```

完成：

```text
Dashboard
README
Deployment
```

此时已经可以写入简历。

---

## Phase 5：自动化

目标：

```text
Zero-maintenance Daily Pipeline
```

完成：

```text
GitHub Actions
Logging
Status
Failure Handling
```

---

## Phase 6：国网增强

有可靠数据才做：

```text
M10
M11
```

---

## Phase 7：交易增强

有 DA/RT 数据再做：

```text
M12
M14
```

---

## Phase 8：预测

时间充裕才做：

```text
M13
```

---

# 46. 11 月前项目优先级

绝对优先：

```text
P0

真实数据
数据质量
储能 LP
回测
Dashboard
GitHub Actions
README
测试
```

第二优先：

```text
P1

衰减
负电价专题
Grid Insight
技术报告
```

第三优先：

```text
P2

DA-RT
Trading Lab
风险分析
```

最后：

```text
P3

机器学习价格预测
```

---

# 47. 项目成功指标

不要以代码行数作为指标。

真正 KPI：

```text
Pipeline Success Rate

Data Completeness

Tracked Days

Test Pass Rate

Latest Data Age

Dashboard Availability

Backtest Days

Model Constraint Violations
```

目标：

```text
Model Constraint Violations = 0
```

---

# 48. README Badge 建议

可以展示：

```text
Pipeline: Passing

Latest Data: YYYY-MM-DD

Tracked Days: xxx

Tests: Passing

Market: xxx
```

不要重点宣传：

```text
Daily GitHub commits
```

---

# 49. 技术报告

AI 最终需要自动生成：

```text
reports/research/voltpulse_report.md
```

题目建议：

**《基于公开现货市场数据的电价特征与储能优化调度研究》**

结构：

```text
摘要

1. 研究背景

2. 数据来源

3. 数据处理方法

4. 电价统计特征

5. 储能优化模型

6. 回测方法

7. 结果

8. 敏感性分析

9. 局限性

10. 下一步工作
```

报告中的所有数字必须从真实结果程序生成。

禁止 AI 凭空填写。

---

# 50. 敏感性分析

如果时间允许，优先做这个，而不是深度学习。

改变：

```text
效率
85%
88%
90%

Duration
1h
2h
4h

Degradation Cost
0
30
60 RMB/MWh
```

观察：

```text
Net Profit
EFC
Capture Value
```

这一部分非常适合工程答辩。

---

# 51. 最终 Master Acceptance Test

Reviewer Agent 最后必须执行：

```text
fresh clone repository

install dependencies

run pytest

run pipeline using fixture

run optimization

run backtest

start dashboard

check generated files

verify no secrets

verify no simulated data presented as real

verify README commands work
```

然后生成：

```text
FINAL_AUDIT.md
```

内容：

```text
PASS / FAIL

Critical Issues

Minor Issues

Deployment Status

Data Status

Model Status

Testing Status

Recommended Next Tasks
```

如果存在 Critical Issue：

不得宣布项目完成。

---

# 52. 对 AI 工作流的总命令

最终执行原则：

> 先建立最小可运行闭环，再扩展功能。任何 Agent 不得为了“看起来高级”增加需求之外的技术。数据真实性、模型正确性和自动运行稳定性高于 UI 美观和算法复杂度。每个模块必须提供测试和验收结果。真实数据不可获得时允许模块降级或隐藏，但禁止制造虚假真实数据。所有分析结果必须能够追溯到原始数据和明确的计算代码。

项目最终需要做到：

```text
打开 GitHub：
能看懂。

打开手机网页：
能看到今天的数据。

打开代码：
架构清楚。

看模型：
数学成立。

问数据：
来源明确。

问收益：
口径明确。

问局限：
能够解释。

即使一个月无人维护：
系统仍能够自动运行。
```

这就是 VoltPulse V1 的完成标准。
