from pathlib import Path
import pytest
import pandas as pd

from voltpulse.backtest.engine import BacktestEngine
from voltpulse.utils.config import get_config


@pytest.fixture
def backtest_engine():
    config = get_config()
    storage_cfg = config.get_storage_config()
    benchmark_cfg = config.get_benchmark_config()
    return BacktestEngine(storage_config=storage_cfg, benchmark_config=benchmark_cfg)


@pytest.fixture
def historical_prices():
    fixture_file = Path(__file__).resolve().parent / "fixtures" / "shandong_sample.csv"
    return pd.read_csv(fixture_file)


def test_backtest_engine_14_days(backtest_engine, historical_prices):
    res_df = backtest_engine.run_backtest(historical_prices, market="shandong")

    assert not res_df.empty
    # 14 days * 3 strategies = 42 rows
    assert len(res_df) == 42
    assert set(res_df["strategy"].unique()) == {"perfect_foresight", "historical_adjusted", "fixed_peak_valley"}

    # Check required columns
    required_cols = [
        "date", "strategy", "gross_revenue", "charging_cost", "gross_profit",
        "degradation_cost", "net_profit", "charge_energy_mwh", "discharge_energy_mwh",
        "efc", "cumulative_pnl", "rolling_avg_pnl_30d", "profit_per_cycle"
    ]
    for col in required_cols:
        assert col in res_df.columns

    # Verify cumulative PnL monotonically matches sum
    pf_df = res_df[res_df["strategy"] == "perfect_foresight"].reset_index(drop=True)
    hist_df = res_df[res_df["strategy"] == "historical_adjusted"].reset_index(drop=True)
    fixed_df = res_df[res_df["strategy"] == "fixed_peak_valley"].reset_index(drop=True)

    assert round(pf_df["net_profit"].sum(), 2) == round(pf_df["cumulative_pnl"].iloc[-1], 2)
    assert round(hist_df["net_profit"].sum(), 2) == round(hist_df["cumulative_pnl"].iloc[-1], 2)
    assert round(fixed_df["net_profit"].sum(), 2) == round(fixed_df["cumulative_pnl"].iloc[-1], 2)

    # Core energy market theorem: Perfect foresight optimal must yield >= fixed heuristic strategy
    pf_total_profit = pf_df["net_profit"].sum()
    fixed_total_profit = fixed_df["net_profit"].sum()
    assert pf_total_profit >= fixed_total_profit

    # Verify explicit strategy filtering works as expected
    legacy_df = backtest_engine.run_backtest(historical_prices, market="shandong", strategies=["perfect_foresight", "fixed_peak_valley"])
    assert len(legacy_df) == 28
