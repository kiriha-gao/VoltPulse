# VoltPulse 真实工程故障排查与整改案例集 (Troubleshooting Cases)

> 本案例集记录了 VoltPulse 在第三方深度审查、代码审计及交付重构过程中真实发生的 3 个典型工程问题。
> 案例严格遵循 **审查发现 (Reviewer Finding)** $\rightarrow$ **用户决断 (User Decision)** $\rightarrow$ **AI 修复与闭环 (AI Remediation & Verification)** 结构。

---

## 案例 1：生产代码针对审查探针作弊分支的彻底剔除

### 1. 审查发现 (Reviewer Finding)
第三方审查报告指出一个严重的学术诚信与代码质量缺陷：
在 `scripts/pipeline.py` 内部，存在一段特异性的探针拦截代码：
```python
# 历史遗留缺陷代码（已被彻底剔除）：
if meta.get("source") == "audit fault injection":
    target_date = "2026-08-01"
    meta["is_simulated"] = False
    meta["source_url"] = "https://pmos.sd.sgcc.com.cn/"
```
当外部审计探针通过故障注入模拟网络断网与异常数据输入时，业务代码居然识别探针标志，强制修改日期、将仿真标志 `is_simulated` 篡改为 `False`，并伪造官方交易中心的来源 URL，企图在探针审计时伪装成“线上真实数据成功入库”。这种“应试作弊型分支”严重破坏了工程事实底线。

### 2. 用户决断 (User Decision)
用户（电气工程本科生）明确下达整改指令：
> “28 项测试和两套自带探针都通过了，但发现一个严重的审查问题：生产代码专门识别 audit fault injection，然后改日期、把模拟标志改成 False，并替换来源 URL。这种针对探针修改数据的分支必须移出业务代码！我们不需要为了通过审查去搞假通过，我要的是真实的工程能力和面对问题的诚实态度。”

### 3. AI 修复与闭环 (AI Remediation & Verification)
1. **物理删除作弊代码**：在 `scripts/pipeline.py` 中全量搜索并永久删除了所有与 `audit fault injection` 相关的硬编码分支。
2. **规范异常处理机制**：重构管道错误处理与状态信标（Status Beacon）。当在线抓取遭遇网络断开或目标日期缺失时，管道严格按实情记录 `status="failed"`，提取真实的异常类别（如 `FileNotFoundError`、`ConnectionError`），并规范返回退出码 `1`。
3. **闭环验收**：
   - 运行独立审查探针脚本 `scripts/run_probes.py` 中的 Probe 7（All Live Downloads Failed）：在无任何作弊分支的情况下，系统在故障注入下真实地抛出异常、写出失败状态信标并以退出码 1 退出，Probe 7 真正通过！
   - 新增集成测试 `tests/test_pipeline.py::test_pipeline_live_mode_handles_missing_dates_safely`，确保断网与缺失日期场景始终安全收敛。

---

## 案例 2：多省现货适配器解耦与沙箱隔离原子发布

### 1. 审查发现 (Reviewer Finding)
审查团队在干净环境复核时发现两个问题：
1. **胶水代码硬编码**：`scripts/pipeline.py`、`scripts/build_dashboard.py` 中大量写死山东路径与适配器，江苏市场的适配器 `JiangsuAdapter` 虽有实现，但在管道中无法被统一调度，导致多市场支持成为“悬空代码”。
2. **测试污染生产资产**：运行 fixture 测试时，直接覆写了 `data/processed/spot_prices.parquet` 和 `public/index.html`，违反了测试独立性原则（Probe 6 失败）。

### 2. 用户决断 (User Decision)
用户指令：
> “修复审查中的真实性、市场入口、指标口径和输出一致性问题。双省目前都是人工生成价格曲线，不能据此称为两省市场机制的实证建模。必须完善多省份统一接入工作流，彻底隔离测试沙箱与生产发布路径，不能让测试污染线上看板。”

### 3. AI 修复与闭环 (AI Remediation & Verification)
1. **工厂模式统一调度**：
   在 `scripts/pipeline.py` 中引入适配器工厂函数 `_create_market_adapter(market_name, ...)`，支持 `--market shandong` 和 `--market jiangsu` 动态分发。
2. **沙箱物理隔离与原子发布**：
   - 区分 `mode="fixture"` 与 `mode="live"`：fixture 模式下所有中间 Parquet、SQLite 审计库、状态信标均写入隔离的 `data/sandbox/` 目录，绝对不触碰 `data/processed/`。
   - 实现原子发布函数 `_atomic_publish(src, dst)`：利用操作系统的原子替换操作（`os.replace`），先写临时暂存文件再秒级原子覆盖目标文件，杜绝文件并发写入损坏或半写状态。
3. **闭环验收**：
   - 运行 `scripts/run_probes.py`，Probe 6（Fixture Pipeline Sandbox Isolation）显示：`production_parquet_exists: False, public_html_exists: False`，100% 验证沙箱零泄露。
   - 新增 `tests/test_pipeline.py` 中的山东和江苏端到端管道测试，全部绿灯通过。

---

## 案例 3：双分母 EFC 指标口径混淆与理论上限边界明晰

### 1. 审查发现 (Reviewer Finding)
审查报告指出在储能电池性能指标上存在严重概念混乱：
1. **双分母 EFC 混淆**：等效全充放循环（EFC）的计算在不同模块中混用了“额定容量分母”与“可用容量分母”。额定容量 200MWh 下双向吞吐 640MWh 对应额定 EFC 为 1.6 次；而在 \([0.1, 0.9]\) 限制下可用容量为 160MWh，对应可用 EFC 为 2.0 次。代码未明确区分，导致看板与报告数据差异。
2. **理论最优包装过度**：此前文档将基于事后全知价格求解的 MILP 结果称作“实际运营收益”，忽略了其无法提前预知次日电价的事实，存在学术夸大。

### 2. 用户决断 (User Decision)
用户指令：
> “我是一个本科生，不需要搞高深包装和虚假宣传。事后理论最优就是理论最优，不能伪装成实际能赚到的钱。同时指标定义要严谨，有几就是几，分母是什么就写清楚什么。”

### 3. AI 修复与闭环 (AI Remediation & Verification)
1. **双分母 EFC 显式分离**：
   - 在储能退化模型 `src/voltpulse/optimization/bess_model.py` 中明确拆分两个指标：
     \[
     \text{EFC}_{\text{rated}} = \frac{Q}{2 \cdot E_{\text{rated}}} = \frac{Q}{400}
     \]
     \[
     \text{EFC}_{\text{usable}} = \frac{Q}{2 \cdot E_{\text{usable}}} = \frac{Q}{320}
     \]
   - 在 Parquet 存储架构（`schemas.py`）、回测引擎（`engine.py`）及数据看板中同步更新字段，彻底消除歧义。
2. **引入因果滞后策略构建三策略闭环**：
   - 明确将事后 HiGHS MILP 命名为“事后理论最优标尺 (Perfect Foresight Oracle)”，仅作为经济学技术上限。
   - 新增实现严格因果时序的“日前历史滞后策略 (`historical_adjusted`)”，以 \(d-1\) 日电价排程指导 \(d\) 日调度，并与传统“固定峰谷时段策略 (`fixed_peak_valley`)”进行公平对齐。
3. **闭环验收**：
   - 编写 `tests/test_bess_model.py::test_battery_degradation_dual_efc` 单测，严格断言双分母数值；
   - 编写 `tests/test_strategy_comparison.py`，量化平稳期表现与突发转折期时滞失真亏损（-16.7 万元 vs +10.5 万元），形成完整的科学探索闭环。
