"""Build the offline decision lab and its reproducible default experiment."""
import argparse
import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voltpulse.decision.game import GameConfig, simulate_game


def load_fixture(path):
    raw = path.read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if len({row["market"] for row in rows}) != 1:
        raise ValueError("Expected a single market fixture")
    grouped = {}
    for row in rows:
        if row["is_simulated"].lower() != "true" or not row["source_url"].startswith(("synthetic://", "fixture://")):
            raise ValueError("Decision lab requires labeled synthetic fixtures")
        if int(row["interval"]) != 15:
            raise ValueError("Decision lab requires 15-minute data")
        ts = datetime.fromisoformat(row["timestamp"])
        period = int(row["period"])
        if (ts.date().isoformat() != row["date"] or ts.utcoffset() != timedelta(hours=8)
                or (ts.hour * 60 + ts.minute) != (period - 1) * 15 or ts.second or ts.microsecond):
            raise ValueError("Fixture timestamp does not match its date and period")
        grouped.setdefault(row["date"], []).append(row)
    dates, days = sorted(grouped), []
    for date in dates:
        records = sorted(grouped[date], key=lambda r: r["timestamp"])
        if len(records) != 96 or [int(r["period"]) for r in records] != list(range(1, 97)):
            raise ValueError(f"Incomplete fixture day: {date}")
        days.append([float(r["price_rmb_mwh"]) for r in records])
    if not days:
        raise ValueError("Empty fixture")
    return {"dates": dates, "prices": days, "sha256": hashlib.sha256(raw).hexdigest(),
            "source_labels": sorted({r["source_url"] for r in rows})}


def build(output_dir=None, rounds=120, seed=17):
    output_dir = Path(output_dir) if output_dir else ROOT / "public"
    payload = {"schema_version": 1, "seed": seed, "rounds": rounds,
               "markets": {}, "scenarios": {}, "action_labels": ["观望", "适中", "积极"]}
    for market in ("shandong", "jiangsu"):
        fixture = load_fixture(ROOT / "tests" / "fixtures" / f"{market}_sample.csv")
        payload["markets"][market] = fixture
        for speed, alpha in (("slow", 0.05), ("balanced", 0.2), ("fast", 0.65)):
            for feedback, impact in (("none", 0.0), ("moderate", 1.5), ("strong", 4.0)):
                key = f"{market}/{speed}/{feedback}"
                payload["scenarios"][key] = simulate_game(
                    fixture["prices"], GameConfig(rounds=rounds, learning_rate=alpha, price_impact=impact, seed=seed)
                )
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    template = (ROOT / "src" / "voltpulse" / "reporting" / "templates" / "decision_lab.html").read_text(encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    html = output_dir / "decision-lab.html"
    html.write_text(template.replace("__EXPERIMENT_DATA__", serialized), encoding="utf-8")
    default = payload["scenarios"]["shandong/balanced/moderate"]
    report_dir = ROOT / "reports" / "experiments"
    report_dir.mkdir(parents=True, exist_ok=True)
    export = {"market": "shandong", "fixture": payload["markets"]["shandong"], **default}
    (report_dir / "decision_lab.json").write_text(json.dumps(export, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    last = default["history"][-1]
    report = f"""# 双储能决策实验：默认运行记录

- 场景：山东合成价格；{len(export['fixture']['dates'])} 个样本日循环重放 {rounds} 轮，不代表 {rounds} 天真实交易。
- 随机种子：{seed}；收益更新速度：0.2；价格反馈系数：1.5 (元/兆瓦时)/MW。
- 储能 A / B 累计模型净收益：{last['cumulative'][0]:,.2f} / {last['cumulative'][1]:,.2f} 元。
- 双方固定选择“适中”的独立对照累计收益：{last['fixed_cumulative'][0]:,.2f} / {last['fixed_cumulative'][1]:,.2f} 元。
- 原始样本 SHA-256：`{export['fixture']['sha256']}`。

参与者只更新本轮实际选择的策略价值；没有查看未来价格或未选策略的收益。共享价格反馈让一方的行动影响另一方收益。对照是在另一个独立市场中双方始终选择适中，并非固定对手与学习者对战。

这是固定日内模板、有限动作空间和简化价格反馈下的行为演示，不是现货市场出清、真实交易收益或均衡证明。完整默认参数与逐轮结果见 [decision_lab.json](decision_lab.json)。

复现：`python scripts/build_decision_lab.py --rounds {rounds} --seed {seed}`。交互页面：`public/decision-lab.html`；可切换 18 组预计算实验并导出 CSV/JSON。模型说明见 [决策实验说明](../../docs/decision_lab.md)。
"""
    (report_dir / "decision_lab.md").write_text(report, encoding="utf-8")
    print(f"Decision lab built: {html}; 18 scenarios, {rounds} rounds, seed={seed}")
    return html


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=120)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    build(rounds=args.rounds, seed=args.seed)
