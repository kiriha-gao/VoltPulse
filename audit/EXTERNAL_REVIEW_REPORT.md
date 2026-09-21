# VoltPulse 独立技术审查与验收报告

审查日期：2026-09-21  
结论：**FAIL — 当前不能通过真实数据平台验收，也不能认定为仅等待七日观察的发布候选版。**

当前较准确的定位：**基于合成电价的储能 MILP 技术原型，包含数据隔离、验收可信性及运行可靠性的发布阻断缺陷。**

## 1. 审查范围与证据方法

审查对象为用户提供的 VoltPulse_REVIEW.zip，共 71 个文件。压缩包 SHA-256：

`5602aa2dca9ceaaf407aa7071a642e6de41f14fc95332bce731a7615d005cc4b`

先阅读 audit/REVIEW_HANDOFF.md，再对照 audit/AUDIT_RUN.log、源码、配置、测试、样本、页面和研究报告。以包内 docs/SPECIFICATION_V2.md 为主要验收依据。

解压原件保持不变，运行测试和故障注入使用单独副本。审查末尾逐文件核对，原解压文件与压缩包全部一致。本次未修复项目、连接 GitHub、部署、修改原压缩包或开展真实市场抓取。

复现环境：Linux / Python 3.12，Pandas 2.2.3、NumPy 2.3.5、SciPy 1.17.0、PyArrow 25.0.1、pytest 9.1.1；与交付方 Windows / Python 3.11 环境不完全相同。因此复现结果与对方日志分别记录，不把环境相同当成前提。

证据级别：**复现确认**指独立执行及比对；**静态确认**指明确代码路径；**交付日志**指包内记录，本次不为日志本身的真实性背书；**未观察**指缺少实际运行或外部证据。没有真实 HTTP 下载成功证据，不证明该网站永远不可用，也不证明接口不存在；但不能据此通过数据关卡。

## 2. 验收状态重判

| 关卡 | 本次结论 | 理由 |
| --- | --- | --- |
| G0 真实数据可行性 | FAIL | 所谓真实样本与合成脚本一致；交付日志中 14 次在线解析全部失败 |
| G1 最小自动闭环 | FAIL | fixture 写入正式库和网页，下载失败仍 healthy，关键 QC 缺失 |
| G2 模型与公平回测 | PARTIAL，关卡未通过 | MILP 主体可复算，但固定策略终端检查缺失、半日和混合序列进入回测 |
| G3 页面与研究材料 | FAIL | 页面与回测配置不同，报告数字及方法陈旧，来源标签错误 |
| G4 无人值守 | NOT OBSERVED，且存在实现阻断 | 没有七日或线上运行证据；调度日期固定；恢复与隔离不完整 |
| G5 最终验收 | FAIL | 验收脚本会写出错误通过状态，干净环境测试不自包含 |

不能维持交接文档“G0、G1、G2、G3、G5 已完成，只有 G4 部分完成”的判断。

## 3. S0 发布阻断：合成数据标注为官方真实数据

**位置：** tests/fixtures/generate_benchmark_fixture.py 第 21—58 行；src/voltpulse/ingestion/shandong.py 第 32—45、109 行；tests/test_ingestion.py；evidence/。

生成器以 sin、分段时间、日期取模及人为 solar_intensity 生成电价，随后写入官方来源 URL 和 is_simulated=False。Adapter 对 fixture 再次设置同样的来源和非模拟标签。测试甚至断言 fixture 必须为 False，因此测试是在保护错误标签。

**独立比对结果：**

- 在临时目录重新执行生成器，生成的 **1,344 行与提供的 fixture 全部字段完全一致**。
- evidence/raw_sample_2026-08-01.csv 的 **96 个价格与生成器逐点一致**。
- evidence/processed_sample_2026-08-01.csv 的 **96 个价格同样一致**。
- 原始样本的 SHA-256 与元数据匹配。这证明文件字节一致，不能证明数据来自官方。

**影响：** 无法接受“14 天真实市场数据”的声明。当前所有基于这些价格的历史收益、负价分布和新能源归因，最多是合成场景结果，不能用作山东真实市场研究。这里评价代码和证据，不推断用户或开发者的主观意图。

