# VoltPulse 核心方法论与理论推导白皮书 (Methodology)

本文档依据《VoltPulse V1 项目实施规格书》（第 27 条）制定，系统阐述平台的数据清洗规范、电价特征指标定义、储能线性规划（LP）运筹模型、状态转移方程、电池寿命衰减折旧机理与回测框架，旨在为研究人员、电网调度工程师与电力交易面试官提供透明、可复现、严密的理论依据。

---

## 一、 数据处理与质量防御体系 (Data Ingestion & Quality Audit)

### 1.1 基础时序标准化
我国现货试点省份（如山东）通常以 **15 分钟** 为一个出清计算时段，全天划分为 **96 个时序点**：
$$t \in \{1, 2, \dots, 96\}, \quad \Delta t = 0.25 \, \text{h}$$
时间戳统一强制对齐东八区北京时间（`Asia/Shanghai`, UTC+08:00）：
$$\text{timestamp} = \text{YYYY-MM-DDTHH:MM:00+08:00}$$

### 1.2 8 维数据质量防御矩阵 (M02)
数据在进入持久化层前，必须 100% 通过以下八项硬性检验，任何一项异常即触发熔断（`FAIL`），阻断数据入库：
1. **行数完整性**：$\text{Count}(t) = 96$；
2. **零空值容忍**：$\sum \mathbb{I}(\text{price} = \text{NaN}) = 0$；
3. **零重复校验**：$\text{CountUnique}(\text{timestamp}) = 96$；
4. **时序连续性**：$\forall t \in [1, 95], \, \text{timestamp}_{t+1} - \text{timestamp}_t = 15 \, \text{min}$（连续性得分 $= 1.0$）；
5. **物理合理区间**：$-500 \le \lambda_t \le 5000 \, \text{RMB/MWh}$；
6. **省级现货限价边界**：$-80.0 \le \lambda_t \le 1300.0 \, \text{RMB/MWh}$（以山东现货规则为准）；
7. **Schema 契约审查**：严格匹配 11 项标准字段；
8. **时区规范审查**：必须携带明确的时区偏移量标识。

---

## 二、 电价特征指标体系 (Price Analytics)

设某日出清电价序列为 $\Lambda = \{\lambda_1, \lambda_2, \dots, \lambda_T\}$，其中 $T=96$。

### 2.1 基础统计量
- **算术平均价**：$\bar{\lambda} = \frac{1}{T} \sum_{t=1}^T \lambda_t$
- **峰谷综合价差**：$\Delta \lambda_{\text{spread}} = \max(\Lambda) - \min(\Lambda)$
- **分位数区间**：计算 $P_{05}, P_{25}, P_{75}, P_{95}$，以 $[P_{05}, P_{95}]$ 描述排除极端尖峰/深谷后的核心波动带。

### 2.2 负电价专项统计 (M05)
在光伏装机高渗透率区域，正午常出现供大于求引发的边际负电价：
- **负电价时段数**：$N_{\text{neg}} = \sum_{t=1}^T \mathbb{I}(\lambda_t < 0)$
- **累计持续时长**：$H_{\text{neg}} = N_{\text{neg}} \times \Delta t \, (\text{h})$
- **最长连续负电价时长**：
  $$L_{\text{consec}} = \max_{k} \left\{ k \cdot \Delta t \;\middle|\; \exists i, \, \lambda_{i}, \dots, \lambda_{i+k-1} < 0 \right\}$$

---

## 三、 储能电站（BESS）运筹优化模型 (HiGHS MILP Engine)

### 3.1 机组参考标称参数
- **额定功率**：$P_{\text{rated}} = 100 \, \text{MW}$
- **额定容量**：$E_{\text{nom}} = 200 \, \text{MWh}$（充放电时长 2 小时）
- **荷电状态限制**：$SOC_{\min} = 10\%, \quad SOC_{\max} = 90\%$
- **可用储能容量**：$E_{\text{usable}} = (SOC_{\max} - SOC_{\min}) \cdot E_{\text{nom}} = 160 \, \text{MWh}$
- **充放电综合效率**：采用非对称/对称充放效率建模：
  $$\eta_{\text{ch}} = \sqrt{0.85} \approx 0.92195, \quad \eta_{\text{dis}} = \sqrt{0.85} \approx 0.92195 \implies \eta_{\text{RTE}} = \eta_{\text{ch}} \cdot \eta_{\text{dis}} = 85.0\%$$

### 3.2 混合整数线性规划（HiGHS MILP）决策变量
对于每个时段 $t \in \{1, \dots, T\}$：
- $P_{\text{ch}}(t) \ge 0$：该时段平均充电功率（MW）
- $P_{\text{dis}}(t) \ge 0$：该时段平均放电功率（MW）
- $u_t \in \{0, 1\}$：充放互斥 0-1 二进制状态指示变量（$u_t = 1$ 表示允许充电，$u_t = 0$ 表示允许放电）
- $E(t)$：时段末电池所储存的电能量（MWh）

