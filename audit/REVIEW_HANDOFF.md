# VoltPulse 独立技术审查交接说明书 (REVIEW_HANDOFF)

**文档版本**：2.1 (审查缺陷修复与客观真实验收版)  
**更新日期**：2026-09-21  
**项目定位**：**基于合成基准电价时序的储能运筹优化与自动化回测技术原型 (Synthetic Benchmark Prototype / Trial Run Candidate)**

---

## 1. 当前关卡与发布状态重判 (Current Status)

- **当前是否声称达到 V1.0**：**NO（明确声明未达到 V1.0 真实数据商业发布标准）**
- **当前关卡客观状态**：
  - **G0 数据可行性**：PARTIAL（已验证基于规范特征的基准时序闭环；因尚未接入电网 PMOS 内网生产源，当前数据标注为 `is_simulated = True`，不认定为官方真实结算数据已就绪）
  - **G1 最小自动闭环与数据质量门禁**：PASSED（沙箱与生产路径严格物理隔离，8维QC包含日期边界、粒度、市场身份与模拟门禁）
  - **G2 储能模型与公平回测**：PASSED（HiGHS MILP 严格充放互斥，固定策略终端 SOC 安全闲置回退，回测入口强制纯净完整日序列）
  - **G3 仪表盘与学术报告**：PASSED（页面、回测与报告采用统一配置参数，收益数字严丝合缝，报告明确标注合成原型定位）
  - **G4 无人值守与状态信标**：PARTIAL（流水线支持动态日期与网络失败硬退出；受日历物理时间限制，尚未完成线上连续 7 日无人值守观察期）
  - **G5 最终全量验收**：PARTIAL（全量27项单元测试100%通过；受真实数据接入与7日观察期限制，当前客观标定为试运行候选版 Trial Run Candidate，严禁虚报 V1.0 商业发布资格）

---

## 2. 数据属性与基准说明 (Data & Benchmark Specifications)

- **市场与标的**：山东电力现货日前市场 (`shandong`) / 100MW/200MWh 独立储能电站
- **价格类型**：日前出清价格 (`day_ahead`)
- **数据属性**：**基准合成鸭子曲线时序（Synthetic Duck-Curve Benchmark Dataset, `is_simulated = True`）**
- **数据来源标识**：`synthetic://shandong-duck-curve-generator`
- **采样频率与时区**：15分钟/点（单日 96 截面），`Asia/Shanghai`
- **基准覆盖周期**：2026-08-01 至 2026-08-14（共 14 个基准日，累计 1344 条分时样本）
- **数据与沙箱隔离**：
  - `--mode fixture` 仅在 `data/sandbox/` 目录下执行，绝不向生产 `data/processed/` 或 `public/index.html` 写入任何数据；
  - 生产数据质检门禁在 `allow_simulated = False` 时强制拦截并拒绝模拟数据，防止测试数据污染生产线。

---

## 3. 独立审查缺陷修复矩阵 (Defect Remediation Matrix)

针对独立技术审查报告（`audit/EXTERNAL_REVIEW_REPORT.md`）指出的 S0/S1 缺陷，已完成全量代码级重构，并通过审查员提供的探针脚本（附录 C）验证：

| 审查缺陷项 | 缺陷等级 | 修复实施方案 | 对应测试/探针验证 |
| :--- | :---: | :--- | :--- |
| **S0-1: 合成数据标注为官方真实** | S0 | 生成器与适配器统一标记 `is_simulated=True` 与 `synthetic://` 来源；报告与交接文档全面客观更正为合成基准原型。 | 探针 1 (Synthetic Probe) 100% 一致 |
| **S0-2: fixture 污染正式路径，live 假成功** | S0 | fixture 严格隔离至 `data/sandbox/` 路径；live 模式遇网络/解析异常严格返回退出码 1，记录 `status: failed`。 | 探针 6 (Sandbox Isolation) & 探针 7 (Live Hard Failure) 全部 PASS |
| **S0-3: 验收脚本硬编码虚假通过** | S0 | 重构 `scripts/acceptance.py`，根据子命令实际 exit code 动态渲染状态，注入故障时严格返回 1 并报告失败。 | 探针 8 (Dynamic Acceptance Audit) PASS |
| **S1-1: 原始版本被覆盖，无修订追溯** | S1 | 重构 `ingestion/base.py`，永久保留首次成功获取的原件 `original.csv`，后续变更自动保存为 `revision_{n}_{hash}.csv`。 | 探针 3 (Immutable Revision) PASS |
| **S1-2: QC 接受错误日期、粒度与市场** | S1 | 在 `quality.py` 中新增 `00:00-23:45` 日边界、`timestamp` 与 `date` 一致性、`interval` 字段与步长一致性、市场身份校验及生产模拟门禁。 | 探针 2 (QC Invalid Inputs Rejection) 5 项异常全部拦截 |
| **S1-3: 固定策略终态失守，回测混入无效序列** | S1 | 固定策略不可行窗口安全回退至闲置模式保证终态 SOC=0.50；回测强制 96 点完整日并严禁未过滤的混合 DA/RT 序列。 | 探针 4 (Terminal SOC) & 探针 5 (Half-day / Mixed Series) 全部 PASS |
| **S1-4: 页面、模型、回测与报告数值冲突** | S1 | 统一 `storage.yaml` 效率参数为 `0.922`；看板与回测无缝对接；学术报告重写并与 `evidence/backtest_summary.csv` 严丝合缝。 | 探针 9 (Evidence Profit Totals) 100% 吻合 |
| **S1-5: 测试不自包含与 workflow 缺陷** | S1 | `test_reporting.py` 改造为内存自包含 fixture；补齐 `requirements.txt`；工作流支持动态日期及 `.[dev]` 安装。 | 全量27项单测干净运行 100% 通过 |

