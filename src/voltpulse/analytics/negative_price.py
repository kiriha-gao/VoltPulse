from typing import Dict, Any, List
import pandas as pd
import numpy as np


class NegativePriceAnalyzer:
    """
    Negative Price Analysis conforming strictly to
    VoltPulse Specification Section 10 (M05).
    """

    @staticmethod
    def analyze_daily_negative_prices(day_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyzes negative electricity price characteristics for a single trade date.
        """
        if day_df.empty:
            return {
                "negative_price_periods": 0,
                "negative_price_hours": 0.0,
                "max_consecutive_hours": 0.0,
                "lowest_price": 0.0,
                "hourly_distribution": {}
            }

        df = day_df.sort_values(by="timestamp").copy()
        prices = df["price_rmb_mwh"].values
        interval_hours = float(df["interval"].iloc[0]) / 60.0 if "interval" in df.columns else 0.25

        neg_mask = (prices < 0.0)
        neg_count = int(np.sum(neg_mask))

        if neg_count == 0:
            return {
                "negative_price_periods": 0,
                "negative_price_hours": 0.0,
                "max_consecutive_hours": 0.0,
                "lowest_price": float(np.min(prices)),
                "hourly_distribution": {}
            }

        lowest_negative_price = float(np.min(prices))
        total_neg_hours = round(neg_count * interval_hours, 2)

        # Compute maximum consecutive negative periods
        max_consec = 0
        curr_consec = 0
        for is_neg in neg_mask:
            if is_neg:
                curr_consec += 1
                max_consec = max(max_consec, curr_consec)
            else:
                curr_consec = 0
        max_consecutive_hours = round(max_consec * interval_hours, 2)

        # Hourly distribution: count how many negative intervals fall in each hour [0..23]
        hourly_counts: Dict[int, int] = {}
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"])
            hours = ts.dt.hour
            for h in range(24):
                h_mask = (hours == h) & neg_mask
                count_in_h = int(np.sum(h_mask))
                if count_in_h > 0:
                    hourly_counts[h] = count_in_h

        return {
            "negative_price_periods": neg_count,
            "negative_price_hours": total_neg_hours,
            "max_consecutive_hours": max_consecutive_hours,
            "lowest_price": round(lowest_negative_price, 2),
            "hourly_distribution": hourly_counts
        }

    @staticmethod
    def calculate_rolling_negative_days(metrics_df: pd.DataFrame, window: int = 30) -> int:
        """
        Calculates the number of days with negative price in the past `window` days.
        """
        if metrics_df.empty or "negative_price_count" not in metrics_df.columns:
            return 0
        recent = metrics_df.tail(window)
        return int((recent["negative_price_count"] > 0).sum())
