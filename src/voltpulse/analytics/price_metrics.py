from typing import Dict, Any, List
import pandas as pd
import numpy as np
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.analytics.price")


class PriceMetricsCalculator:
    """
    Computes daily price metrics conforming strictly to
    VoltPulse Specification Section 9 (M04).
    """

    @staticmethod
    def calculate_daily_metrics(day_df: pd.DataFrame, low_threshold: float = 100.0, high_threshold: float = 500.0) -> Dict[str, Any]:
        """
        Computes price statistical metrics for a single date's spot price series.
        Expects day_df to contain 'price_rmb_mwh', 'market', 'date'.
        """
        if day_df.empty:
            raise ValueError("Cannot calculate price metrics on empty dataframe")

        prices = day_df["price_rmb_mwh"].astype(float).values
        market = str(day_df["market"].iloc[0])
        trade_date = str(day_df["date"].iloc[0])

        mean_price = float(np.mean(prices))
        median_price = float(np.median(prices))
        max_price = float(np.max(prices))
        min_price = float(np.min(prices))
        peak_valley_spread = float(max_price - min_price)
        std_price = float(np.std(prices))

        # Quantiles
        p05 = float(np.percentile(prices, 5))
        p25 = float(np.percentile(prices, 25))
        p75 = float(np.percentile(prices, 75))
        p95 = float(np.percentile(prices, 95))

        # Negative price metrics
        neg_mask = prices < 0.0
        neg_count = int(np.sum(neg_mask))
        neg_ratio = float(neg_count / len(prices))

        # Interval duration in hours (e.g. 15 min = 0.25h)
        interval_hours = float(day_df["interval"].iloc[0]) / 60.0 if "interval" in day_df.columns else 0.25
        low_duration_hours = float(np.sum(prices <= low_threshold) * interval_hours)
        high_duration_hours = float(np.sum(prices >= high_threshold) * interval_hours)

        return {
            "market": market,
            "date": trade_date,
            "mean_price": round(mean_price, 2),
            "median_price": round(median_price, 2),
            "max_price": round(max_price, 2),
            "min_price": round(min_price, 2),
            "peak_valley_spread": round(peak_valley_spread, 2),
            "std_price": round(std_price, 2),
            "p05": round(p05, 2),
            "p25": round(p25, 2),
            "p75": round(p75, 2),
            "p95": round(p95, 2),
            "negative_price_count": neg_count,
            "negative_price_ratio": round(neg_ratio, 4),
            "low_price_duration_hours": round(low_duration_hours, 2),
            "high_price_duration_hours": round(high_duration_hours, 2),
            "total_periods": len(prices)
        }

    @staticmethod
    def compute_and_save_all(df_all: pd.DataFrame, output_parquet: Path) -> pd.DataFrame:
        """
        Groups all historical spot prices by (market, date) and computes
        daily metrics, saving them to data/results/daily_metrics.parquet.
        """
        if df_all.empty:
            logger.warning("Empty dataframe provided to compute_and_save_all")
            return pd.DataFrame()

        results = []
        for (mkt, dt), group in df_all.groupby(["market", "date"]):
            m = PriceMetricsCalculator.calculate_daily_metrics(group)
            results.append(m)

        metrics_df = pd.DataFrame(results).sort_values(by=["market", "date"]).reset_index(drop=True)

        output_path = Path(output_parquet)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pandas(metrics_df)
        pq.write_table(table, output_path, compression="SNAPPY")

        logger.info(f"Daily price metrics computed for {len(metrics_df)} days; saved to {output_path}")
        return metrics_df
