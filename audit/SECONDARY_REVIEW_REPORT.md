# VoltPulse 二次复验报告

结论：**原有具体探针多数已修复，测试套件通过；“全部 S0/S1 完成整改”不成立，项目整体仍未通过验收。**

本次对象：VoltPulse_REVIEW(1).zip。以此前独立报告附录 C 原始脚本直接执行，未修改该探针；另执行新版测试套件，并针对探针覆盖不足进行有限补充。所有运行在一次性副本中完成，原始交付文件未修改。没有进行真实抓取、线上部署或七日观察。

## 1. 直接执行结果

- 干净副本：**27 passed in 1.18s**，上轮 reporting 测试依赖生产数据的问题已修复。
- 附录 C 原样脚本：完整执行并输出 JSON，无接口适配必要。
- 注意：原探针主要采集事实，不是带全面断言的发布门禁。脚本退出 0 不等于全部检查通过，更不代表整个规格书通过。

| 上轮具体失败用例 | 本次结果 | 判定 |
| --- | --- | --- |
| fixture 标注及来源 | 新生成器、fixture 与 Adapter 均标为模拟 | 新生成路径已修复；旧交付产物未清理 |
| 错误时间戳日期、interval、market | 均拒绝 | 对这些输入通过 |
| is_simulated=True、source_url 缺失 | 均拒绝 | 对这些输入通过 |
| 原件 first→second | original 保持 first，产生修订文件 | 首次不同内容修订已修复 |
| 短放电窗口终态 | 50%，闲置回退 | 初末目标均为 50% 时通过 |
| 半天数据、混合 DA/RT | 均返回 0 行回测 | 对这些输入通过 |
| fixture 生产 Parquet | 未创建 | 通过 |
| fixture 生产网页 | 原探针显示存在；前后哈希相同 | 包内预存网页，非新增污染 |
| 所有下载失败 | 退出 1，status=failed | 通过 |
| 所有验收子命令失败 | 退出 1，不再宣称发布资格或全测试通过 | 主要缺陷已修复 |
| 核心模型 | 互斥为 0，能量残差约 10^-14 MWh | 所测场景通过 |

交付方 scripts/run_probes.py 在复制时排除了 index.html，所以其 public_html_exists=False 与本次原样解压得到 True 不矛盾。本次另用哈希确认 fixture 未修改预存正式网页；不将这个存在性探针误判为污染回归。

## 2. S0 尚未关闭：旧证据与正式网页仍错误标注

对比两轮压缩包，**evidence/ 的全部文件和 public/index.html 均未变化**。旧 processed/raw 样本仍 is_simulated=False，元数据仍写官方来源；旧模型样本、status 仍是上一轮版本。新生成器已改为模拟标签，不能自动纠正以前导出的文件。

原探针的 all_1344_records_equal=True 只表示新生成器与新 fixture 一致；raw_96_prices_equal=True 只比较价格，不能证明原始证据的来源标签已修正。该探针没有检查所有下游标签，因而“探针运行成功”不足以支持全面关闭 S0。

docs/data_sources.md、docs/methodology.md 也与上一版相同。前者仍称官方公开来源并写 is_simulated=False，后者仍使用 LP、epsilon 互斥和旧循环公式。

**处理要求：** 将旧审查证据移入明确的历史审计区域，不能继续当作当前合规证据；重新生成当前 evidence、页面、状态和方法文件，或删除不适用的当前发布产物。全部展示入口标明合成场景。修订须保留历史溯源，不通过直接改成 False 或重命名伪造真实数据。

## 3. S1：模型异常时状态仍停留 healthy，未实现完整失败保护

新版只在抓取/校验失败后主动写 failed，移除了上一版外层异常捕获。模型、存储、指标和页面构建异常没有统一收尾。

**独立复现：** 在副本置入既有 healthy 状态，为入口提供可通过 QC 的测试批次，并让 BacktestEngine.run_backtest 抛出 INJECTED_MODEL_FAILURE。结果：