**修复及复验：** 生成器改成 synthetic 来源、is_simulated=True；清点并隔离其全部下游产物；正式发布拒绝模拟数据。重新取得合法可验证原件，保留原始响应及来源、内容类型、日期、哈希，独立核验样本后再回填。不能只把标志改为 False 来满足验收。

## 4. S0 发布阻断：fixture 污染正式路径，live 失败仍成功

**位置：** scripts/pipeline.py 第 51—90、176—201 行；config/app.yaml；audit/AUDIT_RUN.log 第 285—380 行附近。

fixture 模式只更换 Adapter 输入，没有替换 raw、processed、SQLite、results、status、public 和 reports 路径。它因此会写正式库和页面。live 模式确实尝试联网，并非直接选择 fixture；但抓取/解析异常被 continue 吞掉，随后从共享数据库继续计算。

**交付日志：** live 对 2026-08-01 至 08-14 全部报 Missing required price column；原始响应反复出现相同哈希前缀 dd4996e4；最后却退出 0 并报告 healthy。日志没有展示成功解析的官方价格。

**独立复现：** 在副本先运行一天 fixture，确认生产 Parquet 和 public/index.html 被写入；将所有下载注入 ConnectionError 后运行 live，仍退出 0、status=healthy、error_category=null，并刷新 last_success 与 last_data_change。

**影响：** 定时任务成功率、更新时间和数据真实性均失去可信性。程序成功重算旧数据不等于成功更新市场数据。保留旧结果本身正确，但不能隐藏更新失败。

**修复及复验：** 以运行模式隔离全部路径；fixture 禁止正式发布和线上降级；跟踪每次抓取是否成功、有无变化及失败分类。保留 last_good 与最后成功更新，不因重算旧库刷新数据成功时间。失败时更新独立状态，超过时效显示 stale；无真实数据则 unavailable。测试必须覆盖全失败、部分失败、无变化及预计尚未发布。

## 5. S0 发布阻断：验收脚本生成不实通过声明

**位置：** scripts/acceptance.py 第 39、94—110、150—202 行。

G0 只检查 fixture 单测返回码；G4 只检查 live/fixture 返回码和状态文件存在；没有七日观察、正式发布、真实来源等证据检查。PROJECT_STATE.md 内容是硬编码 PASSED 文本，与计算出的 gate_results 不一致；日志最后也无条件写 ALL GATES ... PASSED。报告引用 FINAL_AUDIT.md，但包内没有该文件。

**独立故障注入：** 令所有子命令返回失败，run_acceptance() 返回 1，但生成的 PROJECT_STATE.md 仍写“全量26项单元测试100%通过”“具备 V1.0 发布资格”。返回码并非总是错误，错误在其人读报告和日志可与返回码相反。

**影响：** ACCEPTANCE、PROJECT_STATE 和交接材料不能作为独立验收结论。七天之后再运行此脚本也不能自动解决问题。

**修复及复验：** 所有状态、摘要和通过数从实际证据生成；支持 FAIL / NOT OBSERVED；缺少外部证据不能推导为 PASS。通过“全失败、部分失败、无证据”三个负向用例，检查退出码、日志和文件一致。使用当前 Python 解释器运行模块，移除 .venv\\Scripts\\pytest.exe 等 Windows 硬编码路径。

## 6. S1：原始修订、last_good 和增量更新未达到声称能力

**位置：** ingestion/base.py 第 60 行；storage/database.py 第 116—144 行；scripts/pipeline.py 第 109—120 行及结果写出流程。

原始数据每次以 wb 覆盖 original.csv，metadata.json 同样覆盖。独立复现同一日期写入 first 再写 second，最终只有一个 original.csv 和一个 metadata.json，内容为 second。更严重的是，归档在解析前执行，错误响应也会覆盖上次正确原件。

Parquet 使用临时文件再替换，提供有限单文件保护；但仍是完整历史文件读写，没有按日分区或变更检测。每日指标、回测、网页和状态不是一个事务；模型失败时价格库可能已经推进、结果文件可能只更新一部分。不存在可切换的 last_good 快照指针。失败状态会丢弃旧 last_success 等信息。

数据库批次 sha256 在 pipeline 中写空字符串。缺少关联原始哈希、代码、配置、模型、运行 ID 的统一清单。固定临时文件名且无锁，静态上存在并发覆盖/丢更新风险；本次未做实际并发压力实验。

