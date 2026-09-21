# VoltPulse 数据源与合规披露说明书 (Data Sources)

本文档依据《VoltPulse V1 项目实施规格书》（第 28 条）制定，详细记录平台所接入与支持的公开电力市场数据集规范，确保数据来源清晰合规、可回溯、严禁造假。

---

## 1. 核心数据集：山东典型鸭子曲线合成基准数据 (Synthetic Benchmark Dataset)

> [!IMPORTANT]
> **真实性声明**：当前 VoltPulse 项目处于技术原型与基准验证阶段（Trial Run Candidate）。当前系统所包含与运行的 14 天山东分时出清电价为**高保真鸭子曲线合成基准数据集**（Synthetic Benchmark Dataset），系统全局标记 `is_simulated = True`，来源标识为 `synthetic://shandong-duck-curve-generator`。此举旨在确保技术审查与数学验证的完全可复现性，严禁虚构或伪称真实抓取。

| 规范条目 | 详细说明 |
| :--- | :--- |
| **数据集名称 (Dataset Name)** | 山东电力现货市场鸭子曲线特征合成基准电价 (Shandong Duck-Curve Synthetic Benchmark) |
| **数据性质 (Data Nature)** | 科学基准模拟数据集（真实光伏出力激增导致午间负电价特征） |
| **模拟标志 (Simulation Flag)** | **`is_simulated = True`**（全局强制标注，严禁虚报） |
| **来源协议与标识 (Source URL)** | `synthetic://shandong-duck-curve-generator` |
| **采样频率 (Frequency)** | 15 分钟/点，每日 96 点整点对齐 |
| **覆盖时间与时区 (Coverage)** | 每日 00:00:00 至 23:45:00，严格采用 `Asia/Shanghai` (UTC+08:00) |
| **数据范围与特征** | 14 天基准周期 (2026-08-01 至 2026-08-14)，完整体现午间深谷（最低 -65.0 RMB/MWh）与晚高峰（最高 870.0 RMB/MWh） |
| **合规与伦理声明 (Ethics)** | 遵循规格书第 1.4 条：真实可溯源。线下测试与原型验证全链路保持 `is_simulated = True`；生产质量门禁（QC Gate）在 live 模式下严格拦截未经授权的模拟数据进入生产库。 |

---

## 2. 生产目标接口规范：山东电力交易中心 (PMOS) 接入架构

| 规范条目 | 详细说明 |
| :--- | :--- |
| **生产机构 (Provider)** | 山东电力交易中心有限公司（国家电网山东省电力公司下属交易机构） |
| **官方披露网址 (URL)** | https://pmos.sd.sgcc.com.cn/ |
| **数据类型 (Data Type)** | 日前统一出清电价（Day-Ahead Electricity Clearing Price, RMB/MWh） |
| **真实数据准入规则** | 真实数据必须满足：`is_simulated = False`、`source_url` 以 `https://` 开头且指向合规披露源、每日 96 个连续 15 分钟点、时区为 `Asia/Shanghai` (+08:00)。 |
| **已知工程局限 (Known Limitations)**| 官方公开披露系统遇检修或网络波动时可能熔断；系统已具备 `INDEPENDENT_AUDIT_INJECTED_DOWNLOAD_FAILURE` 等错误容灾收尾，若无法获取则写入 `failed` 状态并保留既有快照，严禁以模拟数据伪装线上成功。 |

---

## 2. 扩展备选数据集：山西电力现货市场（架构预留）

| 规范条目 | 详细说明 |
| :--- | :--- |
| **数据集名称 (Dataset Name)** | 山西电力现货市场日前出清电价与运行日报数据 |
| **数据提供机构 (Provider)** | 山西电力交易中心有限公司 |
| **官方披露网址 (URL)** | https://pmos.sx.sgcc.com.cn/ |
| **数据类型 (Data Type)** | 日前分时统一出清价格（RMB/MWh） |
| **限价规则差异** | 山西现货限价区间为 `[0.0, 1500.0] RMB/MWh`（不设负电价规则，与山东形成鲜明机制对照） |
| **V1 阶段状态** | 架构层在 `config/markets.yaml` 已预留时区、限价与采样配置，V1 阶段优先将山东做深。 |

---

## 3. 原始数据归档与哈希存证机制 (Raw Archiving)

为确保历史数据真实可追溯，每一批次原始文件永久保存在：
`data/raw/{market}/{YYYY}/{MM}/{YYYY-MM-DD}/`
包含：
1. `original.csv`：抓取或接收到的未经修改的原始字节流文件；
2. `metadata.json`：存证元数据，包含：
   - `sha256`：原始文件 256 位安全哈希指纹；
   - `source` & `source_url`：来源名称与出处；
   - `retrieved_at`：精确到毫秒的检索归档时间戳；
   - `status`：批次状态。
