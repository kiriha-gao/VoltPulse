from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from voltpulse.reporting.dashboard_builder import DashboardBuilder
from voltpulse.reporting.daily_report import DailyReportGenerator


@pytest.fixture
def sample_datasets():
    """Generates self-contained test datasets without depending on external parquet files."""
    dates = ["2026-08-01", "2026-08-02"]
    price_records = []
    for d in dates:
        for i in range(96):
            h = i // 4
            m = (i % 4) * 15
            price_records.append({
                "market": "shandong",
                "date": d,
                "timestamp": f"{d}T{h:02d}:{m:02d}:00+08:00",
                "interval": 15,
                "price_type": "day_ahead",
                "price_rmb_mwh": 200.0 + 100.0 * np.sin(i / 10.0),
                "is_simulated": True
            })
    df_p = pd.DataFrame(price_records)

    metrics_records = []
    for d in dates:
        metrics_records.append({
            "market": "shandong",
            "date": d,
            "mean_price": 250.0,
            "min_price": -50.0,
            "max_price": 800.0,
            "peak_valley_spread": 850.0,
            "negative_price_count": 8,
            "negative_price_hours": 2.0
        })
    df_m = pd.DataFrame(metrics_records)

    backtest_records = []
    for d in dates:
        for strat in ["perfect_foresight", "fixed_peak_valley"]:
            backtest_records.append({
                "market": "shandong",
                "date": d,
                "strategy": strat,
                "strategy_label": strat.replace("_", " ").title(),
                "gross_revenue": 150000.0 if strat == "perfect_foresight" else 100000.0,
                "charging_cost": 30000.0 if strat == "perfect_foresight" else 25000.0,
                "gross_profit": 120000.0 if strat == "perfect_foresight" else 75000.0,
                "degradation_cost": 15000.0 if strat == "perfect_foresight" else 10000.0,
                "net_profit": 105000.0 if strat == "perfect_foresight" else 65000.0,
                "charge_energy_mwh": 180.0,
                "discharge_energy_mwh": 160.0,
                "cell_throughput_q_mwh": 340.0,
                "efc": 1.0,
                "efc_rated": 0.85,
                "efc_usable": 1.06,
                "cumulative_pnl": 105000.0,
                "rolling_avg_pnl_30d": 105000.0,
                "profit_per_mwh": 656.25,
                "profit_per_cycle": 105000.0
            })
    df_b = pd.DataFrame(backtest_records)
    return df_p, df_m, df_b


def test_dashboard_builder(tmp_path, sample_datasets):
    df_p, df_m, df_b = sample_datasets
    out_html = tmp_path / "public" / "index.html"

    result_path = DashboardBuilder.build_dashboard(df_p, df_m, df_b, out_html)
    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")
    assert "VoltPulse" in content
    assert "今日平均电价" in content
    assert "储能今日净收益" in content
    assert "echarts" in content


def test_daily_report_generator(tmp_path, sample_datasets):
    _, df_m, df_b = sample_datasets
    reports_dir = tmp_path / "reports"
    latest_date = str(df_m["date"].max())

    rep_path = DailyReportGenerator.generate_report("shandong", latest_date, df_m, df_b, reports_dir)
    assert rep_path.exists()
    content = rep_path.read_text(encoding="utf-8")
    assert f"({latest_date})" in content
    assert "现货电价关键特征" in content
    assert "储能电站套利表现" in content
