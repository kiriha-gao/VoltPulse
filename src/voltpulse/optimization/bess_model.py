from typing import Dict, Any, List, Optional
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

from voltpulse.optimization.degradation import BatteryDegradationModel
from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.optimization.bess")


class BESSModelSanityError(Exception):
    """Raised when BESS optimization results violate physical constraints."""
    pass


class BESSOptimizer:
    """
    Mixed-Integer Linear Programming (MILP) Battery Energy Storage System (BESS) Optimizer
    conforming strictly to VoltPulse Specification V2.0 Section 10.2 & 10.3.

    Variables:
      - c_t: AC charging power (MW), continuous in [0, P_c]
      - d_t: AC discharging power (MW), continuous in [0, P_d]
      - u_t: Binary charging status indicator in {0, 1}
      - E_t: Cell-side energy state (MWh), continuous in [E_min, E_max]

    Mutual Exclusion:
      0 <= c_t <= P_c * u_t
      0 <= d_t <= P_d * (1 - u_t)
      Mathematically guarantees simultaneous charge and discharge is strictly ZERO under any price.

    Cell-side Bidirectional Throughput & Objective:
      Q = sum_t (eta_c * c_t + d_t / eta_d) * dt
      max sum_t p_t * (d_t - c_t) * dt - k_deg * Q
    """

    def __init__(self, power_mw: float = 100.0, energy_mwh: float = 200.0,
                 charge_efficiency: Optional[float] = None,
                 discharge_efficiency: Optional[float] = None,
                 soc_min: float = 0.10, soc_max: float = 0.90,
                 soc_initial: float = 0.50, soc_final: float = 0.50,
                 degradation_cost_per_mwh: float = 30.0):
        self.power_mw = float(power_mw)
        self.energy_mwh = float(energy_mwh)

        # Default round-trip efficiency 85%, eta_c = eta_d = sqrt(0.85) per V2 Section 10.1
        default_eff = float(np.sqrt(0.85))
        self.charge_eff = float(charge_efficiency) if charge_efficiency is not None else default_eff
        self.discharge_eff = float(discharge_efficiency) if discharge_efficiency is not None else default_eff
        self.round_trip_eff = self.charge_eff * self.discharge_eff

        self.soc_min = float(soc_min)
        self.soc_max = float(soc_max)
        self.soc_initial = float(soc_initial)
        self.soc_final = float(soc_final)
        self.degradation_cost_per_mwh = float(degradation_cost_per_mwh)

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

    def optimize_dispatch(self, prices: np.ndarray, interval_minutes: int = 15) -> Dict[str, Any]:
        """
        Solves the MILP optimal dispatch problem using HiGHS MIP solver.

        Args:
            prices: 1D array of spot prices in RMB/MWh of length T.
            interval_minutes: duration per interval in minutes (default 15).

        Returns:
            Dictionary containing optimal schedule, financial metrics, and validation status.
        """
        T = len(prices)
        dt = float(interval_minutes) / 60.0

        # Variable index layout (Length 4*T):
        # c_t (charge power MW):      [0 : T]
        # d_t (discharge power MW):   [T : 2*T]
        # u_t (binary charge state):  [2*T : 3*T]
        # E_t (cell energy end of t): [3*T : 4*T]
        num_vars = 4 * T

        # Integrality vector: 0 = continuous, 1 = integer (binary)
        integrality = np.zeros(num_vars)
        integrality[2 * T : 3 * T] = 1

        # Bounds
        lb = np.zeros(num_vars)
        ub = np.zeros(num_vars)
        lb[0 : T] = 0.0
        ub[0 : T] = self.power_mw
        lb[T : 2 * T] = 0.0
        ub[T : 2 * T] = self.power_mw
        lb[2 * T : 3 * T] = 0
        ub[2 * T : 3 * T] = 1
        lb[3 * T : 4 * T] = self.e_min
        ub[3 * T : 4 * T] = self.e_max
        bounds = Bounds(lb, ub)

        # Objective function (minimizing negative profit):
        # min sum_t dt * [ (p_t + k_deg * eta_c) * c_t + (-p_t + k_deg / eta_d) * d_t ]
        c_obj = np.zeros(num_vars)
        for t in range(T):
            p_t = float(prices[t])
            c_obj[t] = dt * (p_t + self.degradation_cost_per_mwh * self.charge_eff)
            c_obj[T + t] = dt * (-p_t + self.degradation_cost_per_mwh / self.discharge_eff)

        # Constraints matrix: 3*T + 1 rows
        # 1. c_t - P_c * u_t <= 0 (T rows)
        # 2. d_t + P_d * u_t <= P_d (T rows)
        # 3. State-of-Charge dynamics (T rows)
        # 4. Terminal SOC constraint E(T) = e_final (1 row)
        num_constraints = 3 * T + 1
        A = np.zeros((num_constraints, num_vars))
        lhs = np.zeros(num_constraints)
        rhs = np.zeros(num_constraints)

        # 1. Charge mutual exclusion: c_t - P_c * u_t <= 0
        for t in range(T):
            A[t, t] = 1.0
            A[t, 2 * T + t] = -self.power_mw
            lhs[t] = -np.inf
            rhs[t] = 0.0

        # 2. Discharge mutual exclusion: d_t + P_d * u_t <= P_d
        for t in range(T):
            row_idx = T + t
            A[row_idx, T + t] = 1.0
            A[row_idx, 2 * T + t] = self.power_mw
            lhs[row_idx] = -np.inf
            rhs[row_idx] = self.power_mw

        # 3. Energy dynamics:
        # E(t+1) - E(t) - eta_c * dt * c_t + (dt / eta_d) * d_t = 0
        for t in range(T):
            row_idx = 2 * T + t
            A[row_idx, t] = -self.charge_eff * dt
            A[row_idx, T + t] = dt / self.discharge_eff
            A[row_idx, 3 * T + t] = 1.0
            if t == 0:
                lhs[row_idx] = self.e_initial
                rhs[row_idx] = self.e_initial
            else:
                A[row_idx, 3 * T + t - 1] = -1.0
                lhs[row_idx] = 0.0
                rhs[row_idx] = 0.0

        # 4. Terminal energy constraint: E(T) = e_final
        row_idx = 3 * T
        A[row_idx, 4 * T - 1] = 1.0
        lhs[row_idx] = self.e_final
        rhs[row_idx] = self.e_final

        constraints = LinearConstraint(A, lhs, rhs)

        # Solve with SciPy HiGHS MILP solver
        res = milp(c=c_obj, integrality=integrality, bounds=bounds, constraints=constraints)

        if not res.success:
            raise RuntimeError(f"BESS MILP Optimization failed: {res.status} - {getattr(res, 'message', 'Solver error')}")

        # Extract optimal schedules
        p_ch = res.x[0 : T]
        p_dis = res.x[T : 2 * T]
        u_state = res.x[2 * T : 3 * T]
        energy_traj = res.x[3 * T : 4 * T]
        soc_traj = energy_traj / self.energy_mwh

        # Energy & Throughput accounting
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

        result = {
            "status": "OPTIMAL",
            "solver": "HiGHS_MILP",
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
            "u_state": [int(round(u)) for u in u_state],
            "soc": soc_traj.tolist(),
            "min_soc": round(float(np.min(soc_traj)), 4),
            "max_soc": round(float(np.max(soc_traj)), 4),
            "final_soc": round(float(soc_traj[-1]), 4)
        }

        # Rigorous Sanity Checks (V2.0 Section 11.2)
        self.verify_sanity(result, p_ch, p_dis, energy_traj, dt)
        return result

    def verify_sanity(self, res: Dict[str, Any], p_ch: np.ndarray, p_dis: np.ndarray,
                      energy_traj: np.ndarray, dt: float, tol: float = 1e-3):
        """
        Executes strict Sanity Checks conforming to V2.0 Section 11.2.
        Throws BESSModelSanityError if physical constraints are violated.
        """
        violations = []

        # 1. Power Limits
        if np.any(p_ch > self.power_mw + tol) or np.any(p_ch < -tol):
            violations.append(f"Charging power breached [0, {self.power_mw}]")
        if np.any(p_dis > self.power_mw + tol) or np.any(p_dis < -tol):
            violations.append(f"Discharging power breached [0, {self.power_mw}]")

        # 2. SOC Limits
        if np.any(energy_traj < self.e_min - tol) or np.any(energy_traj > self.e_max + tol):
            violations.append(f"Energy level breached [{self.e_min}, {self.e_max}]")

        # 3. Final SOC Constraint
        if abs(energy_traj[-1] - self.e_final) > tol:
            violations.append(f"Terminal energy {energy_traj[-1]:.3f} != target {self.e_final:.3f}")

        # 4. Simultaneous Charge & Discharge Check (guaranteed by binary variable u_t)
        simultaneous = np.minimum(p_ch, p_dis)
        if np.any(simultaneous > 1e-3):
            max_simult = np.max(simultaneous)
            violations.append(f"Simultaneous charge/discharge detected (max {max_simult:.4f} MW)")

        # 5. Energy Balance Check
        T = len(p_ch)
        for t in range(T):
            prev_e = self.e_initial if t == 0 else energy_traj[t - 1]
            expected_e = prev_e + self.charge_eff * p_ch[t] * dt - (p_dis[t] * dt) / self.discharge_eff
            if abs(energy_traj[t] - expected_e) > tol:
                violations.append(f"Energy balance violated at t={t}: actual {energy_traj[t]:.4f} vs expected {expected_e:.4f}")
                break

        if violations:
            logger.error(f"Sanity Check FAILED: {violations}")
            raise BESSModelSanityError(f"Model sanity violations detected: {violations}")
