import pytest
import numpy as np

from voltpulse.optimization.bess_model import BESSOptimizer, BESSModelSanityError
from voltpulse.optimization.degradation import BatteryDegradationModel
from voltpulse.optimization.sensitivity import SensitivityAnalyzer


@pytest.fixture
def optimizer():
    return BESSOptimizer(
        power_mw=100.0,
        energy_mwh=200.0,
        soc_min=0.10,
        soc_max=0.90,
        soc_initial=0.50,
        soc_final=0.50,
        degradation_cost_per_mwh=30.0
    )


# =========================================================================
# 8 Required Model Tests Conforming to V2.0 Specification Section 11.2
# =========================================================================

def test_v2_case_1_constant_non_negative_price(optimizer):
    """
    Scenario 1: Constant non-negative price and non-negative degradation cost.
    Battery should idle; optimal profit must be ~ 0; cannot manufacture profit.
    """
    T = 96
    prices = np.full(T, 350.0)
    res = optimizer.optimize_dispatch(prices, interval_minutes=15)

    assert res["status"] == "OPTIMAL"
    assert res["net_profit"] <= 1e-4
    assert res["cell_throughput_q_mwh"] <= 1e-4
    assert abs(res["final_soc"] - 0.50) < 1e-4


def test_v2_case_2_all_zero_prices_zero_cost():
    """
    Scenario 2: All-zero price, zero degradation cost.
    Accepts multiple optima, but must NEVER manufacture positive profit.
    """
    opt = BESSOptimizer(power_mw=100.0, energy_mwh=200.0, degradation_cost_per_mwh=0.0)
    prices = np.zeros(96)
    res = opt.optimize_dispatch(prices, interval_minutes=15)

    assert res["status"] == "OPTIMAL"
    assert abs(res["net_profit"]) < 1e-4
    assert abs(res["gross_revenue"]) < 1e-4
    assert abs(res["final_soc"] - 0.50) < 1e-4


def test_v2_case_3_low_price_then_high_price(optimizer):
    """
    Scenario 3: Low price then high price.
    Satisfies constraints, buys low and sells high with proper efficiency losses.
    """
    T = 96
    prices = np.zeros(T)
    prices[48:] = 800.0  # 800 RMB/MWh in second half

    res = optimizer.optimize_dispatch(prices, interval_minutes=15)

    assert res["status"] == "OPTIMAL"
    assert res["net_profit"] > 40000.0
    assert res["charge_energy_mwh"] > 0
    assert res["discharge_energy_mwh"] > 0
    # Efficiency loss verification: charge energy > discharge energy
    assert res["charge_energy_mwh"] > res["discharge_energy_mwh"]
    assert abs(res["final_soc"] - 0.50) < 1e-4


def test_v2_case_4_all_negative_prices(optimizer):
    """
    Scenario 4: All negative prices.
    Simultaneous charge and discharge MUST be strictly 0.0 (enforced by binary u_t).
    """
    T = 96
    prices = np.full(T, -60.0)
    res = optimizer.optimize_dispatch(prices, interval_minutes=15)

    assert res["status"] == "OPTIMAL"
    # Check binary mutual exclusion
    p_ch = np.array(res["p_charge_mw"])
    p_dis = np.array(res["p_discharge_mw"])
    simult = np.minimum(p_ch, p_dis)
    assert np.all(simult < 1e-5), "Simultaneous charge and discharge detected in negative prices!"
    assert abs(res["final_soc"] - 0.50) < 1e-4


def test_v2_case_5_extreme_prices(optimizer):
    """
    Scenario 5: Extreme positive and negative spikes [-200, 1500].
    Power, SOC, terminal balance, and binary exclusion must not breach bounds.
    """
    T = 96
    prices = np.full(T, 250.0)
    prices[40:50] = -200.0  # Midday solar surplus
    prices[72:82] = 1500.0  # Evening peak spike

    res = optimizer.optimize_dispatch(prices, interval_minutes=15)

    assert res["status"] == "OPTIMAL"
    assert res["min_soc"] >= 0.10 - 1e-4
    assert res["max_soc"] <= 0.90 + 1e-4
    assert abs(res["final_soc"] - 0.50) < 1e-4

    p_ch = np.array(res["p_charge_mw"])
    p_dis = np.array(res["p_discharge_mw"])
    assert np.all(p_ch <= 100.0 + 1e-4)
    assert np.all(p_dis <= 100.0 + 1e-4)
    assert np.all(np.minimum(p_ch, p_dis) < 1e-5)