### 3.3 状态转移方程（SOC 动力学）
电池储能量的动态物理演化方程为：
$$E(t) = E(t-1) + \eta_{\text{ch}} P_{\text{ch}}(t) \Delta t - \frac{1}{\eta_{\text{dis}}} P_{\text{dis}}(t) \Delta t, \quad \forall t = 1, \dots, T$$
其中初始储能设定为标称中间点：$E(0) = SOC_{\text{initial}} \cdot E_{\text{nom}} = 100 \, \text{MWh}$。

### 3.4 物理约束与严密互斥
1. **充放电功率与 0-1 互斥约束**：
   $$0 \le P_{\text{ch}}(t) \le u_t \cdot P_{\text{rated}}, \quad 0 \le P_{\text{dis}}(t) \le (1 - u_t) \cdot P_{\text{rated}}, \quad u_t \in \{0, 1\}$$
   通过 HiGHS MILP 严格约束 $P_{\text{ch}}(t) \cdot P_{\text{dis}}(t) \equiv 0$，即使在深负电价场景下，杜绝同一时段同时充放电造成不合逻辑的能量内耗与非物理套利漏洞。
2. **容量边界约束**：
   $$E_{\min} \le E(t) \le E_{\max}, \quad \text{其中 } E_{\min} = 20 \, \text{MWh}, \, E_{\max} = 180 \, \text{MWh}$$
3. **初末电量平衡硬约束 (Terminal SOC Constraint)**：
   $$E(T) = E(0) = 100 \, \text{MWh}$$
   若不施加终端约束，求解器将在全天最后一个高价时段将电池残余电量全部放空至 $E_{\min}$ 虚增纸面收益，导致跨日不可持续。

### 3.5 目标函数
优化目标为全天能量市场套利净收益最大化（售电收入 - 购电成本 - 电池衰减折旧）：
$$\max \sum_{t=1}^T \Delta t \left[ \lambda_t P_{\text{dis}}(t) - \lambda_t P_{\text{ch}}(t) - c_{\text{deg}} P_{\text{dis}}(t) \right]$$
其中 $c_{\text{deg}} = 30 \, \text{RMB/吞吐 MWh}$ 为度电吞吐衰减折旧成本。

---

## 四、 电池寿命衰减与双分母循环计量 (Degradation & Dual EFC Metrics)

### 4.1 吞吐量折旧模型
本项目采用标准吞吐量折旧模型：
$$\text{Cost}_{\text{deg}} = c_{\text{deg}} \cdot \sum_{t=1}^T P_{\text{dis}}(t) \Delta t = 30 \times \text{Discharge MWh}$$

### 4.2 双分母等效满充满放循环次数 (Dual EFC Metrics)
为消除行业不同口径歧义，系统严格同步计算并输出两套 EFC：
1. **基于可用容量的循环次数 (Usable Capacity EFC)**：
   $$\text{EFC}_{\text{usable}} = \frac{\sum_{t=1}^T P_{\text{dis}}(t) \Delta t}{E_{\text{usable}}} = \frac{\text{Total Discharge MWh}}{160 \, \text{MWh}}$$
2. **基于额定标称容量的循环次数 (Rated Capacity EFC)**：
   $$\text{EFC}_{\text{rated}} = \frac{\sum_{t=1}^T P_{\text{dis}}(t) \Delta t}{E_{\text{nom}}} = \frac{\text{Total Discharge MWh}}{200 \, \text{MWh}}$$

---

## 五、 Benchmark 策略体系 (Strategy Benchmarks)

1. **Strategy 1: 事后理论最优 (Perfect Foresight)**
   - 算法：基于 HiGHS MILP 混合整数规划求解全局最优解；
   - 属性：**Ex-post Theoretical Optimum（事后理论上限）**，仅作为对标基准与调度潜力评估，严禁直接宣称为前向可执行实操策略。
2. **Strategy 2: 规则型固定峰谷策略 (Fixed Peak-Valley Benchmark)**
   - 算法：模拟人工固定作息启发式调度（充电 11:00-15:00，放电 18:00-22:00）；
   - 遇满即停、遇空即止，严格守住功率与 SOC 物理极限；
   - **终端 SOC 容错与无套利闲置回退**：若因极端初末 SOC 设定或空充放窗口导致无法达成终端平衡，触发 Spec 10.4 闲置回退机制（`INFEASIBLE_WINDOW_IDLE_FALLBACK`），保持静置以防止电池物理毁损。

---

## 六、 模型局限性说明 (Limitations)

在向评审专家或面试官汇报时，应主动指出以下客观工程边界：
1. **价格接受者假设 (Price-Taker Assumption)**：模型假定 100MW 储能充放对系统边际出清电价无反作用（Market Impact 为 0）。在真实电网中，大容量储能集中充放将抬高低谷电价并平抑高峰电价；
2. **理想电芯衰减假设**：未引入温度（Arrhenius 方程）、日历老化、极化内阻动态与局部微循环雨流计数法（Rainflow Counting），衰减以线性折旧处理；
3. **电网物理拓扑省略**：单节点储能充放未代入全网交流潮流（AC-OPF）校验局部变电站母线电压越限。
