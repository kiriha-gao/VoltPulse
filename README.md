# VoltPulse
### China Power Spot Market Dynamics & Battery Energy Storage (BESS) Optimal Dispatch Platform
### 面向江苏（双峰两充两放）与山东（负电价鸭子曲线）的电力现货与储能运筹优化框架

<p align="center">
  <a href="https://github.com/kiriha-gao/VoltPulse/actions/workflows/test.yml"><img src="https://img.shields.io/badge/CI-Passing%20(Ubuntu%20%7C%20Windows)-10b981.svg?style=flat-square&logo=githubactions" alt="CI Status"></a>
  <a href="https://kiriha-gao.github.io/VoltPulse/"><img src="https://img.shields.io/badge/Live%20Demo-Interactive%20Dashboard-38bdf8.svg?style=flat-square&logo=googlechrome" alt="Live Demo"></a>
  <a href="https://highs.dev/"><img src="https://img.shields.io/badge/Optimization-SciPy%20HiGHS%20MILP-8b5cf6.svg?style=flat-square" alt="HiGHS Solver"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?style=flat-square&logo=python" alt="Python"></a>
  <a href="tests/"><img src="https://img.shields.io/badge/Tests-28%2F28%20Passed-10b981.svg?style=flat-square" alt="Tests"></a>
  <a href="NOTES.md"><img src="https://img.shields.io/badge/Notes-Engineering%20Logs-orange.svg?style=flat-square" alt="Engineering Notes"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square" alt="License"></a>
  <a href="CITATION.cff"><img src="https://img.shields.io/badge/Cite-CITATION.cff-blue.svg?style=flat-square" alt="Citation"></a>
</p>

---

## 1. 研究背景与核心问题 (Motivation)

我国电力现货市场正在从“试点探索”全面转向“长周期连续结算与商业化运行”。在不同资源禀赋与用电负荷结构的省份，现货出清电价呈现出截然不同的物理形态，对独立储能（BESS）与虚拟电厂（VPP）的充放电调度提出了完全不同的数学建模与工程要求：

1. **江苏电力现货市场（华东工业负荷中枢）**：
   - 作为全国第一工业用电大省，夏季与冬季尖峰负荷极高（突破 1.4 亿千瓦），呈现显著的**夏冬“早晚双峰”**特征（早高峰 09:00-11:30，晚高峰 18:30-21:30）。
   - **调度挑战**：储能电站必须采用**“两充两放（Two Cycles per Day）”**以捕捉两个峰谷时段。然而，双充双放使电池日等效满充满放循环次数（EFC）激增至 1.7~1.8，如果只算电能量账面价差而忽略非线性电芯衰减折损，储能项目全生命周期度电成本（LCOS）与内部收益率（IRR）将被严重高估。
2. **山东电力现货市场（高渗透新能源消纳区）**：
   - 作为全国分布式光伏装机第一大省，午间极端新能源大发造成净负荷剧烈下凹，形成典型的**“深 V 鸭子曲线”**与**负出清电价**（最低达 -80 RMB/MWh）。
   - **调度挑战**：储能调度核心在于午间负电价时段受电充电（由电网消纳补贴），并在晚高峰全容量放电。

**VoltPulse** 是一个基于 Python 3 与 SciPy HiGHS C++ 求解内核构建的高性能运筹优化分析框架。项目通过解耦的适配器架构、严密的混合整数线性规划（MILP）模型与 8 维度数据防御门禁，为储能系统在多区域现货市场下的充放电决策、电池退化成本折算及收益回测提供严谨的量化工具。

> [!NOTE]
> 详细的技术选型对比、为什么放弃 PuLP/Pyomo、以及跨平台 CI 换行符避坑经验，请参阅：  
> 👉 **[设计手记与工程踩坑记录 (NOTES.md)](NOTES.md)**

---