**修复：** 内容寻址原件、按批次保存元数据、变更日期重算、完整快照提交及恢复、串行锁或等效并发保护。补充同日修订、解析失败原件保护、模型失败不提交、第二进程竞争和新环境恢复测试。

## 7. S1：QC 可接受日期、粒度、市场错误的数据

**位置：** processing/quality.py；storage/schemas.py。

现有 QC 检查行数和相邻 15 分钟间隔，却不核对完整交易日的起止、不核对 timestamp 与 date/target_date 的一致性，不核对 interval 字段和时间间隔一致性，也不核对市场身份。仅检查首个时间戳的时区标记。Schema 仍是 V1 字段，缺少 series_id、location_id、价格定义、版本与原始哈希。

**独立负向用例均错误通过：**

1. 将全部时间戳向后移动一天，仍声称原交易日。
2. 时间戳仍每 15 分钟，但 interval 改为 60。
3. market 改为 shanxi，验收请求仍是 shandong。
4. source_url 设为缺失。
5. is_simulated=True 的批次没有发布级拒绝机制；QC 本身允许模拟数据可用于沙箱，但正式流程必须有额外门禁，当前没有。

此外代码将 [-500,5000] 称作 physical price 范围，并将未附生效依据的市场边界作为硬失败；价格范围是规则/质量假设而非普适物理界限。本次不判定配置的具体市场限值是否合法，仅判定缺少依据与版本管理。

**修复：** 验证明确序列身份、预期时段集合、日期边界、单位、所有必需来源字段和模式；不靠行数代替完整性。极端值按有依据的规则或 WARN 处理，不静默裁剪。

## 8. S1：固定策略不保证终态，回测纳入无效序列

**位置：** optimization/benchmark.py 第 86—110 行；backtest/engine.py 第 58—74、136 行。

默认 11:00—15:00 充、18:00—22:00 放时可回到 50%，但代码没有终态校验。将放电窗口改为 18:00—18:15，最终 SOC=**0.7644**，仍返回收益。窗口倒序、重叠、跨午夜及初终态变化也缺少明确配置验证。空列表因 `or` 表达式被替换成默认窗口。

回测只在日内少于 24 行时跳过，因此 **48 个 15 分钟时段（半天）仍生成两条完整策略记录**。按 market/date 分组，不区分 price_type；将同日 DA、RT 两套序列传入，会把 192 行当成一条时间轴，仍返回两条策略记录。

30 日均值是最近 30 行而非 30 个日历日；缺少覆盖率及排除原因。零循环收益显示 0，而非 N/A。当前主 Adapter 只输出 DA，混合序列缺陷不解释现有单序列数字，但会影响扩展及直接回测接口的可靠性。

**修复：** 固定策略调用与优化相同的物理校验；配置阶段拒绝不可行窗口或明确闲置回退。回测入口强制有效完整日和唯一 series_id；日历窗口及共同有效日期比较；按日检查最优不劣于可行固定策略。

固定策略只利用 50%—90% 容量窗口，本身可作为较弱的规则基准，不是独立数学错误；但不能把它描述为所有固定调度中的最佳策略，也不能把差异全归为预测能力。

## 9. S1：模型数值、页面与报告不属于同一配置/版本

**位置：** dashboard_builder.py 第 41—43 行；config/storage.yaml；evidence/model_dispatch_2026-08-01.json；reports/research/voltpulse_report.md。

页面重新实例化默认 BESSOptimizer，使用 sqrt(0.85)；回测使用配置中的 0.922。模型证据也使用默认参数。这使同一天出现两套收益。

| 对象 | 日期/范围 | 净收益（元） |
| --- | --- | ---: |
| 模型样本，默认效率 | 08-01 | 104,253.40 |
| 配置效率 0.922，回测 | 08-01 | 104,265.42 |
| 页面当日 KPI | 08-14 | 136,312.65 |
| 页面历史与 status | 08-14 | 136,323.80 |
| 证据汇总，最优 | 14 天 | 1,738,263.73 |
| 研究报告，最优 | 14 天 | 1,883,146.93 |
| 证据汇总，固定 | 14 天 | 638,314.10 |
| 研究报告，固定 | 14 天 | 1,496,232.87 |

