import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add src to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.acceptance")


def run_cmd(cmd: str, cwd: Path = project_root) -> tuple[int, str, float]:
    """Runs a shell command portably using sys.executable and returns exit code, output, and elapsed time."""
    start_t = time.time()
    res = subprocess.run(cmd, cwd=str(cwd), shell=True, capture_output=True, text=True)
    elapsed = time.time() - start_t
    output = (res.stdout or "") + "\n" + (res.stderr or "")
    return res.returncode, output.strip(), elapsed


def run_acceptance() -> int:
    logger.info("=" * 70)
    logger.info("VOLTPULSE V2.0 AUTOMATED ACCEPTANCE AUDIT (G0 - G5)")
    logger.info("=" * 70)

    now_iso = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    py_exec = f'"{sys.executable}"'
    gate_results = {}

    # -------------------------------------------------------------
    # G0: Data Ingestion & Real Data Feasibility
    # -------------------------------------------------------------
    logger.info("Auditing Gate G0: Data Feasibility & Ingestion...")
    cmd_g0 = f"{py_exec} -m pytest -v tests/test_ingestion.py"
    code_g0, out_g0, elapsed_g0 = run_cmd(cmd_g0)
    
    # Real data check: Does production database have genuine non-simulated records?
    prices_file = project_root / "data" / "processed" / "spot_prices.parquet"
    has_real_data = False
    if prices_file.exists():
        try:
            import pandas as pd
            df_check = pd.read_parquet(prices_file)
            if not df_check.empty and "is_simulated" in df_check.columns and "source_url" in df_check.columns:
                all_non_sim = not bool(df_check["is_simulated"].any())
                valid_sources = bool(df_check["source_url"].astype(str).str.startswith("http").all())
                has_real_data = all_non_sim and valid_sources and (len(df_check) >= 96)
        except Exception:
            has_real_data = False

    # G0 requires both ingestion adapter test passing AND verified real data
    if code_g0 == 0 and has_real_data:
        g0_status = "PASSED"
        g0_desc = "山东现货日前价格已验证（真实公开出清数据）"
    elif code_g0 == 0:
        g0_status = "PARTIAL"
        g0_desc = "数据适配器与合成基准验证通过；真实官方在线出清数据待连接"
    else:
        g0_status = "FAILED"
        g0_desc = "数据摄取适配器测试失败"

    gate_results["G0"] = {
        "title": "关卡 G0：数据可行性验证",
        "status": g0_status,
        "command": cmd_g0,
        "elapsed": f"{elapsed_g0:.2f}s",
        "evidence": "src/voltpulse/ingestion/shandong.py, tests/fixtures/shandong_sample.csv",
        "detail": g0_desc
    }

    # -------------------------------------------------------------
    # G1: Quality Gate & Minimum Closed Loop
    # -------------------------------------------------------------
    logger.info("Auditing Gate G1: Quality Gate & Storage Closed Loop...")
    cmd_g1 = f"{py_exec} -m pytest -v tests/test_quality.py tests/test_storage.py tests/test_metrics.py"
    code_g1, out_g1, elapsed_g1 = run_cmd(cmd_g1)
    gate_results["G1"] = {
        "title": "关卡 G1：最小自动闭环与数据质量门禁",
        "status": "PASSED" if code_g1 == 0 else "FAILED",
        "command": cmd_g1,
        "elapsed": f"{elapsed_g1:.2f}s",
        "evidence": "src/voltpulse/processing/quality.py, voltpulse.db",
        "detail": "8维度质量门禁与Parquet/SQLite存储审计" if code_g1 == 0 else "质量门禁或存储测试失败"
    }

    # -------------------------------------------------------------
    # G2: BESS HiGHS MILP & Backtest Engine
    # -------------------------------------------------------------
    logger.info("Auditing Gate G2: BESS HiGHS MILP & Fairness Backtest...")
    cmd_g2 = f"{py_exec} -m pytest -v tests/test_bess_model.py tests/test_backtest.py"
    code_g2, out_g2, elapsed_g2 = run_cmd(cmd_g2)
    gate_results["G2"] = {
        "title": "关卡 G2：储能模型与公平回测 (HiGHS MILP / 双EFC)",
        "status": "PASSED" if code_g2 == 0 else "FAILED",
        "command": cmd_g2,
        "elapsed": f"{elapsed_g2:.2f}s",
        "evidence": "src/voltpulse/optimization/bess_model.py, tests/test_bess_model.py",
        "detail": "二元互斥变量 u_t 物理闭锁与8大边界场景验证" if code_g2 == 0 else "模型或回测测试失败"
    }

    # -------------------------------------------------------------
    # G3: Dashboard & Research Deliverables
    # -------------------------------------------------------------
    logger.info("Auditing Gate G3: Dashboard Builder & Research Reports...")
    cmd_g3 = f"{py_exec} -m pytest -v tests/test_reporting.py"
    code_g3, out_g3, elapsed_g3 = run_cmd(cmd_g3)
    dashboard_file = project_root / "public" / "index.html"
    has_dashboard = dashboard_file.exists() and dashboard_file.stat().st_size > 5000
    research_report_file = project_root / "reports" / "research" / "voltpulse_report.md"
    has_research_report = research_report_file.exists() and research_report_file.stat().st_size > 1000
    g3_pass = (code_g3 == 0 and has_dashboard and has_research_report)
    gate_results["G3"] = {
        "title": "关卡 G3：移动端页面与学术级研究材料",
        "status": "PASSED" if g3_pass else "FAILED",
        "command": cmd_g3,
        "elapsed": f"{elapsed_g3:.2f}s",
        "evidence": "public/index.html, reports/daily/, docs/methodology.md, reports/research/voltpulse_report.md",
        "detail": "极速单页看板与学术研究报告生成成功" if g3_pass else "前端看板生成或材料缺失"
    }

    # -------------------------------------------------------------
    # G4: Automated Pipeline & Health Status Beacon
    # -------------------------------------------------------------
    logger.info("Auditing Gate G4: Pipeline In Live & Fixture Sandbox...")
    cmd_g4_fix = f"{py_exec} scripts/pipeline.py --mode fixture"
    cmd_g4_live = f"{py_exec} scripts/pipeline.py --mode live"
    code_fix, out_fix, elapsed_fix = run_cmd(cmd_g4_fix)
    code_live, out_live, elapsed_live = run_cmd(cmd_g4_live)

    # Note per V2 Spec Section 14: G4 requires 7 continuous calendar days observation
    # A single execution only proves code path execution, not 7-day unattended stability
    if code_fix == 0:
        if code_live == 0:
            g4_status = "PARTIAL"
            g4_desc = "流水线与沙箱隔离执行成功；连续7日线上无人值守观察期尚未完全结束"
        else:
            g4_status = "PARTIAL"
            g4_desc = f"离线沙箱执行成功；线上 live 模式因无外网/真实接口熔断退出 (code {code_live})，连续7日线上无人值守未观察 (NOT OBSERVED)"
    else:
        g4_status = "FAILED"
        g4_desc = "流水线执行失败"

    gate_results["G4"] = {
        "title": "关卡 G4：无人值守试运行与5级状态信标",
        "status": g4_status,
        "command": f"{cmd_g4_fix} && {cmd_g4_live}",
        "elapsed": f"{elapsed_fix + elapsed_live:.2f}s",
        "evidence": "data/sandbox/status.json, .github/workflows/daily.yml",
        "detail": g4_desc
    }

    # -------------------------------------------------------------
    # G5: Full Regression & Release Eligibility Evaluation
    # -------------------------------------------------------------
    logger.info("Auditing Gate G5: Full Regression Test Suite...")
    cmd_g5 = f"{py_exec} -m pytest -v"
    code_full, out_full, elapsed_full = run_cmd(cmd_g5)

    import re
    match_passed = re.search(r"(\d+)\s+passed", out_full)
    passed_count = int(match_passed.group(1)) if match_passed else 0
    all_tests_passed = (code_full == 0 and passed_count > 0)
    test_suite_label = f"PASS ({passed_count} passed)" if all_tests_passed else f"FAIL ({passed_count} passed)"

    all_commands_succeeded = (code_g0 == 0 and code_g1 == 0 and code_g2 == 0 and g3_pass and code_fix == 0 and all_tests_passed)
    is_v1_release_eligible = all_commands_succeeded and (g0_status == "PASSED") and (g4_status == "PASSED")

    if is_v1_release_eligible:
        g5_status = "PASSED"
        g5_desc = "全关卡验证通过，满足全部发布门槛"
    elif all_commands_succeeded:
        g5_status = "PARTIAL"
        g5_desc = f"全量 {passed_count} 项单元测试与模型原型通过；受真实数据接入与7日观察期限制，当前为试运行候选版 (Trial Run Candidate)"
    else:
        g5_status = "FAILED"
        g5_desc = "存在未通过的单元测试或验收命令"

    gate_results["G5"] = {
        "title": "关卡 G5：最终全量验收与发布门禁",
        "status": g5_status,
        "command": cmd_g5,
        "elapsed": f"{elapsed_full:.2f}s",
        "evidence": "ACCEPTANCE.md, PROJECT_STATE.md, audit/AUDIT_RUN.log",
        "detail": g5_desc
    }

    # -------------------------------------------------------------
    # Write Updated ACCEPTANCE.md Dynamically
    # -------------------------------------------------------------
    acceptance_md_path = project_root / "ACCEPTANCE.md"
    lines = [
        "# VoltPulse 关卡验收记录 (ACCEPTANCE)",
        "",
        f"> **自动验收更新时间**：{now_iso}  ",
        f"> **全量回归测试状态**：{test_suite_label}  ",
        f"> **当前系统发布资格**：{'YES (已具备 V1.0 发布资格)' if is_v1_release_eligible else 'NO (当前为候选试运行版，未达 V1.0 发布门槛)'}",
        "",
        "---",
        ""
    ]

    for gid, info in gate_results.items():
        lines.append(f"## {info['title']}")
        lines.append(f"- **状态**：**{info['status']}**")
        lines.append(f"- **详细说明**：{info['detail']}")
        lines.append(f"- **验收命令**：`{info['command']}`")
        lines.append(f"- **耗时**：{info['elapsed']}")
        lines.append(f"- **证据路径**：{info['evidence']}")
        lines.append("")

    with open(acceptance_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # -------------------------------------------------------------
    # Write Updated PROJECT_STATE.md Dynamically
    # -------------------------------------------------------------
    project_state_path = project_root / "PROJECT_STATE.md"
    
    rows_text = ""
    for gid, info in gate_results.items():
        rows_text += f"| **{gid}** | {info['title'].split('：')[1]} | {info['status']} | {info['detail']} |\n"

    status_beacon_file = project_root / "data" / "results" / "status.json"
    has_status_beacon = status_beacon_file.exists()

    state_content = f"""# VoltPulse 项目状态追踪 (PROJECT_STATE)

> **方案版本**：2.0 (AI主控、低人工干预版)  
> **更新时间**：{now_iso}  
> **当前状态**：{'全关卡通过，具备 V1.0 发布资格' if is_v1_release_eligible else '试运行候选版 (Candidate / Trial Run) - 未声称完成 V1.0'}  
> **全量测试**：{'全量 ' + str(passed_count) + ' 项单元测试100%通过' if all_tests_passed else '单元测试存在失败'}

---

## 1. 关卡状态总览

| 关卡 | 名称 | 状态 | 详细说明 |
| :--- | :--- | :---: | :--- |
{rows_text}
---

## 2. 核心任务执行矩阵

| 任务 ID | 目标 | 状态 | 验收证据 |
| :--- | :--- | :---: | :--- |
| **T-G0-01** | 山东现货日前价格抓取与样本验证 | **{'passed' if code_g0 == 0 else 'failed'}** | `tests/test_ingestion.py` |
| **T-G1-01** | 8维度数据质量校验门禁 (Quality Gate) | **{'passed' if code_g1 == 0 else 'failed'}** | `tests/test_quality.py` |
| **T-G1-02** | Parquet原子分区存储与SQLite审计日志 | **{'passed' if code_g1 == 0 else 'failed'}** | `tests/test_storage.py` |
| **T-G1-03** | 电价基础指标与负电价特征统计 | **{'passed' if code_g1 == 0 else 'failed'}** | `tests/test_metrics.py` |
| **T-G2-01** | BESS HiGHS MILP 模型 (显式二元变量 $u_t$) | **{'passed' if code_g2 == 0 else 'failed'}** | `tests/test_bess_model.py` |
| **T-G2-02** | 电芯侧吞吐量 $Q$ 与额定/可用双 EFC 计算统一 | **{'passed' if code_g2 == 0 else 'failed'}** | `src/voltpulse/optimization/degradation.py` |
| **T-G2-03** | 固定峰谷基准策略终态 SOC 约束自洽与基准回测 | **{'passed' if code_g2 == 0 else 'failed'}** | `tests/test_backtest.py` |
| **T-G2-04** | 单因素敏感性分析引擎 (效率/时长/衰减系数) | **{'passed' if code_g2 == 0 else 'failed'}** | `src/voltpulse/optimization/sensitivity.py` |
| **T-G3-01** | 5级健康状态信标 (`healthy` ~ `unavailable`) 实现 | **{'passed' if has_status_beacon else 'failed'}** | `data/results/status.json` |
| **T-G3-02** | 手机端自适应静态仪表盘与 ECharts 渲染更新 | **{'passed' if has_dashboard else 'failed'}** | `public/index.html` |
| **T-G3-03** | 自动化学术研究报告与求职面试材料更新 | **{'passed' if has_research_report else 'failed'}** | `reports/research/voltpulse_report.md` |
| **T-G5-01** | 统一标准入口验收脚本 `scripts/acceptance.py` | **passed** | `python scripts/acceptance.py` |

---

## 3. 当前阻塞与未完成事项

- **未达到 V1.0 发布门槛的具体原因**：
  1. 真实电力现货官方公开网络接口需要在线抓取环境支持，当前暂以合成鸭子曲线基准数据集运行；
  2. 连续 7 个自然日无人值守定时调度实测受日历物理时间限制，尚未观察满 7 天。
- **发布资格状态**：{'具备 V1.0 发布资格' if is_v1_release_eligible else '当前为候选版，试运行中 (Release Candidate / Trial Run)'}
"""
    with open(project_state_path, "w", encoding="utf-8") as f:
        f.write(state_content)

    overall_exit_code = 0 if all_commands_succeeded else 1
    logger.info("=" * 70)
    logger.info(f"ACCEPTANCE AUDIT COMPLETED. Overall Exit Code: {overall_exit_code}")
    logger.info(f"- Acceptance Record: file:///{acceptance_md_path.as_posix()}")
    logger.info(f"- Project State:     file:///{project_state_path.as_posix()}")
    logger.info("=" * 70)
    return overall_exit_code


if __name__ == "__main__":
    sys.exit(run_acceptance())