def test_v2_case_6_high_degradation_cost():
    """
    Scenario 6: Very high degradation cost.
    Does not force unprofitable cycling; idle strategy preferred.
    """
    opt = BESSOptimizer(power_mw=100.0, energy_mwh=200.0, degradation_cost_per_mwh=2000.0)
    T = 96
    prices = np.full(T, 200.0)
    prices[48:] = 400.0  # Spread is 200, but degradation cost is 2000

    res = opt.optimize_dispatch(prices, interval_minutes=15)

    assert res["status"] == "OPTIMAL"
    # Should choose to idle because cycling is unprofitable
    assert res["cell_throughput_q_mwh"] < 1e-4
    assert abs(res["net_profit"]) < 1e-4


def test_v2_case_7_time_resolution_invariance():
    """
    Scenario 7: 15-min / 30-min / 60-min resolution invariance.
    Same 24-hour step profile gives consistent energy throughput and financial yield.
    """
    # 24-hour step: 0-12h low price (100 RMB), 12-24h high price (600 RMB)
    opt = BESSOptimizer(power_mw=100.0, energy_mwh=200.0, degradation_cost_per_mwh=30.0)

    # 15-min: 96 steps
    prices_15 = np.array([100.0] * 48 + [600.0] * 48)
    res_15 = opt.optimize_dispatch(prices_15, interval_minutes=15)

    # 30-min: 48 steps
    prices_30 = np.array([100.0] * 24 + [600.0] * 24)
    res_30 = opt.optimize_dispatch(prices_30, interval_minutes=30)

    # 60-min: 24 steps
    prices_60 = np.array([100.0] * 12 + [600.0] * 12)
    res_60 = opt.optimize_dispatch(prices_60, interval_minutes=60)

    # Energy throughput and net profits should match within 0.1%
    assert abs(res_15["net_profit"] - res_30["net_profit"]) < 50.0
    assert abs(res_15["net_profit"] - res_60["net_profit"]) < 100.0
    assert abs(res_15["cell_throughput_q_mwh"] - res_30["cell_throughput_q_mwh"]) < 1.0


def test_v2_case_8_enumerable_hand_calculation():
    """
    Scenario 8: Small enumerable scenario matching independent hand calculation.
    T = 4, dt = 1.0h, P_max = 100MW, E_nom = 200MWh, eta = 1.0, k_deg = 0.
    E_min = 0, E_max = 200, E_0 = E_T = 100.
    prices = [10.0, 100.0, 10.0, 100.0].
    Hand calculation:
      t=0: charge 100 MWh at 10 RMB/MWh -> cost 1000 RMB, E=200
      t=1: discharge 100 MWh at 100 RMB/MWh -> rev 10000 RMB, E=100
      t=2: charge 100 MWh at 10 RMB/MWh -> cost 1000 RMB, E=200
      t=3: discharge 100 MWh at 100 RMB/MWh -> rev 10000 RMB, E=100
    Total Net Profit = (10000 - 1000) + (10000 - 1000) = 18,000.0 RMB.
    """
    opt = BESSOptimizer(
        power_mw=100.0,
        energy_mwh=200.0,
        charge_efficiency=1.0,
        discharge_efficiency=1.0,
        soc_min=0.0,
        soc_max=1.0,
        soc_initial=0.5,
        soc_final=0.5,
        degradation_cost_per_mwh=0.0
    )
    prices = np.array([10.0, 100.0, 10.0, 100.0])
    res = opt.optimize_dispatch(prices, interval_minutes=60)

    assert res["status"] == "OPTIMAL"
    assert abs(res["net_profit"] - 18000.0) < 1e-2
    assert abs(res["charging_cost"] - 2000.0) < 1e-2
    assert abs(res["gross_revenue"] - 20000.0) < 1e-2


def test_battery_degradation_dual_efc():
    """Tests degradation calculation and dual EFC metrics."""
    deg = BatteryDegradationModel(
        degradation_cost_per_mwh=30.0,
        nominal_energy_mwh=200.0,
        soc_min=0.10,
        soc_max=0.90
    )
    # 100 MWh charge, 100 MWh discharge with eta_c=eta_d=sqrt(0.85)=0.921954
    # Throughput Q = 0.921954 * 100 + 100 / 0.921954 = 92.1954 + 108.4652 = 200.66 MWh
    res = deg.calculate_degradation(charge_energy_mwh=100.0, discharge_energy_mwh=100.0)

    assert res["degradation_cost_rmb"] > 0
    assert res["efc_rated"] > 0
    assert res["efc_usable"] > res["efc_rated"]  # usable EFC is higher than rated EFC because usable < nominal


def test_sensitivity_analyzer(optimizer):
    """Tests the single-factor sensitivity analyzer."""
    prices = np.full(96, 250.0)
    prices[44:52] = -80.0
    prices[76:84] = 1200.0

    analyzer = SensitivityAnalyzer()
    res = analyzer.analyze(prices, interval_minutes=15)

    assert "efficiency" in res
    assert len(res["efficiency"]) == 3
    assert "duration" in res
    assert len(res["duration"]) == 3
    assert "degradation_cost" in res
    assert len(res["degradation_cost"]) == 3