- 异常向外抛出，未返回统一 pipeline 状态；
- status.json 仍为旧 healthy；
- daily_metrics.parquet 已写入；
- 数据与结果未形成同批事务。

故障注入中的输入只用于验证控制流，不宣称是真实来源。下载失败的修复不能替代模型/磁盘/页面失败保护。

**处理要求：** 统一异常收尾；先在暂存快照计算、验证，全部成功再切换 last_good；失败独立更新状态，同时保留最后成功快照。补充优化、写盘、页面构建失败测试。

## 4. S1：QC 与回测仍有输入漏洞

补充探针独立确认以下输入仍被 QC 接受：

- timestamp 和 target_date 都为 08-01，但 `date` 列写成 08-02；
- `is_simulated` 全为 null；
- source_url 明确为 `synthetic://generator`，但 is_simulated=False。

原因：日期检查只核对 timestamp，不核对 date 列；模拟标志使用 any()，缺失值未按未知来源拒绝；source 检查仅非空。真实来源不能只依靠布尔标志判断，至少应与配置的来源身份/协议一致。

回测依然以行数推断完整日。把全套 96 个时间戳移到第二天、保留原 date 列，回测仍生成两行策略结果；它没有复用完整的时间轴验证。30 日统计依然是 rolling(window=30) 记录数窗口，而非日历窗口。

**处理要求：** 强制布尔且不缺失、明确来源身份、date/时间戳/请求日期一致；回测复用完整有效日验证，并记录排除原因与覆盖率。

## 5. S1：修订仅部分修复，快照/增量/并发仍未完成

首次不同内容不会再覆盖 original，这是正确修复。但连续写 first、second、second，会生成两个不同编号但相同内容哈希的修订文件。当前只与 original 哈希比较，没有查全部已有修订。

storage/database.py 与第一轮完全相同，仍为整库重写、固定临时文件名，无统一快照、无并发锁，也没有按受影响日期增量重算。不能把“原件不覆盖”扩大解释为“所有历史恢复、事务和增量问题完成”。

**处理要求：** 按内容哈希去重全部版本；实现有效快照与恢复；对重复抓取不刷新 last_data_change；补充锁或明确只允许单写者并通过验证。

## 6. S1：固定策略回退对不同初末 SOC 仍不成立

默认 initial=final=50% 的短窗口已修复。额外配置 initial=50%、final=60%、充放窗口为空，代码返回 INFEASIBLE_WINDOW_IDLE_FALLBACK，但 final_soc 仍为 50%。将 curr_e 赋成 e_final 不会改变实际 energy 数组。

如果 V1 只允许初末相等，应在配置入口明确拒绝不等配置；否则必须提供真正可行的调度或失败结果。回退状态也应传到回测输出，不能静默丢弃。此项不否定默认等终态用例的修复。

## 7. 数值口径：新生成代码改善，但交付包仍不一致

新版 DashboardBuilder 会读取 storage 配置，修复了旧版直接采用默认效率的问题。研究报告主收益数字也已调整至：最优 1,738,263.73 元、固定 638,314.10 元，并明确写合成场景。

但：

- 包内正式网页未重新生成，仍有 08-14 KPI 136,312.65 元和历史 136,323.80 元两套值；
- evidence 模型样本仍使用默认效率，对应 08-01 104,253.40 元；回测仍是配置效率下 104,265.42 元；
- scripts/build_research_report.py 未修改，重新生成仍会使用旧 LP/真实数据措辞；只改报告成品不能保证后续运行正确；
- pipeline 的敏感性基准效率使用 charge_efficiency ** 2，非 charge_efficiency × discharge_efficiency；非对称效率配置会错误。默认两者相同时不产生此项误差。

**处理要求：** 一份数据/配置/代码版本清单驱动所有产物，更新生成器后重新生成，而非仅手改报告；一致性验收读取实际打包文件。

## 8. 验收与自动化剩余问题

已经修复 requirements.txt 缺失、安装 .[dev]、workflow 多余 results/ 路径以及 CLI 的固定日期。无需重复返工这些已解决项。