## 2. 核心系统特性 (System Architecture)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                VoltPulse 模块架构与数据流                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. 数据接入层 (Ingestion Adapters)                                                     │
│    - 江苏交易中心适配器 (JiangsuAdapter): 15分钟出清 / 双峰两充两放特征时序             │
│    - 山东交易中心适配器 (ShandongAdapter): 15分钟出清 / 鸭子曲线与负电价特征时序        │
│    - 统一抽象基类 (MarketDataSource): 具备不可变 SHA-256 原始存档与增量版本管理         │
│                                                                                        │
│ 2. 质量防御门禁 (Data Quality Gate)                                                    │
│    - 8 维度校验: 时间戳单调性 / 96点完整性 / 物理限价越界 / 重复数据去重 / 模拟标签防御│
│                                                                                        │
│ 3. 运筹优化求解引擎 (HiGHS MILP Optimizer)                                            │
│    - 目标函数: 最大化电能量现货套利收益 - 充放电循环电芯退化成本                       │
│    - 约束条件: 二元互斥变量 u_t 决策互斥 / 动态 SOC 连续转移 / 初末 SOC 平衡守恒       │
│                                                                                        │
│ 4. 逐日滚动回测与敏度分析 (Rolling Backtest & Sensitivity)                              │
│    - 对比基准: 理论事后最优 (HiGHS MILP) vs 规则型固定峰谷策略 (Fixed Benchmark)       │
│    - 关键指标: 净套利收益 / 双分母 EFC 循环口径 (Rated vs Usable) / 边际循环收益率       │
│                                                                                        │
│ 5. 轻量级前端看板 (Zero-Dependency Web Dashboard)                                      │
│    - 23KB 单文件纯 HTML5 + ECharts 交互看板，支持一键切换江苏与山东市场分析            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 数学模型与运筹机理 (Mathematical Formulation)

### 3.1 储能系统物理标称参数
- **标称功率与容量**：$P_{\text{rated}} = 100 \, \text{MW}, \quad E_{\text{nom}} = 200 \, \text{MWh}$（充放时长 2 小时）
- **充放电往返效率 (RTE)**：$\eta_{\text{ch}} = \eta_{\text{dis}} = \sqrt{0.85} \approx 0.922 \implies \eta_{\text{RTE}} = 85.0\%$
- **荷电状态（SOC）安全区间**：$10\% \le \text{SOC}(t) \le 90\%$，严格日内初末平衡：$\text{SOC}(0) = \text{SOC}(T) = 50\%$

### 3.2 混合整数线性规划 (MILP) 优化目标
$$\max \sum_{t=1}^T \Delta t \left[ \lambda_t P_{\text{dis}}(t) - \lambda_t P_{\text{ch}}(t) \right] - c_{\text{deg}} \cdot \sum_{t=1}^T \Delta t \left[ \eta_{\text{ch}} P_{\text{ch}}(t) + \frac{1}{\eta_{\text{dis}}} P_{\text{dis}}(t) \right]$$

其中：
- $\lambda_t$ 为 $t$ 时段日前出清电价（RMB/MWh）；
- $P_{\text{ch}}(t), P_{\text{dis}}(t)$ 分别为 AC 侧充电与放电功率（MW）；
- $c_{\text{deg}}$ 为电芯循环退化边际折损系数（默认取 30.0 RMB/吞吐 MWh）；
- $\Delta t = 0.25 \, \text{h}$（15 分钟出清粒度）。

### 3.3 关键约束方程
1. **充放互斥时段决策约束**：引入二元决策变量 $u_t \in \{0, 1\}$，防止同一时段内优化模型同时出现充放电动作：
   $$0 \le P_{\text{ch}}(t) \le u_t P_{\text{rated}}$$
   $$0 \le P_{\text{dis}}(t) \le (1 - u_t) P_{\text{rated}}$$
2. **电池电芯动态能量转移方程**：
   $$E(t) = E(t-1) + \left[ \eta_{\text{ch}} P_{\text{ch}}(t) - \frac{1}{\eta_{\text{dis}}} P_{\text{dis}}(t) \right] \Delta t$$
3. **容量限额与初末平衡**：
   $$0.10 \cdot E_{\text{nom}} \le E(t) \le 0.90 \cdot E_{\text{nom}}, \quad E(T) = E(0) = 0.50 \cdot E_{\text{nom}}$$

---

## 4. 江苏 vs 山东：14 天基准仿真算例对比 (Benchmark Simulation Results)

> [!IMPORTANT]
> **基准数据属性声明 (Data Provenance & Simulation Truthfulness)**：  
> 当前版本包含的山东与江苏 14 天日前出清时序均为**根据两省典型物理负荷与日前出清特征构建的高保真基准仿真算例（Benchmark Synthetic Dataset）**，所有数据全局明确标记 `is_simulated = True` 并带有 `synthetic://` 来源标识。  
> 本平台的核心定位是**储能运筹优化模型数学自洽性、HiGHS 求解器性能测试与调度策略对比的算法工程框架**，不声称构成基于电网官方历史结算真实数据的“实证经济学分析”。

在 100MW / 200MWh 储能电站标称参数下，基于两省典型 14 天完整 96 点基准出清时序算例回测对比如下（代码实跑精确输出）：

