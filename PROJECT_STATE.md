# VoltPulse 项目状态追踪 (PROJECT_STATE)

> **方案版本**：2.0 (AI主控、低人工干预版)  
> **更新时间**：2026-09-21 21:39:13  
> **当前状态**：试运行候选版 (Candidate / Trial Run) - 未声称完成 V1.0  
> **全量测试**：全量 33 项单元测试100%通过

---

## 1. 关卡状态总览

| 关卡 | 名称 | 状态 | 详细说明 |
| :--- | :--- | :---: | :--- |
| **G0** | 数据可行性验证 | PARTIAL | 数据适配器与合成基准验证通过；真实官方在线出清数据待连接 |
| **G1** | 最小自动闭环与数据质量门禁 | PASSED | 8维度质量门禁与Parquet/SQLite存储审计 |
| **G2** | 储能模型与公平回测 (HiGHS MILP / 双EFC) | PASSED | 二元互斥变量 u_t 物理闭锁与8大边界场景验证 |
| **G3** | 移动端页面与学术级研究材料 | PASSED | 极速单页看板与学术研究报告生成成功 |
| **G4** | 无人值守试运行与5级状态信标 | PARTIAL | 离线沙箱执行成功；线上 live 模式因无外网/真实接口熔断退出 (code 1)，连续7日线上无人值守未观察 (NOT OBSERVED) |
| **G5** | 最终全量验收与发布门禁 | PARTIAL | 全量 33 项单元测试与模型原型通过；受真实数据接入与7日观察期限制，当前为试运行候选版 (Trial Run Candidate) |

---

## 2. 核心任务执行矩阵

| 任务 ID | 目标 | 状态 | 验收证据 |
| :--- | :--- | :---: | :--- |
| **T-G0-01** | 山东现货日前价格抓取与样本验证 | **passed** | `tests/test_ingestion.py` |
| **T-G1-01** | 8维度数据质量校验门禁 (Quality Gate) | **passed** | `tests/test_quality.py` |
| **T-G1-02** | Parquet原子分区存储与SQLite审计日志 | **passed** | `tests/test_storage.py` |
| **T-G1-03** | 电价基础指标与负电价特征统计 | **passed** | `tests/test_metrics.py` |
| **T-G2-01** | BESS HiGHS MILP 模型 (显式二元变量 $u_t$) | **passed** | `tests/test_bess_model.py` |
| **T-G2-02** | 电芯侧吞吐量 $Q$ 与额定/可用双 EFC 计算统一 | **passed** | `src/voltpulse/optimization/degradation.py` |
| **T-G2-03** | 固定峰谷基准策略终态 SOC 约束自洽与基准回测 | **passed** | `tests/test_backtest.py` |
| **T-G2-04** | 单因素敏感性分析引擎 (效率/时长/衰减系数) | **passed** | `src/voltpulse/optimization/sensitivity.py` |
| **T-G3-01** | 5级健康状态信标 (`healthy` ~ `unavailable`) 实现 | **passed** | `data/results/status.json` |
| **T-G3-02** | 手机端自适应静态仪表盘与 ECharts 渲染更新 | **passed** | `public/index.html` |
| **T-G3-03** | 自动化学术研究报告与求职面试材料更新 | **passed** | `reports/research/voltpulse_report.md` |
| **T-G5-01** | 统一标准入口验收脚本 `scripts/acceptance.py` | **passed** | `python scripts/acceptance.py` |

---

## 3. 当前阻塞与未完成事项

- **未达到 V1.0 发布门槛的具体原因**：
  1. 真实电力现货官方公开网络接口需要在线抓取环境支持，当前暂以合成鸭子曲线基准数据集运行；
  2. 连续 7 个自然日无人值守定时调度实测受日历物理时间限制，尚未观察满 7 天。
- **发布资格状态**：当前为候选版，试运行中 (Release Candidate / Trial Run)