研究报告仍称 LP、使用旧收益/循环/衰减口径，方法文档声称效率及 epsilon 保证互斥，与当前二元变量模型不一致。报告在没有 CAPEX 的情况下评价资本回报，并把合成曲线解释为真实新能源影响，均无支持。数值来自某次历史程序执行，也不代表符合当前版本。

**修复：** 页面直接读取同一批模型结果，参数、代码和数据版本一并传递；研究报告与方法同步重建；复验每个显示数字与同一结果快照一致。敏感性模块也应继承实际基准配置，不能独立使用默认 SOC、默认容量等参数。

## 10. S1：每日自动化与干净复现不成立

- daily.yml 调用 pipeline 时不传 date，而默认日期固定为 **2026-08-01**；配合 backfill-days=1，每天只重抓该日。
- 两个 workflow 都执行 pip install -r requirements.txt，但包内没有该文件。打包脚本未包含它，故本次只能判定交付包不自包含，不能断言外部仓库也一定没有。
- pyproject.toml 的 pytest 在 dev 依赖内，workflow 没有显式安装 .[dev]；其能否运行依赖缺失的 requirements.txt。
- git add data/ results/ reports/ public/ 包含顶层 results/，而代码只生成 data/results/。基于包内结构会存在不存在路径的风险；若外部仓库有该目录则另验。
- 工作流无独立失败状态发布步骤；流水线失败会跳过后续部署。没有线上运行 ID、仓库 URL、可访问部署 URL 或七日证据。
- 源码没有实现陈旧阈值判断；status healthy 是固定写入，awaiting_publication 和 stale 只是注释中的状态名。

**本次干净副本 pytest：24 passed, 2 errors。** 两个 reporting 测试直接依赖 data/ 中的生产 Parquet，包内未提供。先运行 fixture 生成这些文件，再跑得到 **26 passed**。这解释了对方日志的通过，但同时证明测试依赖预先污染/准备的数据，不是自包含的干净验收。

**修复：** 一份权威依赖及锁定记录，临时测试数据独立构建；使用目标市场当前日期及发布规则；验证全新 runner 上从恢复到发布的过程。补充运行证据后才评价线上稳定性。

## 11. 页面验收边界

静态 HTML 实际依赖 jsDelivr 的 ECharts 外链，不能称“零外链依赖”；24KB 是 HTML 大小，不代表完整加载体积。页面不读取 status.json，没有失败/陈旧状态渲染，仍把历史日期称为“今日”。SOC 使用平滑线会弱化真实分段变化的表达，应优先阶梯或不平滑绘制。

本次未执行浏览器移动端视觉和触控验证，375/390/430 px、线上可访问性、加载时延均为 NOT OBSERVED。文件存在和包含 echarts 字符串不能替代这些验收。

## 12. 可以保留的技术成果

MILP 主体确实实现了二元充放互斥、能量平衡、功率/SOC 边界和终端能量约束，目标函数包括时段长度及双向电芯吞吐成本。它不是只有文档的空壳。

独立重算 08-01 合成场景：

- 默认效率：净收益 104,253.40 元，与模型样本一致。
- 配置效率 0.922：净收益 104,265.42 元，与回测一致。
- 独立能量残差约 1.8×10^-14 MWh；同时充放功率 0 MW；终态 50%。
- Q=640 MWh，额定 EFC=1.6，可用窗口 EFC=2.0；独立收益复算与输出舍入后一致。
- 包内模型人工场景测试在本环境通过。

这支持“默认有效参数下模型核心在所测场景可运行”，不支持“所有参数/输入均正确”。参数合法性、非有限值、时间长度、求解时限、MIP gap 及异常状态记录仍需完善。没有必要优先研究跨月大规模 MILP，当前设计本来逐日求解，关键问题在数据和验收。

## 13. 对交接待核验十项的回复

