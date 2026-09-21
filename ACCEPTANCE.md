# VoltPulse 关卡验收记录 (ACCEPTANCE)

> **自动验收更新时间**：2026-09-21 16:25:21  
> **全量回归测试状态**：PASS (27 passed)  
> **当前系统发布资格**：NO (当前为候选试运行版，未达 V1.0 发布门槛)

---

## 关卡 G0：数据可行性验证
- **状态**：**PARTIAL**
- **详细说明**：数据适配器与合成基准验证通过；真实官方在线出清数据待连接
- **验收命令**：`"C:\Users\12782\.gemini\antigravity\scratch\voltpulse\.venv\Scripts\python.exe" -m pytest -v tests/test_ingestion.py`
- **耗时**：2.31s
- **证据路径**：src/voltpulse/ingestion/shandong.py, tests/fixtures/shandong_sample.csv

## 关卡 G1：最小自动闭环与数据质量门禁
- **状态**：**PASSED**
- **详细说明**：8维度质量门禁与Parquet/SQLite存储审计
- **验收命令**：`"C:\Users\12782\.gemini\antigravity\scratch\voltpulse\.venv\Scripts\python.exe" -m pytest -v tests/test_quality.py tests/test_storage.py tests/test_metrics.py`
- **耗时**：2.62s
- **证据路径**：src/voltpulse/processing/quality.py, voltpulse.db

## 关卡 G2：储能模型与公平回测 (HiGHS MILP / 双EFC)
- **状态**：**PASSED**
- **详细说明**：二元互斥变量 u_t 物理闭锁与8大边界场景验证
- **验收命令**：`"C:\Users\12782\.gemini\antigravity\scratch\voltpulse\.venv\Scripts\python.exe" -m pytest -v tests/test_bess_model.py tests/test_backtest.py`
- **耗时**：4.03s
- **证据路径**：src/voltpulse/optimization/bess_model.py, tests/test_bess_model.py

## 关卡 G3：移动端页面与学术级研究材料
- **状态**：**PASSED**
- **详细说明**：极速单页看板与学术研究报告生成成功
- **验收命令**：`"C:\Users\12782\.gemini\antigravity\scratch\voltpulse\.venv\Scripts\python.exe" -m pytest -v tests/test_reporting.py`
- **耗时**：3.07s
- **证据路径**：public/index.html, reports/daily/, docs/methodology.md, reports/research/voltpulse_report.md

## 关卡 G4：无人值守试运行与5级状态信标
- **状态**：**PARTIAL**
- **详细说明**：离线沙箱执行成功；线上 live 模式因无外网/真实接口熔断退出 (code 1)，连续7日线上无人值守未观察 (NOT OBSERVED)
- **验收命令**：`"C:\Users\12782\.gemini\antigravity\scratch\voltpulse\.venv\Scripts\python.exe" scripts/pipeline.py --mode fixture && "C:\Users\12782\.gemini\antigravity\scratch\voltpulse\.venv\Scripts\python.exe" scripts/pipeline.py --mode live`
- **耗时**：9.31s
- **证据路径**：data/sandbox/status.json, .github/workflows/daily.yml

## 关卡 G5：最终全量验收与发布门禁
- **状态**：**PARTIAL**
- **详细说明**：全量 27 项单元测试与模型原型通过；受真实数据接入与7日观察期限制，当前为试运行候选版 (Trial Run Candidate)
- **验收命令**：`"C:\Users\12782\.gemini\antigravity\scratch\voltpulse\.venv\Scripts\python.exe" -m pytest -v`
- **耗时**：4.71s
- **证据路径**：ACCEPTANCE.md, PROJECT_STATE.md, audit/AUDIT_RUN.log
