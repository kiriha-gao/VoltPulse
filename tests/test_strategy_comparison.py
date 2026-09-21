import numpy as np
import pandas as pd
import pytest
from voltpulse.optimization.benchmark import HistoricalAdjustedStrategy, FixedPeakValleyStrategy
from voltpulse.optimization.bess_model import BESSOptimizer
from voltpulse.backtest.engine import BacktestEngine
from voltpulse.utils.config import get_config


def test_three_strategies_14_days_execution():
    """Verify that BacktestEngine runs all 3 strategies across 14 benchmark days cleanly."""
    cfg = get_config()
    engine = BacktestEngine(cfg.get_storage_config(), cfg.get_benchmark_config())
    
    # Load Shandong 14-day sample
    fixture_path = cfg.get_path("fixtures_dir") / "shandong_sample.csv"
    df = pd.read_csv(fixture_path)
    
    results = engine.run_backtest(df, market="shandong")
    assert len(results) == 42  # 14 days * 3 strategies
    
    strategies = set(results["strategy"].unique())
    assert strategies == {"perfect_foresight", "historical_adjusted", "fixed_peak_valley"}
    
    # Check that net profit is computed for all
    pnl = results.groupby("strategy")["net_profit"].sum()
    assert pnl["perfect_foresight"] > 0
    assert pnl["historical_adjusted"] > 0
    assert pnl["fixed_peak_valley"] > 0
    
    # Perfect foresight is theoretical upper bound
    assert pnl["perfect_foresight"] >= pnl["historical_adjusted"]
    assert pnl["perfect_foresight"] >= pnl["fixed_peak_valley"]


def test_regime_shift_failure_case():
    """
    Demonstrate Core Research Question 2 & Failure Case:
    When market regime shifts abruptly (e.g. Sunny duck curve -> Cloudy/Emergency day),
    HistoricalAdjustedStrategy blindly replays Day d-1 schedule and suffers severe lag loss,
    proving that naive persistence without day-ahead forecasting is fragile.
    """
    # 96 points per day (15-min intervals)
    # Day 1 (Sunny Duck Curve):
    # - Morning/Night: Moderate price (300 RMB/MWh)
    # - Noon (Periods 40-56, 10:00-14:00): Solar flood, negative/zero price (-20 RMB/MWh)
    # - Evening (Periods 72-84, 18:00-21:00): Evening peak (800 RMB/MWh)
    prices_day1 = np.full(96, 300.0)
    prices_day1[40:56] = -20.0   # Noon solar valley -> optimal to charge
    prices_day1[72:84] = 800.0   # Evening peak -> optimal to discharge

    # Optimize Day 1 with HiGHS MILP
    opt = BESSOptimizer(power_mw=100.0, energy_mwh=200.0)
    res_day1 = opt.optimize_dispatch(prices_day1)
    assert res_day1["status"] == "OPTIMAL"
    assert res_day1["net_profit"] > 0

    planned_charge = np.array(res_day1["p_charge_mw"])
    planned_discharge = np.array(res_day1["p_discharge_mw"])

    # Verify Day 1 charged around noon and discharged in evening
    assert np.sum(planned_charge[40:56]) > 50.0
    assert np.sum(planned_discharge[72:84]) > 50.0

    # Day 2 (Regime Shift / Abrupt Weather Change - Sudden cloudy day + wind surge):
    # - Noon (Periods 40-56): Solar collapses, industrial load high -> price spikes to PEAK (900 RMB/MWh)!
    # - Evening (Periods 72-84): Heavy wind generation + load drop -> price collapses to VALLEY (50 RMB/MWh)!
    prices_day2 = np.full(96, 300.0)
    prices_day2[40:56] = 900.0   # Peak at noon!
    prices_day2[72:84] = 50.0    # Valley at evening!

    # 1. Historical Adjusted (Lagged Persistence) blindly replays Day 1 schedule on Day 2:
    hist_strategy = HistoricalAdjustedStrategy(power_mw=100.0, energy_mwh=200.0)
    res_hist_day2 = hist_strategy.simulate(prices_day2, planned_charge, planned_discharge)

    # 2. Perfect Foresight (Oracle) on Day 2:
    res_perf_day2 = opt.optimize_dispatch(prices_day2)

    # Core Scientific Finding:
    # Historical Adjusted charges at 900 RMB/MWh and discharges at 50 RMB/MWh -> DEEP LOSS!
    assert res_hist_day2["net_profit"] < 0, f"Expected loss due to lag error, got {res_hist_day2['net_profit']}"
    # Perfect Foresight adapts and charges in evening (50 RMB) and discharges at noon (900 RMB) -> PROFIT!
    assert res_perf_day2["net_profit"] > 0, f"Expected profit for perfect foresight, got {res_perf_day2['net_profit']}"

    # Difference confirms the risk of lag persistence
    profit_gap = res_perf_day2["net_profit"] - res_hist_day2["net_profit"]
    assert profit_gap > 100000.0  # Over 100,000 RMB gap in a single day for a 100MW/200MWh battery!