| 待核验项 | 审查意见 |
| --- | --- |
| 跨月 MILP 性能 | 当前逐日问题规模小；暂不优先，先修数据与门禁。未做跨月联合求解性能验收 |
| 负价互斥 | 二元约束形式正确，已测样本为零同时充放；补参数验证及求解状态记录 |
| 双向吞吐 vs 单边衰减 | 可作情景模型，但系数口径须固定，不能冒充电化学寿命证明 |
| 固定策略截断 50% | 默认策略可以如此定义；可配置窗口下终态失守已复现 |
| DA 事后最优高估 | 缺真实价格与实际结算/执行基线，无法量化；不得给任意折扣比例 |
| 15 分钟积分误差 | 区间功率恒定假设下是模型定义；本次残差接近浮点精度，未发现积分公式缺陷 |
| 缺 RT 结算偏差 | 属于明确研究边界，不必阻断 DA 情景研究；不能宣传完整交易收益 |
| 静态页面扩展性能 | 当前嵌入最新日曲线与历史摘要，不是完整年度逐时数据；一年性能未观察 |
| 修订与并发 | 原始覆盖已复现；无事务快照和锁，必须优先修复 |
| 时长与 CAPEX | 不能据绝对收益判投资最优；当前报告已有不受支持的资本回报措辞 |

## 14. 建议返工顺序与重验标准

**第一批：恢复事实可信性。** 暂停把现有数据/报告称作真实研究；隔离合成产物；修 fixture 路径和发布门禁；重写基于证据的验收报告生成器。

**第二批：真正通过 G0。** 实际获得可追溯数据，验证抓取环境、价格口径和完整日。取得一份可信样本前，不继续扩大页面或算法。

**第三批：保证计算一致。** 补 QC 日期/粒度/身份、固定策略终端及回测序列验证；统一页面、模型、报告配置和版本。

**第四批：恢复与自动化。** 原件版本、快照、状态、变更重算、依赖和动态日期；干净环境失败演练全部完成。

**第五批：开展真实七日观察。** 留存线上 run ID、日期、输入/输出哈希、失败与恢复，随后进行最终验收。

下一包至少提供：可信原始数据和响应元数据；隔离测试；上述负向用例；干净测试日志；失败不会报告 healthy 的证据；配置一致性检查；有效来源、代码和结果版本清单；实际部署及观察记录。先通过门禁再观察七日，不能用等待代替修复。

当前适合的求职表述是“完成合成场景下储能 MILP 调度原型，真实数据接入与自动化可靠性正在整改”。不建议使用“已构建真实山东市场持续分析平台”或当前历史收益作为研究结论。

## 附录 A：独立探针结果

以下结果来自审查副本，包含故障注入；不是生产运行结果。

```json
{
  "synthetic": {
    "all_1344_records_equal": true,
    "raw_96_prices_equal": true,
    "processed_96_prices_equal": true,
    "raw_hash_matches_metadata": true
  },
  "qc_invalid_inputs_accepted": {
    "wrong_date": true,
    "wrong_interval": true,
    "wrong_market": true,
    "simulated": true,
    "missing_source": true
  },
  "raw_revision_files": [
    "shandong/2026/08/2026-08-01/metadata.json",
    "shandong/2026/08/2026-08-01/original.csv"
  ],
  "raw_revision_content": "second",
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
  "short_window_terminal_soc": 0.7644,
  "half_day_backtested_rows": 2,
  "mixed_da_rt_result_rows": 2,
  "fixture_pipeline": {
    "exit": 0,
    "production_parquet_exists": true,
    "public_html_exists": true
  },
  "all_downloads_failed": {
    "exit": 0,
    "status": {
      "status": "healthy",
      "pipeline": "healthy",
      "last_attempt": "2026-09-21T15:38:37.718725+08:00",
      "last_success": "2026-09-21T15:38:37.718725+08:00",
      "latest_market_date": "2026-08-01",
      "last_data_change": "2026-09-21T15:38:37.718725+08:00",
      "expected_next_check": "2026-09-22T17:00:00+08:00",
      "error_category": null,
      "market": "shandong",
      "data_quality": 1.0,
      "days_tracked": 1,
      "total_records": 96,
      "optimization_engine": {
        "solver": "HiGHS_MILP",
        "integrality": "Binary charge/discharge mutual exclusion u_t in {0, 1}",
        "throughput_formula": "Q = sum_t (eta_c * c_t + d_t / eta_d) * dt",
        "latest_date_net_profit_rmb": 104265.42,
        "cumulative_net_profit_rmb": 104265.42,
        "bess_rating": "100MW_200MWh"
      },
      "schema_version": "2.0.0"
    }
  },
  "acceptance_all_commands_failed": {
    "exit": 1,
    "state_says_release_eligible": true,
    "state_says_all_tests_passed": true
  },
  "evidence_profit_totals": {
    "fixed_peak_valley": 638314.1,
    "perfect_foresight": 1738263.73
  }
}
```