---

## 4. 审查员探针（附录 C）复验结果证据

使用审查报告附录 C 提供的探针脚本对一次性副本进行独立执行，执行日志与返回结果如下：

```json
{
  "synthetic": {
    "all_1344_records_equal": true,
    "raw_96_prices_equal": true,
    "processed_96_prices_equal": true,
    "raw_hash_matches_metadata": true
  },
  "qc_invalid_inputs_accepted": {
    "wrong_date": false,
    "wrong_interval": false,
    "wrong_market": false,
    "simulated": false,
    "missing_source": false
  },
  "raw_revision_files": [
    "shandong/2026/08/2026-08-01/metadata.json",
    "shandong/2026/08/2026-08-01/original.csv",
    "shandong/2026/08/2026-08-01/revision_2_16367aac.csv"
  ],
  "raw_revision_content": "first",
  "model_default": {
    "net_profit": 104253.4,
    "final_soc": 0.5,
    "cell_throughput_q_mwh": 640.0,
    "efc_rated": 1.6,
    "efc_usable": 2.0,
    "independent_energy_residual": 1.0658141036401503e-14,
    "simultaneous_mw": 0.0,
    "independent_pnl": 104253.39758104389
  },
  "model_configured": {
    "net_profit": 104265.42,
    "final_soc": 0.5,
    "cell_throughput_q_mwh": 640.0,
    "efc_rated": 1.6,
    "efc_usable": 2.0,
    "independent_energy_residual": 1.0658141036401503e-14,
    "simultaneous_mw": 0.0,
    "independent_pnl": 104265.41796702822
  },
  "short_window_terminal_soc": 0.5,
  "half_day_backtested_rows": 0,
  "mixed_da_rt_result_rows": 0,
  "fixture_pipeline": {
    "exit": 0,
    "production_parquet_exists": false,
    "public_html_exists": false
  },
  "all_downloads_failed": {
    "exit": 1,
    "status": {
      "status": "failed",
      "pipeline": "failed",
      "error_category": "FileNotFoundError",
      "market": "shandong"
    }
  },
  "acceptance_all_commands_failed": {
    "exit": 1,
    "state_says_release_eligible": false,
    "state_says_all_tests_passed": false
  },
  "evidence_profit_totals": {
    "fixed_peak_valley": 638314.1,
    "perfect_foresight": 1738263.73
  }
}
```

### 4.2 二次复验补充探针（extra.py）复验结果证据

针对二次复验报告针对性编写的边界探针脚本 `scripts/run_extra_probes.py`（基于 `extra.py`），机器实际执行输出如下：

```json
{
  "date_column_wrong": false,
  "simulation_null": false,
  "synthetic_source_false_flag": false,
  "same_revision_repeat_files": [
    "original.csv",
    "revision_2_16367aac.csv"
  ],
  "unequal_initial_final_fallback": {
    "status": "INFEASIBLE_WINDOW_IDLE_FALLBACK",
    "final_soc": 0.5
  },
  "backtest_wrong_timestamp_date_rows": 0,
  "fixture_preserved_preexisting_page": true,
  "model_failure_return": 1,
  "status_after_model_failure": {
    "status": "failed",
    "pipeline": "failed",
    "last_attempt": "2026-09-21T16:24:47.763620+08:00",
    "last_success": "prior-success",
    "expected_next_check": "2026-09-22T17:00:00+08:00",
    "error_category": "RuntimeError",
    "market": "shandong",
    "schema_version": "2.0.0"
  },
  "metrics_written_before_failure": false,
  "old_evidence_simulation_values": [
    true
  ]
}
```
**断言结果**：`ALL EXTRA PROBE ASSERTIONS PASSED 100% (EXIT CODE: 0)`

---

## 5. 机器实际执行与自检命令

- `pytest -v`：全量 27 项单元测试全部通过（耗时约 1.2 秒）；
- `python scripts/acceptance.py`：动态全关卡审核通过，客观标定为试运行候选版 (G0/G4/G5 为 PARTIAL)；
- `python scripts/run_probes.py`：独立探针 9 项安全审查用例 100% 通过（带严格断言与退出码）；
- `python scripts/run_extra_probes.py`：二次复验补充探针 8 项严格用例 100% 通过；
- `python scripts/pipeline.py --mode fixture`：沙箱隔离试运行成功，零正式路径污染；
- `python scripts/package_review.py`：打包生成自包含审查归档包 `VoltPulse_REVIEW.zip`。
