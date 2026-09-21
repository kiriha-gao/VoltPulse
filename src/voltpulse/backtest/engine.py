from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from voltpulse.optimization.bess_model import BESSOptimizer
from voltpulse.optimization.benchmark import FixedPeakValleyStrategy
from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.backtest")


class BacktestEngine:
    """
    Day-by-day rolling backtest engine conforming to
    VoltPulse Specification V2.0 Section 10.4 & 10.5 (M09).
    """

    def __init__(self, storage_config: Dict[str, Any], benchmark_config: Optional[Dict[str, Any]] = None):
        self.storage_config = storage_config
        self.benchmark_config = benchmark_config or {}

        # Initialize HiGHS MILP Optimizer
        self.milp_optimizer = BESSOptimizer(
            power_mw=storage_config.get("power_mw", 100.0),
            energy_mwh=storage_config.get("energy_mwh", 200.0),
            charge_efficiency=storage_config.get("charge_efficiency"),
            discharge_efficiency=storage_config.get("discharge_efficiency"),
            soc_min=storage_config.get("soc_min", 0.10),
            soc_max=storage_config.get("soc_max", 0.90),
            soc_initial=storage_config.get("soc_initial", 0.50),
            soc_final=storage_config.get("soc_final", 0.50),
            degradation_cost_per_mwh=storage_config.get("degradation_cost_rmb_per_mwh", 30.0)
        )
        self.lp_optimizer = self.milp_optimizer

        fixed_cfg = self.benchmark_config.get("fixed_strategy", {})
        self.fixed_strategy = FixedPeakValleyStrategy(
            optimizer_params=storage_config,
            charging_windows=fixed_cfg.get("charging_windows"),
            discharging_windows=fixed_cfg.get("discharging_windows")
        )

    def run_backtest(self, prices_df: pd.DataFrame, market: str,
                     price_type: Optional[str] = None,
                     start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Executes rolling backtest across all complete valid days in prices_df.
        Strictly segregates price_type (DA vs RT) and enforces complete 24h intervals.
        """
        if prices_df is None or prices_df.empty:
            logger.warning("Empty prices dataframe provided for backtest")
            return pd.DataFrame()

        df = prices_df[prices_df["market"] == market].copy()

        # Strict Price Type Segregation & Unique Series per Spec 10.5
        if "price_type" in df.columns:
            if price_type:
                df = df[df["price_type"] == price_type]
                if df.empty:
                    logger.warning(f"No records matching market={market}, price_type={price_type}")
                    return pd.DataFrame()
            elif df["price_type"].nunique() > 1:
                logger.error("Input contains mixed price_types without explicit price_type parameter")
                return pd.DataFrame()

        # Enforce unique timeline per trading day (reject overlapping/duplicate timestamps)
        if "timestamp" in df.columns and df.duplicated(subset=["date", "timestamp"]).any():
            logger.error("Duplicate timestamps detected in prices_df; timeline must be strictly unique")
            return pd.DataFrame()

        if start_date:
            df = df[df["date"] >= start_date]
        if end_date:
            df = df[df["date"] <= end_date]

        unique_dates = sorted(df["date"].unique())
        logger.info(f"[{market}] Commencing backtest across {len(unique_dates)} candidate dates: {unique_dates[0] if unique_dates else 'None'} to {unique_dates[-1] if unique_dates else 'None'}")

        daily_records: List[Dict[str, Any]] = []

        # Initialize market-specific fixed strategy windows if configured
        fixed_cfg = self.benchmark_config.get("fixed_strategy", {})
        market_cfg = fixed_cfg.get("markets", {}).get(market, {})
        c_windows = market_cfg.get("charging_windows") if "charging_windows" in market_cfg else fixed_cfg.get("charging_windows")
        d_windows = market_cfg.get("discharging_windows") if "discharging_windows" in market_cfg else fixed_cfg.get("discharging_windows")
        market_fixed_strategy = FixedPeakValleyStrategy(
            optimizer_params=self.storage_config,
            charging_windows=c_windows,
            discharging_windows=d_windows
        )

        for d in unique_dates:
            day_df = df[df["date"] == d].sort_values(by="timestamp").reset_index(drop=True)
            interval_min = int(day_df["interval"].iloc[0]) if "interval" in day_df.columns else 15
            expected_periods = int(1440 / interval_min)

            # Strict complete-day requirement per Spec 10.5 (e.g. 96 for 15-min; reject partial half-days)
            if len(day_df) != expected_periods:
                logger.warning(f"Skipping incomplete date {d}: got {len(day_df)} periods, expected {expected_periods}")
                continue

            # Strict date-timestamp consistency check (reject mismatched date and timestamp)
            if "timestamp" in day_df.columns:
                ts_dates = pd.to_datetime(day_df["timestamp"]).dt.strftime("%Y-%m-%d")
                if (ts_dates != d).any():
                    logger.warning(f"Skipping date {d}: timestamps do not match date column")
                    continue

            prices = day_df["price_rmb_mwh"].values
            timestamps = day_df["timestamp"].tolist()

            # 1. Strategy 1: Ex-post Theoretical Optimum (HiGHS MILP)
            res_opt = self.milp_optimizer.optimize_dispatch(prices, interval_minutes=interval_min)
            daily_records.append({
                "market": market,
                "date": d,
                "price_type": price_type or (day_df["price_type"].iloc[0] if "price_type" in day_df.columns else "day_ahead"),
                "strategy": "perfect_foresight",
                "strategy_label": "Ex-post Theoretical Optimum (MILP)",
                "solver": "HiGHS_MILP",
                "is_theoretical_optimum": True,
                "is_feasible": res_opt.get("status") == "OPTIMAL",
                "status": res_opt.get("status", "OPTIMAL"),
                "gross_revenue": res_opt["gross_revenue"],
                "charging_cost": res_opt["charging_cost"],
                "gross_profit": res_opt["gross_profit"],
                "degradation_cost": res_opt["degradation_cost"],
                "net_profit": res_opt["net_profit"],
                "charge_energy_mwh": res_opt["charge_energy_mwh"],
                "discharge_energy_mwh": res_opt["discharge_energy_mwh"],
                "cell_throughput_q_mwh": res_opt["cell_throughput_q_mwh"],
                "efc": res_opt["efc"],
                "efc_rated": res_opt["efc_rated"],
                "efc_usable": res_opt["efc_usable"],
                "min_soc": res_opt["min_soc"],
                "max_soc": res_opt["max_soc"],
                "final_soc": res_opt["final_soc"]
            })

            # 2. Strategy 2: Fixed Peak-Valley Rule-based Benchmark Strategy
            res_fixed = market_fixed_strategy.simulate(prices, timestamps, interval_minutes=interval_min)
            daily_records.append({
                "market": market,
                "date": d,
                "price_type": price_type or day_df["price_type"].iloc[0] if "price_type" in day_df.columns else "day_ahead",
                "strategy": "fixed_peak_valley",
                "strategy_label": "Fixed Peak-Valley Benchmark",
                "solver": "Rule_Based",
                "is_theoretical_optimum": False,
                "is_feasible": res_fixed.get("is_feasible", res_fixed.get("status") == "SUCCESS"),
                "status": res_fixed.get("status", "SUCCESS"),
                "gross_revenue": res_fixed["gross_revenue"],
                "charging_cost": res_fixed["charging_cost"],
                "gross_profit": res_fixed["gross_profit"],
                "degradation_cost": res_fixed["degradation_cost"],
                "net_profit": res_fixed["net_profit"],
                "charge_energy_mwh": res_fixed["charge_energy_mwh"],
                "discharge_energy_mwh": res_fixed["discharge_energy_mwh"],
                "cell_throughput_q_mwh": res_fixed["cell_throughput_q_mwh"],
                "efc": res_fixed["efc"],
                "efc_rated": res_fixed["efc_rated"],
                "efc_usable": res_fixed["efc_usable"],
                "min_soc": res_fixed["min_soc"],
                "max_soc": res_fixed["max_soc"],
                "final_soc": res_fixed["final_soc"]
            })

        results_df = pd.DataFrame(daily_records)
        if results_df.empty:
            return results_df

        # Derived Analytics: Cumulative PnL, Rolling Mean, Profit per MWh / Cycle
        enhanced_records = []
        for strat, grp in results_df.groupby("strategy"):
            grp = grp.sort_values(by="date").reset_index(drop=True)
            grp["cumulative_pnl"] = round(grp["net_profit"].cumsum(), 2)
            grp["rolling_avg_pnl_30d"] = round(grp["net_profit"].rolling(window=30, min_periods=1).mean(), 2)
            grp["profit_per_mwh"] = np.where(
                grp["discharge_energy_mwh"] > 0,
                np.round(grp["net_profit"] / grp["discharge_energy_mwh"], 2),
                np.nan
            )
            grp["profit_per_cycle"] = np.where(
                grp["efc_rated"] > 0,
                np.round(grp["net_profit"] / grp["efc_rated"], 2),
                np.nan
            )
            enhanced_records.append(grp)

        final_df = pd.concat(enhanced_records, ignore_index=True)
        final_df = final_df.sort_values(by=["date", "strategy"]).reset_index(drop=True)
        return final_df

    @staticmethod
    def save_results(df: pd.DataFrame, output_path: Path):
        """Saves backtest dataframe to Parquet."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pandas(df)
        pq.write_table(table, p, compression="SNAPPY")
        logger.info(f"Backtest results saved: {len(df)} records at {p}")
