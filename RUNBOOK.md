# VoltPulse 运维与操作手册 (RUNBOOK)

本文档面向工程维护人员与答辩演练，详细说明系统环境准备、流水线调度执行、历史数据回溯补录、异常诊断与灾难恢复流程。

---

## 1. 环境初始化与依赖激活

VoltPulse 基于 Python 3.11 运行环境构建，依赖 `scipy` (>=1.14)、`pandas`、`pyarrow`、`pydantic` 等核心科学计算包。

```bash
# 1. 激活虚拟环境 (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 2. 安装/更新本地可编辑开发包
pip install -e .

# 3. 运行全量单元测试与物理合规检查
pytest -v
```

---

## 2. 统一流水线操作命令

### 2.1 生产运行流水线 (`live` 模式)
自动执行数据同步、8维度质量校验、Parquet增量更新、MILP回测、指标聚合及移动端仪表盘构建：
```bash
python scripts/pipeline.py --mode live
```

### 2.2 测试夹具沙箱流水线 (`fixture` 模式)
在完全隔离的沙盒目录中使用测试夹具数据执行完整流水线验证，不污染正式数据资产库：
```bash
python scripts/pipeline.py --mode fixture
```

### 2.3 独立生成移动端 Dashboard
重新生成 `public/index.html` 极速单页（24KB，内置 ECharts 5.5，零第三方外链依赖）：
```bash
python scripts/build_dashboard.py
```

### 2.4 全量验收脚本
依据规范自动化验收所有关卡并刷新 `ACCEPTANCE.md`：
```bash
python scripts/acceptance.py
```

---

## 3. 数据增量更新与异常恢复

### 3.1 缺失时段补录 (Backfill)
当由于官方网络抖动或临时维护导致某些日期未同步时：
1. 检查 `data/metadata/quality_reports/` 下对应日期的质检日志；
2. 运行指定日期区间的抓取命令：
   ```bash
   python -c "from voltpulse.ingestion.shandong import ShandongSpotAdapter; adapter = ShandongSpotAdapter(); adapter.fetch_range('2026-08-15', '2026-08-20')"
   ```
3. 重新触发 `python scripts/pipeline.py --mode live` 自动执行增量回测与页面重新渲染。

### 3.2 质检拦截与隔离机制 (Quarantine)
- 任何出现行数缺失（非96行）、价格越界（未授权极端负值）、时间戳断裂的批次，将被 `QualityValidator` 直接打上 `FAIL` 标签，拒绝合并入 `data/processed/spot_prices.parquet`；
- 失败批次保存在 `data/raw/` 对应 SHA-256 归档中，流水线自动保留上一有效批次（`last_good`），页面状态信标切换为 `stale` 或 `failed`。

### 3.3 灾难回滚流程 (Rollback)
若最新生成的分析结果出现逻辑异常：
1. 查看 SQLite 审计库 `voltpulse.db` 中 `audit_runs` 表记录；
2. 定位到最后一次状态为 `SUCCESS` 的 `run_id` 与时间戳；
3. 将 `data/results/status.json` 的 `last_good_snapshot` 重新指向该历史版本快照；
4. 重新执行 `python scripts/build_dashboard.py`，移动端界面即刻恢复至稳态快照。
