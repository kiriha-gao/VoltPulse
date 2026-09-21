from typing import Dict, Any, List
import numpy as np
import pandas as pd

from voltpulse.optimization.bess_model import BESSOptimizer
from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.optimization.sensitivity")


class SensitivityAnalyzer:
    """
    Single-Factor Sensitivity Analysis conforming strictly to
    VoltPulse Specification V2.0 Section 18.

    Variations tested:
      1. Round-Trip Efficiency: 85%, 88%, 90%
      2. Rated Duration (C-rate): 1h (100MW/100MWh), 2h (100MW/200MWh), 4h (100MW/400MWh)
      3. Degradation Cost: 0, 30, 60 RMB/MWh cell-side throughput

    Note per Spec Section 18:
      Results with different rated energy cannot be directly compared as investment return quality.
    """

    def __init__(self, base_power_mw: float = 100.0, base_energy_mwh: float = 200.0,
                 base_efficiency: float = 0.85, base_deg_cost: float = 30.0,
                 soc_min: float = 0.10, soc_max: float = 0.90,
                 soc_initial: float = 0.50, soc_final: float = 0.50):
        self.base_power_mw = float(base_power_mw)
        self.base_energy_mwh = float(base_energy_mwh)
        self.base_efficiency = float(base_efficiency)
        self.base_deg_cost = float(base_deg_cost)
        self.soc_min = float(soc_min)
        self.soc_max = float(soc_max)
        self.soc_initial = float(soc_initial)
        self.soc_final = float(soc_final)

    @classmethod
    def from_config(cls, storage_config: Dict[str, Any]) -> "SensitivityAnalyzer":
        eff = storage_config.get("round_trip_efficiency")
        if eff is None and "charge_efficiency" in storage_config and "discharge_efficiency" in storage_config:
            eff = float(storage_config["charge_efficiency"]) * float(storage_config["discharge_efficiency"])
        return cls(
            base_power_mw=storage_config.get("power_mw", 100.0),
            base_energy_mwh=storage_config.get("energy_mwh", 200.0),
            base_efficiency=eff or 0.85,
            base_deg_cost=storage_config.get("degradation_cost_rmb_per_mwh", 30.0),
            soc_min=storage_config.get("soc_min", 0.10),
            soc_max=storage_config.get("soc_max", 0.90),
            soc_initial=storage_config.get("soc_initial", 0.50),
            soc_final=storage_config.get("soc_final", 0.50),
        )

    def analyze(self, prices: np.ndarray, interval_minutes: int = 15) -> Dict[str, List[Dict[str, Any]]]:
        """
        Runs single-factor variations on the provided price vector.
        Returns dictionary of results grouped by factor.
        """
        results: Dict[str, List[Dict[str, Any]]] = {
            "efficiency": [],
            "duration": [],
            "degradation_cost": []
        }

        # 1. Round-Trip Efficiency Variations: 85%, 88%, 90%
        for eff in [0.85, 0.88, 0.90]:
            one_way_eff = float(np.sqrt(eff))
            opt = BESSOptimizer(
                power_mw=self.base_power_mw,
                energy_mwh=self.base_energy_mwh,
                charge_efficiency=one_way_eff,
                discharge_efficiency=one_way_eff,
                soc_min=self.soc_min,
                soc_max=self.soc_max,
                soc_initial=self.soc_initial,
                soc_final=self.soc_final,
                degradation_cost_per_mwh=self.base_deg_cost
            )
            res = opt.optimize_dispatch(prices, interval_minutes=interval_minutes)
            results["efficiency"].append({
                "factor_value": f"{int(eff * 100)}%",
                "efficiency": eff,
                "net_profit": res["net_profit"],
                "gross_revenue": res["gross_revenue"],
                "charging_cost": res["charging_cost"],
                "cell_throughput_q_mwh": res["cell_throughput_q_mwh"],
                "efc_rated": res["efc_rated"]
            })

        # 2. Rated Duration Variations: 1h, 2h, 4h (100MW fixed)
        for duration_h, energy_mwh in [(1.0, 100.0), (2.0, 200.0), (4.0, 400.0)]:
            one_way_eff = float(np.sqrt(self.base_efficiency))
            opt = BESSOptimizer(
                power_mw=self.base_power_mw,
                energy_mwh=energy_mwh,
                charge_efficiency=one_way_eff,
                discharge_efficiency=one_way_eff,
                soc_min=self.soc_min,
                soc_max=self.soc_max,
                soc_initial=self.soc_initial,
                soc_final=self.soc_final,
                degradation_cost_per_mwh=self.base_deg_cost
            )
            res = opt.optimize_dispatch(prices, interval_minutes=interval_minutes)
            results["duration"].append({
                "factor_value": f"{int(duration_h)}h ({int(energy_mwh)}MWh)",
                "duration_hours": duration_h,
                "energy_mwh": energy_mwh,
                "net_profit": res["net_profit"],
                "gross_revenue": res["gross_revenue"],
                "charging_cost": res["charging_cost"],
                "cell_throughput_q_mwh": res["cell_throughput_q_mwh"],
                "efc_rated": res["efc_rated"]
            })

        # 3. Degradation Cost Variations: 0, 30, 60 RMB/MWh
        for deg_cost in [0.0, 30.0, 60.0]:
            one_way_eff = float(np.sqrt(self.base_efficiency))
            opt = BESSOptimizer(
                power_mw=self.base_power_mw,
                energy_mwh=self.base_energy_mwh,
                charge_efficiency=one_way_eff,
                discharge_efficiency=one_way_eff,
                soc_min=self.soc_min,
                soc_max=self.soc_max,
                soc_initial=self.soc_initial,
                soc_final=self.soc_final,
                degradation_cost_per_mwh=deg_cost
            )
            res = opt.optimize_dispatch(prices, interval_minutes=interval_minutes)
            results["degradation_cost"].append({
                "factor_value": f"{int(deg_cost)} RMB/MWh",
                "deg_cost_rmb": deg_cost,
                "net_profit": res["net_profit"],
                "gross_revenue": res["gross_revenue"],
                "charging_cost": res["charging_cost"],
                "degradation_cost": res["degradation_cost"],
                "cell_throughput_q_mwh": res["cell_throughput_q_mwh"],
                "efc_rated": res["efc_rated"]
            })

        return results