但 acceptance.py 仍存在：

- has_real_data 使用 `not bool(df['is_simulated'].all())`，只需有一个 False 就可能把混合库视为真实；缺少有效天数和来源证明。
- 执行 code_live 后，没有将其纳入 all_commands_succeeded；必须独立记录 live 失败，不能仅归因为未满七天。
- 全测试数量仍分别硬编码为 26 和 27，部分任务行固定 passed。
- G3 看板缺失等门禁状态未完全纳入总体判定。
- 交接文档称 G5 PASSED，但实际脚本在无真实数据和观察证据时只能给 PARTIAL；文档相互矛盾。
- scripts/run_probes.py 主要打印 PASS/FAIL，缺少严格总断言与对应失败退出。原附录 C 本来是取证脚本，开发方包装后应另加正式断言。

CLI live 不带参数时从今天向未来取 14 天，而非回填过去 14 天。workflow 显式 days=1 避开此问题，但 acceptance 默认调用仍受影响；函数自身默认日期也仍为 08-01，与 CLI 不一致。

工作流仍未独立发布失败状态，无实际部署和七日记录。不能仅因时间经过七天就自动通过。

## 9. 本轮关卡结论

| 范围 | 结论 |
| --- | --- |
| 27 项现有测试 | PASS |
| 上轮具体负向输入与核心修复 | 多数 PASS，按第 1 节逐项限定 |
| 真实数据 G0 | 未完成；合成数据不能作为真实数据关卡的部分证据 |
| G1/G2/G3 全规格 | PARTIAL，仍有上述未关闭缺陷 |
| G4 线上无人值守 | NOT OBSERVED，另有实现缺陷 |
| G5 全部 S0/S1 关闭及发布资格 | FAIL |

建议下一轮只做四件事：清理并重生成一致的当前产物；统一异常与快照提交；补完整 Schema/QC/回测验证；把本轮负向用例加入真正会失败退出的测试。然后再获取真实数据与开展观察。不要仅围绕固定探针中的几个布尔值修改代码。

## 附录：原样探针、补充探针和测试结果

原样探针未改动，见上轮报告附录 C。本报告记录此次实际输出；补充探针脚本附后，仅对一次性副本运行。

### pytest.log

```text
...........................                                              [100%]
27 passed in 1.18s

```