## 附录 B：测试日志

### 干净副本

```text
.....................EE...                                               [100%]
==================================== ERRORS ====================================
___________________ ERROR at setup of test_dashboard_builder ___________________
tests/test_reporting.py:17: in sample_datasets
    df_p = pd.read_parquet(prices_path)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/pandas/io/parquet.py:667: in read_parquet
    return impl.read(
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/pandas/io/parquet.py:267: in read
    path_or_handle, handles, filesystem = _get_path_or_handle(
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/pandas/io/parquet.py:140: in _get_path_or_handle
    handles = get_handle(
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/pandas/io/common.py:882: in get_handle
    handle = open(handle, ioargs.mode)
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/workspace/scratch/7246480f6393/audit_work/project/data/processed/spot_prices.parquet'
________________ ERROR at setup of test_daily_report_generator _________________
tests/test_reporting.py:17: in sample_datasets
    df_p = pd.read_parquet(prices_path)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/pandas/io/parquet.py:667: in read_parquet
    return impl.read(
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/pandas/io/parquet.py:267: in read
    path_or_handle, handles, filesystem = _get_path_or_handle(
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/pandas/io/parquet.py:140: in _get_path_or_handle
    handles = get_handle(
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/pandas/io/common.py:882: in get_handle
    handle = open(handle, ioargs.mode)
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/workspace/scratch/7246480f6393/audit_work/project/data/processed/spot_prices.parquet'
=========================== short test summary info ============================
ERROR tests/test_reporting.py::test_dashboard_builder - FileNotFoundError: [E...
ERROR tests/test_reporting.py::test_daily_report_generator - FileNotFoundErro...
24 passed, 2 errors in 1.31s

```

### fixture 运行之后

```text
..........................                                               [100%]
26 passed in 1.14s

```

## 附录 C：可复查的探针脚本

仅对一次性副本运行。脚本会故障注入并覆盖副本中的状态与页面，不用于生产。先安装项目运行依赖及 pytest，以项目副本为工作目录。

调用：`python probes.py /absolute/disposable/project /absolute/probe_results.json`

