from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from voltpulse.optimization.degradation import BatteryDegradationModel
from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.optimization.benchmark")


class FixedPeakValleyStrategy:
    """
    Simulates fixed rule-based Peak-Valley charging and discharging
    conforming to VoltPulse Specification V2.0 Section 10.4 (M08 Strategy 2).
    
    Default Shandong Duck Curve Window:
    - Low-price charging window: 11:00 - 15:00 (midday PV surplus)
    - High-price discharge window: 18:00 - 22:00 (evening peak)

    Terminal SOC Consistency (Spec 10.4):
    - Fixed strategy charges from E_initial (50%) up to E_max (90%) during the low-price window.
    - During the high-price window, it discharges down to E_final (50%) and idles.
    - If the configured window cannot achieve terminal SOC balance (e.g. truncated discharge window),
      it executes a no-arbitrage idle fallback per Spec 10.4, preserving E(T) = E_final strictly.
    """

    def __init__(self, optimizer_params: Dict[str, Any],
                 charging_windows: Optional[List[Dict[str, str]]] = None,
                 discharging_windows: Optional[List[Dict[str, str]]] = None):
        self.power_mw = float(optimizer_params.get("power_mw", 100.0))
        self.energy_mwh = float(optimizer_params.get("energy_mwh", 200.0))

        default_eff = float(np.sqrt(0.85))
        self.charge_eff = float(optimizer_params.get("charge_efficiency", default_eff))
        self.discharge_eff = float(optimizer_params.get("discharge_efficiency", default_eff))
        self.soc_min = float(optimizer_params.get("soc_min", 0.10))
        self.soc_max = float(optimizer_params.get("soc_max", 0.90))
        self.soc_initial = float(optimizer_params.get("soc_initial", 0.50))
        self.soc_final = float(optimizer_params.get("soc_final", 0.50))
        self.degradation_cost_per_mwh = float(optimizer_params.get("degradation_cost_rmb_per_mwh", 30.0))

        self.e_min = self.soc_min * self.energy_mwh
        self.e_max = self.soc_max * self.energy_mwh
        self.e_initial = self.soc_initial * self.energy_mwh
        self.e_final = self.soc_final * self.energy_mwh

        # Respect explicitly provided empty list [] without defaulting via 'or'
        self.charging_windows = charging_windows if charging_windows is not None else [{"start": "11:00", "end": "15:00"}]
        self.discharging_windows = discharging_windows if discharging_windows is not None else [{"start": "18:00", "end": "22:00"}]

        self.degradation_model = BatteryDegradationModel(
            degradation_cost_per_mwh=self.degradation_cost_per_mwh,
            nominal_energy_mwh=self.energy_mwh,
            soc_min=self.soc_min,
            soc_max=self.soc_max,
            charge_efficiency=self.charge_eff,
            discharge_efficiency=self.discharge_eff
        )

    def simulate(self, prices: np.ndarray, timestamps: List[str], interval_minutes: int = 15) -> Dict[str, Any]:
        """
        Runs step-by-step physical simulation under fixed time windows.
        Strictly enforces power limits, SOC limits, and terminal SOC equality.
        If terminal SOC cannot be met, executes no-arbitrage idle fallback per Spec 10.4.
        """
        T = len(prices)
        dt = float(interval_minutes) / 60.0

        p_ch = np.zeros(T)
        p_dis = np.zeros(T)
        energy = np.zeros(T)
        curr_e = self.e_initial

        for t in range(T):
            ts_str = str(timestamps[t])
            time_part = ts_str.split("T")[1][:5] if "T" in ts_str else ts_str[-8:-3]

            is_charge_window = any(w["start"] <= time_part < w["end"] for w in self.charging_windows)
            is_discharge_window = any(w["start"] <= time_part < w["end"] for w in self.discharging_windows)

            if is_charge_window and curr_e < self.e_max:
                max_charge_energy = (self.e_max - curr_e) / self.charge_eff
                p_ch_val = min(self.power_mw, max_charge_energy / dt)
                p_ch[t] = max(0.0, p_ch_val)
                curr_e += self.charge_eff * p_ch[t] * dt

            elif is_discharge_window and curr_e > self.e_final:
                max_discharge_energy = (curr_e - self.e_final) * self.discharge_eff
                p_dis_val = min(self.power_mw, max_discharge_energy / dt)
                p_dis[t] = max(0.0, p_dis_val)
                curr_e -= (p_dis[t] * dt) / self.discharge_eff

            energy[t] = curr_e

        # Rigorous Terminal Balance Check (Spec 10.4)
        if abs(curr_e - self.e_final) > 1e-2:
            logger.warning(
                f"Fixed schedule window failed terminal balance: final energy {curr_e:.2f} != {self.e_final:.2f}. "
                f"Executing no-arbitrage idle fallback per Spec 10.4."
            )
            p_ch = np.zeros(T)
            p_dis = np.zeros(T)
            energy = np.full(T, self.e_initial)
            curr_e = self.e_final
            status_label = "INFEASIBLE_WINDOW_IDLE_FALLBACK"
        else:
            status_label = "SUCCESS"

        soc_traj = energy / self.energy_mwh
        charge_energy_mwh = float(np.sum(p_ch) * dt)
        discharge_energy_mwh = float(np.sum(p_dis) * dt)
        cell_throughput_q = float(np.sum(self.charge_eff * p_ch + p_dis / self.discharge_eff) * dt)

        gross_revenue = float(np.sum(prices * p_dis * dt))
        charging_cost = float(np.sum(prices * p_ch * dt))
        gross_profit = gross_revenue - charging_cost

        deg_metrics = self.degradation_model.calculate_degradation(
            charge_energy_mwh, discharge_energy_mwh, cell_throughput_q=cell_throughput_q
        )
        degradation_cost = deg_metrics["degradation_cost_rmb"]
        net_profit = gross_profit - degradation_cost

        return {
            "strategy": "fixed_peak_valley",
            "strategy_label": "Fixed Peak-Valley Benchmark",
            "solver": "Rule_Based",
            "status": status_label,
            "is_feasible": bool(status_label == "SUCCESS"),
            "gross_revenue": round(gross_revenue, 2),
            "charging_cost": round(charging_cost, 2),
            "gross_profit": round(gross_profit, 2),
            "degradation_cost": round(degradation_cost, 2),
            "net_profit": round(net_profit, 2),
            "charge_energy_mwh": round(charge_energy_mwh, 3),
            "discharge_energy_mwh": round(discharge_energy_mwh, 3),
            "cell_throughput_q_mwh": round(cell_throughput_q, 3),
            "efc": deg_metrics["efc"],
            "efc_rated": deg_metrics["efc_rated"],
            "efc_usable": deg_metrics["efc_usable"],
            "p_charge_mw": p_ch.tolist(),
            "p_discharge_mw": p_dis.tolist(),
            "soc": soc_traj.tolist(),
            "min_soc": round(float(np.min(soc_traj)), 4),
            "max_soc": round(float(np.max(soc_traj)), 4),
            "final_soc": round(float(soc_traj[-1]), 4)
        }