| 市场区域 | 核心电价形态 | 调度策略 | 14天累计净收益 (RMB) | 日均净利润 (RMB) | 累计 EFC (额定分母) | 累计 EFC (可用分母) | 相对固定策略提升 |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **江苏现货基准 (Jiangsu)** | 早晚双峰工业负荷 | 规则型固定峰谷基准 | ¥950,272.18 | ¥67,876.58 | 11.20 次 | 14.00 次 | 基准线 (Baseline) |
| **江苏现货基准 (Jiangsu)** | 早晚双峰工业负荷 | **HiGHS 最优调度 (MILP)** | **¥2,209,313.54** | **¥157,808.11** | **22.40 次** | **28.00 次** | **+132.49%** |
| **山东现货基准 (Shandong)** | 单深 V 负电价鸭子曲线 | 规则型固定峰谷基准 | ¥638,314.10 | ¥45,593.86 | 5.60 次 | 7.00 次 | 基准线 (Baseline) |
| **山东现货基准 (Shandong)** | 单深 V 负电价鸭子曲线 | **HiGHS 最优调度 (MILP)** | **¥1,738,263.73** | **¥124,161.70** | **22.40 次** | **28.00 次** | **+172.32%** |

> [!NOTE]
> **EFC 循环次数分母定义说明**：
> - **额定容量分母**：$\mathrm{EFC}_{\text{rated}} = \frac{Q}{2 E_{\text{nom}}} = \frac{Q}{400 \, \text{MWh}}$（反映标称全容量损耗进度；14 天 HiGHS 调度对应每日 1.6 次闭合循环）。
> - **可用容量分母**：$\mathrm{EFC}_{\text{usable}} = \frac{Q}{2 (E_{\max} - E_{\min})} = \frac{Q}{320 \, \text{MWh}}$（反映可用工作区间利用率；单次 10%→90%→10% 满充放计为 1.0 次，14 天对应每日 2.0 次）。
> - **关于相对增益**：表中 +132.49% 与 +172.32% 是基于 14 天算例的事后全知（Perfect Foresight）上界与固定时段规则在样本内的对照提升，包含放电深度扩容与灵活调度的综合效应，不作为实际部署中的实盘超额收益。

### 核心结论与发现
1. **江苏市场套利空间更充裕**：由于江苏峰谷价差高、日内存在早晚两个典型出清高峰，储能通过 MILP 精确规划“两充两放”，14 天净利润相比山东单峰场景高出约 **27.1%**。
2. **退化成本对浅循环的抑制机理**：单次电芯能量往返的保本边际门槛价为 $p_{\text{sell}} > \frac{p_{\text{buy}}}{\eta_{\text{ch}}\eta_{\text{dis}}} + \frac{2k}{\eta_{\text{dis}}} \approx \frac{p_{\text{buy}}}{0.85} + 65.08 \, \text{RMB/MWh}$。当价差无法覆盖该门槛时，MILP 会自发保持待机，避免盲目充放电造成电芯亏损。

---

## 5. 快速上手与本地复现 (Quick Start)

### 5.1 环境依赖
本项目仅依赖 Python 原生生态与标准科学计算库，无外部 C++ 闭源求解器配置负担：

```bash
git clone https://github.com/kiriha-gao/VoltPulse.git
cd VoltPulse

# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装生产与测试依赖
pip install -r requirements.txt
pip install -e ".[dev]"
```

### 5.2 运行测试套件与技术审查探针
```bash
# 1. 运行 28 项单元测试
pytest -v

# 2. 运行独立技术审查探针 (严格断言)
python scripts/run_probes.py
python scripts/run_extra_probes.py
```

### 5.3 编译本地数据看板与日度报告
```bash
# 生成江苏电力现货市场交互看板
python scripts/build_dashboard.py --market jiangsu

# 或生成山东电力现货市场看板
python scripts/build_dashboard.py --market shandong
```
编译完成后，可在浏览器中直接双击打开 `public/index.html` 即可离线浏览完整交互界面。

---

## 6. 学术引用 (Citation)

如果您在电力现货交易研究、储能配置规划或学术论文中参考了本项目，请按如下格式引用：

```bibtex
@software{voltpulse2026,
  author = {VoltPulse Research and Engineering Contributors},
  title = {VoltPulse: China Power Spot Market Dynamics and Battery Energy Storage Optimal Dispatch Platform},
  year = {2026},
  publisher = {GitHub},
  url = {https://github.com/kiriha-gao/VoltPulse}
}
```

---

## 7. 开源协议 (License)

本项目遵循 [MIT License](LICENSE) 开源协议。欢迎学术界与电力行业开发者交流与拓展。
