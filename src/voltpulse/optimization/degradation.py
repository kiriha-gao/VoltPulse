from typing import Dict, Any, Optional
import numpy as np


class BatteryDegradationModel:
    """
    Throughput-based Battery Degradation and Dual EFC Calculator conforming to
    VoltPulse Specification V2.0 Section 10.2 & 10.3 (M07).

    Equations:
      - Cell-side Bidirectional Throughput:
        Q = sum_t (eta_c * c_t + d_t / eta_d) * dt
      - Degradation Cost:
        Cost_deg = k_deg * Q
      - Rated Capacity Equivalent Full Cycles (EFC_rated):
        EFC_rated = Q / (2 * E_nom)
      - Usable Window Equivalent Full Cycles (EFC_usable):
        EFC_usable = Q / [2 * (E_max - E_min)]
    """

    def __init__(self, degradation_cost_per_mwh: float = 30.0, nominal_energy_mwh: float = 200.0,
                 soc_min: float = 0.10, soc_max: float = 0.90,
                 charge_efficiency: float = 0.921954, discharge_efficiency: float = 0.921954):
        self.degradation_cost_per_mwh = degradation_cost_per_mwh
        self.nominal_energy_mwh = nominal_energy_mwh
        self.soc_min = soc_min
        self.soc_max = soc_max
        self.charge_eff = charge_efficiency
        self.discharge_eff = discharge_efficiency

        self.usable_capacity_mwh = nominal_energy_mwh * (soc_max - soc_min)

    def calculate_throughput_q(self, charge_energy_mwh: float, discharge_energy_mwh: float) -> float:
        """
        Calculates cell-side bidirectional throughput Q:
        Q = eta_c * E_charge_ac + (E_discharge_ac / eta_d)
        """
        return float(self.charge_eff * charge_energy_mwh + discharge_energy_mwh / self.discharge_eff)

    def calculate_degradation(self, charge_energy_mwh: float, discharge_energy_mwh: float,
                              cell_throughput_q: Optional[float] = None) -> Dict[str, float]:
        """
        Calculates degradation cost and dual EFC metrics conforming to V2.0 Section 10.3.
        """
        if cell_throughput_q is not None:
            q = float(cell_throughput_q)
        else:
            q = self.calculate_throughput_q(charge_energy_mwh, discharge_energy_mwh)

        cost = q * self.degradation_cost_per_mwh

        # 1. Rated Capacity EFC: Q / (2 * E_nom)
        efc_rated = q / (2.0 * self.nominal_energy_mwh) if self.nominal_energy_mwh > 0 else 0.0

        # 2. Usable Capacity EFC: Q / [2 * (E_max - E_min)]
        efc_usable = q / (2.0 * self.usable_capacity_mwh) if self.usable_capacity_mwh > 0 else 0.0

        return {
            "degradation_cost_rmb": round(cost, 2),
            "throughput_mwh": round(q, 3),
            "cell_throughput_q_mwh": round(q, 3),
            "efc": round(efc_rated, 3),                # standard default EFC = rated EFC
            "efc_rated": round(efc_rated, 3),
            "efc_usable": round(efc_usable, 3),
            "usable_capacity_mwh": round(self.usable_capacity_mwh, 2),
            "nominal_energy_mwh": round(self.nominal_energy_mwh, 2)
        }