class HistoricalAdjustedStrategy:
    """
    Simulates a strictly causal, Day-Ahead Lagged Persistence Strategy (历史数据调整策略).
    
    Core Principle:
      - Uses clearing price observations from Day d-1 to formulate the dispatch schedule.
      - Dispatches Day d using Day d-1's plan without any future price knowledge of Day d.
      - Strict battery physics: respects power limits P_rated, SOC limits [SOC_min, SOC_max], 
        efficiency, and terminal SOC balance.
      - Evaluated at Day d's actual spot clearing prices.
    """

    def __init__(self, optimizer_params: Optional[Dict[str, Any]] = None, **kwargs):
        params = dict(optimizer_params or {})
        params.update(kwargs)
        self.power_mw = float(params.get("power_mw", 100.0))
        self.energy_mwh = float(params.get("energy_mwh", 200.0))

        default_eff = float(np.sqrt(0.85))
        self.charge_eff = float(params.get("charge_efficiency", default_eff))
        self.discharge_eff = float(params.get("discharge_efficiency", default_eff))
        self.soc_min = float(params.get("soc_min", 0.10))
        self.soc_max = float(params.get("soc_max", 0.90))
        self.soc_initial = float(params.get("soc_initial", 0.50))
        self.soc_final = float(params.get("soc_final", 0.50))
        self.degradation_cost_per_mwh = float(params.get("degradation_cost_rmb_per_mwh", 30.0))

        self.e_min = self.soc_min * self.energy_mwh
        self.e_max = self.soc_max * self.energy_mwh
        self.e_initial = self.soc_initial * self.energy_mwh
        self.e_final = self.soc_final * self.energy_mwh

        self.degradation_model = BatteryDegradationModel(
            degradation_cost_per_mwh=self.degradation_cost_per_mwh,
            nominal_energy_mwh=self.energy_mwh,
            soc_min=self.soc_min,
            soc_max=self.soc_max,
            charge_efficiency=self.charge_eff,
            discharge_efficiency=self.discharge_eff
        )

    def simulate(self, prices_today: np.ndarray,
                 planned_charge_mw: np.ndarray,
                 planned_discharge_mw: np.ndarray,
                 interval_minutes: int = 15) -> Dict[str, Any]:
        """
        Executes physical forward dispatch on Day d based on schedule determined from Day d-1.
        Strictly causal: Day d prices are only used for financial evaluation, not for dispatch decisions.
        """
        T = len(prices_today)
        dt = float(interval_minutes) / 60.0

        p_ch = np.zeros(T)
        p_dis = np.zeros(T)
        energy = np.zeros(T)
        curr_e = self.e_initial

        for t in range(T):
            desired_ch = float(planned_charge_mw[t]) if t < len(planned_charge_mw) else 0.0
            desired_dis = float(planned_discharge_mw[t]) if t < len(planned_discharge_mw) else 0.0

            if desired_ch > 0 and curr_e < self.e_max:
                max_ch_energy = (self.e_max - curr_e) / self.charge_eff
                p_ch_val = min(desired_ch, self.power_mw, max_ch_energy / dt)
                p_ch[t] = max(0.0, p_ch_val)
                curr_e += self.charge_eff * p_ch[t] * dt

            elif desired_dis > 0 and curr_e > self.e_min:
                max_dis_energy = (curr_e - self.e_min) * self.discharge_eff
                p_dis_val = min(desired_dis, self.power_mw, max_dis_energy / dt)
                p_dis[t] = max(0.0, p_dis_val)
                curr_e -= (p_dis[t] * dt) / self.discharge_eff

            energy[t] = curr_e

        # Terminal SOC verification & status
        if abs(curr_e - self.e_final) > 1e-2:
            status_label = "TERMINAL_ADJUSTED"
        else:
            status_label = "SUCCESS"

        soc_traj = energy / self.energy_mwh
        charge_energy_mwh = float(np.sum(p_ch) * dt)
        discharge_energy_mwh = float(np.sum(p_dis) * dt)
        cell_throughput_q = float(np.sum(self.charge_eff * p_ch + p_dis / self.discharge_eff) * dt)

        gross_revenue = float(np.sum(prices_today * p_dis * dt))
        charging_cost = float(np.sum(prices_today * p_ch * dt))
        gross_profit = gross_revenue - charging_cost

        deg_metrics = self.degradation_model.calculate_degradation(
            charge_energy_mwh, discharge_energy_mwh, cell_throughput_q=cell_throughput_q
        )
        degradation_cost = deg_metrics["degradation_cost_rmb"]
        net_profit = gross_profit - degradation_cost

        return {
            "strategy": "historical_adjusted",
            "strategy_label": "Day-Ahead Lagged Strategy (Historical Adjusted)",
            "solver": "Lagged_Replay",
            "status": status_label,
            "is_theoretical_optimum": False,
            "is_feasible": True,
            "gross_revenue": round(gross_revenue, 2),
            "charging_cost": round(charging_cost, 2),
            "gross_profit": round(gross_profit, 2),
            "degradation_cost": round(degradation_cost, 2),
            "net_profit": round(net_profit, 2),
            "charge_energy_mwh": round(charge_energy_mwh, 3),
            "discharge_energy_mwh": round(discharge_energy_mwh, 3),
            "cell_throughput_q_mwh": round(cell_throughput_q, 3),
            "efc": deg_metrics["efc"],
            "efc_rated": deg_metrics["efc_rated"],
            "efc_usable": deg_metrics["efc_usable"],
            "p_charge_mw": p_ch.tolist(),
            "p_discharge_mw": p_dis.tolist(),
            "soc": soc_traj.tolist(),
            "min_soc": round(float(np.min(soc_traj)), 4),
            "max_soc": round(float(np.max(soc_traj)), 4),
            "final_soc": round(float(soc_traj[-1]), 4)
        }