### original_probe_results.json

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
    "independent_energy_residual": 1.4210854715202004e-14,
    "simultaneous_mw": 0.0,
    "independent_pnl": 104253.39758104389
  },
  "model_configured": {
    "net_profit": 104265.42,
    "final_soc": 0.5,
    "cell_throughput_q_mwh": 640.0,
    "efc_rated": 1.6,
    "efc_usable": 2.0,
    "independent_energy_residual": 1.7763568394002505e-14,
    "simultaneous_mw": 0.0,
    "independent_pnl": 104265.41796702822
  },
  "short_window_terminal_soc": 0.5,
  "half_day_backtested_rows": 0,
  "mixed_da_rt_result_rows": 0,
  "fixture_pipeline": {
    "exit": 0,
    "production_parquet_exists": false,
    "public_html_exists": true
  },
  "all_downloads_failed": {
    "exit": 1,
    "status": {
      "status": "failed",
      "pipeline": "failed",
      "last_attempt": "2026-09-21T16:04:00.833986+08:00",
      "last_success": null,
      "expected_next_check": "2026-09-22T17:00:00+08:00",
      "error_category": "FileNotFoundError",
      "market": "shandong",
      "schema_version": "2.0.0"
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

### extra_results.json

```json
{
  "date_column_wrong": true,
  "simulation_null": true,
  "synthetic_source_false_flag": true,
  "same_revision_repeat_files": [
    "revision_3_16367aac.csv",
    "original.csv",
    "revision_2_16367aac.csv"
  ],
  "unequal_initial_final_fallback": {
    "status": "INFEASIBLE_WINDOW_IDLE_FALLBACK",
    "final_soc": 0.5
  },
  "backtest_wrong_timestamp_date_rows": 2,
  "fixture_preserved_preexisting_page": true,
  "model_failure_exception": "INJECTED_MODEL_FAILURE",
  "status_after_model_failure": {
    "status": "healthy",
    "last_success": "prior-success"
  },
  "metrics_written_before_failure": true,
  "old_evidence_simulation_values": [
    false
  ]
}
```

### extra.py

```python
import json,sys,hashlib,runpy,tempfile
from pathlib import Path
from unittest.mock import patch
import pandas as pd
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'src'))
from voltpulse.processing.quality import DataQualityValidator
from voltpulse.optimization.benchmark import FixedPeakValleyStrategy
from voltpulse.backtest.engine import BacktestEngine
from voltpulse.utils.config import get_config
from voltpulse.ingestion.shandong import ShandongAdapter
cfg=get_config(); df=pd.read_csv(root/'evidence/processed_sample_2026-08-01.csv'); out={}
with tempfile.TemporaryDirectory() as t:
 v=DataQualityValidator(Path(t))
 for name,x in [('date_column_wrong',df.assign(date='2026-08-02')),('simulation_null',df.assign(is_simulated=None)),('synthetic_source_false_flag',df.assign(source_url='synthetic://generator',is_simulated=False))]:
  out[name]=v.validate_daily_spot_prices(x,'shandong','2026-08-01')[0]
 a=ShandongAdapter({},Path(t)/'raw')
 for b in [b'first',b'second',b'second']:a.save_raw_archive(b,'2026-08-01','csv',{})
 out['same_revision_repeat_files']=[x.name for x in (Path(t)/'raw').rglob('*.csv')]
b=FixedPeakValleyStrategy({'soc_initial':.5,'soc_final':.6},charging_windows=[],discharging_windows=[]).simulate(df.price_rmb_mwh.to_numpy(),df.timestamp.tolist())
out['unequal_initial_final_fallback']={k:b[k] for k in ['status','final_soc']}
e=BacktestEngine(cfg.get_storage_config(),cfg.get_benchmark_config())
x=df.copy();x['timestamp']=(pd.to_datetime(x.timestamp)+pd.Timedelta(days=1)).astype(str)
out['backtest_wrong_timestamp_date_rows']=len(e.run_backtest(x,'shandong'))
pipe=runpy.run_path(str(root/'scripts/pipeline.py'))
page=root/'public/index.html'; before=hashlib.sha256(page.read_bytes()).hexdigest()
pipe['run_pipeline'](backfill_days=1,mode='fixture')
out['fixture_preserved_preexisting_page']=before==hashlib.sha256(page.read_bytes()).hexdigest()
prod=cfg.get_path('spot_prices_parquet');prod.parent.mkdir(parents=True,exist_ok=True)
df.to_parquet(prod,index=False)
status=cfg.get_path('status_file');status.parent.mkdir(parents=True,exist_ok=True);status.write_text(json.dumps({'status':'healthy','last_success':'prior-success'}))
with patch.object(ShandongAdapter,'ingest_date',return_value=(df,{'source':'audit fault injection','sha256':'test'})),patch.object(BacktestEngine,'run_backtest',side_effect=RuntimeError('INJECTED_MODEL_FAILURE')):
 try:out['model_failure_return']=pipe['run_pipeline'](backfill_days=1,mode='live')
 except Exception as ex:out['model_failure_exception']=str(ex)
out['status_after_model_failure']=json.loads(status.read_text())
out['metrics_written_before_failure']=(cfg.get_path('results_dir')/'daily_metrics.parquet').exists()
out['old_evidence_simulation_values']=df.is_simulated.unique().tolist()
print(json.dumps(out,ensure_ascii=False,indent=2));Path(sys.argv[2]).write_text(json.dumps(out,ensure_ascii=False,indent=2))

```

压缩包 SHA-256：`5fd0bf5a04e5ce924329c1dcd2fc2ec51f2ebe745641c0101c879b2a4d34c787`

原始解压条目与压缩包逐字节一致：True。