```python
"""Independent audit probes. Run against a disposable copy; never production."""
import csv, hashlib, json, logging, runpy, sys, tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root/'src'))
from voltpulse.optimization.bess_model import BESSOptimizer
from voltpulse.optimization.benchmark import FixedPeakValleyStrategy
from voltpulse.processing.quality import DataQualityValidator
from voltpulse.backtest.engine import BacktestEngine
from voltpulse.utils.config import get_config
from voltpulse.ingestion.shandong import ShandongAdapter
from voltpulse.ingestion.downloader import RobustDownloader
result={}
with tempfile.TemporaryDirectory() as td:
 g=runpy.run_path(str(root/'tests/fixtures/generate_benchmark_fixture.py'))
 f=g['generate_shandong_benchmark_data']; f.__globals__['__file__']=str(Path(td)/'generate.py'); f()
 gen=list(csv.DictReader(open(Path(td)/'shandong_sample.csv')))
 fix=list(csv.DictReader(open(root/'tests/fixtures/shandong_sample.csv')))
 raw=pd.read_csv(root/'evidence/raw_sample_2026-08-01.csv')
 df=pd.read_csv(root/'evidence/processed_sample_2026-08-01.csv')
 result['synthetic']={'all_1344_records_equal':gen==fix,'raw_96_prices_equal':raw.price_rmb_mwh.tolist()==[float(x['price_rmb_mwh']) for x in gen[:96]],'processed_96_prices_equal':df.price_rmb_mwh.tolist()==raw.price_rmb_mwh.tolist(),'raw_hash_matches_metadata':hashlib.sha256((root/'evidence/raw_sample_2026-08-01.csv').read_bytes()).hexdigest()==json.loads((root/'evidence/raw_sample_2026-08-01_metadata.json').read_text())['sha256']}
 v=DataQualityValidator(Path(td)/'quality')
 result['qc_invalid_inputs_accepted']={}
 for name,change in [('wrong_date',lambda x:x.assign(timestamp=(pd.to_datetime(x.timestamp)+pd.Timedelta(days=1)).astype(str))),('wrong_interval',lambda x:x.assign(interval=60)),('wrong_market',lambda x:x.assign(market='shanxi')),('simulated',lambda x:x.assign(is_simulated=True)),('missing_source',lambda x:x.assign(source_url=None))]:
  ok,report=v.validate_daily_spot_prices(change(df.copy()),'shandong','2026-08-01')
  result['qc_invalid_inputs_accepted'][name]=ok
 adapter=ShandongAdapter({},Path(td)/'raw')
 adapter.save_raw_archive(b'first','2026-08-01','csv',{})
 adapter.save_raw_archive(b'second','2026-08-01','csv',{})
 result['raw_revision_files']=[str(x.relative_to(Path(td)/'raw')) for x in (Path(td)/'raw').rglob('*') if x.is_file()]
 result['raw_revision_content']=(Path(td)/'raw/shandong/2026/08/2026-08-01/original.csv').read_text()
p=df.price_rmb_mwh.to_numpy(); ts=df.timestamp.tolist()
for key,kwargs in [('default',{}),('configured',{'charge_efficiency':.922,'discharge_efficiency':.922})]:
 o=BESSOptimizer(**kwargs); r=o.optimize_dispatch(p)
 result['model_'+key]={k:r[k] for k in ['net_profit','final_soc','cell_throughput_q_mwh','efc_rated','efc_usable']}
 c=np.array(r['p_charge_mw']);d=np.array(r['p_discharge_mw']);E=np.array(r['soc'])*200
 prev=np.r_[100,E[:-1]]
 result['model_'+key]['independent_energy_residual']=float(np.max(np.abs(E-prev-o.charge_eff*c*.25+d*.25/o.discharge_eff)))
 result['model_'+key]['simultaneous_mw']=float(np.max(np.minimum(c,d)))
 result['model_'+key]['independent_pnl']=float(np.sum(p*(d-c))*.25-30*np.sum(o.charge_eff*c+d/o.discharge_eff)*.25)
b=FixedPeakValleyStrategy({},discharging_windows=[{'start':'18:00','end':'18:15'}]).simulate(p,ts)
result['short_window_terminal_soc']=b['final_soc']
cfg=get_config()
engine=BacktestEngine(cfg.get_storage_config(),cfg.get_benchmark_config())
partial=engine.run_backtest(df.iloc[:48],'shandong')
result['half_day_backtested_rows']=len(partial)
other=df.assign(price_type='real_time')
mixed=engine.run_backtest(pd.concat([df,other]),'shandong')
result['mixed_da_rt_result_rows']=len(mixed)
# Fixture execution in disposable copy; capture shared production path writes.
pipe=runpy.run_path(str(root/'scripts/pipeline.py'))
rc=pipe['run_pipeline'](backfill_days=1,mode='fixture')
result['fixture_pipeline']={'exit':rc,'production_parquet_exists':cfg.get_path('spot_prices_parquet').exists(),'public_html_exists':(root/'public/index.html').exists()}
with patch.object(RobustDownloader,'get',side_effect=ConnectionError('INDEPENDENT_AUDIT_INJECTED_DOWNLOAD_FAILURE')):
 rc=pipe['run_pipeline'](backfill_days=1,mode='live')
result['all_downloads_failed']={'exit':rc,'status':json.loads(cfg.get_path('status_file').read_text())}
# Prove acceptance failure still writes success assertions without invoking its real commands.
accept=runpy.run_path(str(root/'scripts/acceptance.py'))
accept['run_acceptance'].__globals__['run_cmd']=lambda *a,**k:(1,'INJECTED_ALL_COMMANDS_FAILED',0.0)
rc=accept['run_acceptance']()
state=(root/'PROJECT_STATE.md').read_text()
result['acceptance_all_commands_failed']={'exit':rc,'state_says_release_eligible':'具备 V1.0 发布资格' in state,'state_says_all_tests_passed':'全量26项单元测试100%通过' in state}
# Packaged summary and report consistency.
bt=pd.read_csv(root/'evidence/backtest_summary.csv')
result['evidence_profit_totals']=bt.groupby('strategy').net_profit.sum().round(2).to_dict()
Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))

```
