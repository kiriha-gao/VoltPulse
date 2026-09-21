import pytest
import numpy as np
import pandas as pd

from voltpulse.analytics.price_metrics import PriceMetricsCalculator
from voltpulse.analytics.negative_price import NegativePriceAnalyzer


@pytest.fixture
def synthetic_day_df():
    # 96 points
    n = 96
    prices = np.linspace(100.0, 600.0, n)
    # Add negative prices in the middle (points 40 to 47 = 2 hours)
    prices[40:48] = -40.0

    timestamps = [f"2026-08-01T{i*15//60:02d}:{i*15%60:02d}:00+08:00" for i in range(n)]

    return pd.DataFrame({
        "market": "shandong",
        "date": "2026-08-01",
        "timestamp": timestamps,
        "interval": 15,
        "price_type": "day_ahead",
        "price_rmb_mwh": prices
    })


def test_price_metrics_calculator(synthetic_day_df):
    metrics = PriceMetricsCalculator.calculate_daily_metrics(synthetic_day_df)

    assert metrics["market"] == "shandong"
    assert metrics["date"] == "2026-08-01"
    assert metrics["min_price"] == -40.0
    assert metrics["max_price"] == 600.0
    assert metrics["peak_valley_spread"] == 640.0
    assert metrics["negative_price_count"] == 8
    assert round(metrics["negative_price_ratio"], 4) == round(8 / 96, 4)
    assert metrics["p05"] <= metrics["p25"] <= metrics["p75"] <= metrics["p95"]
    assert metrics["total_periods"] == 96


def test_negative_price_analyzer(synthetic_day_df):
    neg_res = NegativePriceAnalyzer.analyze_daily_negative_prices(synthetic_day_df)

    assert neg_res["negative_price_periods"] == 8
    # 8 periods * 0.25h = 2.0h
    assert neg_res["negative_price_hours"] == 2.0
    assert neg_res["max_consecutive_hours"] == 2.0
    assert neg_res["lowest_price"] == -40.0
    assert len(neg_res["hourly_distribution"]) > 0


def test_negative_price_analyzer_no_negative():
    df_pos = pd.DataFrame({
        "price_rmb_mwh": [200.0, 300.0, 400.0],
        "interval": [15, 15, 15],
        "timestamp": ["2026-08-01T00:00:00+08:00", "2026-08-01T00:15:00+08:00", "2026-08-01T00:30:00+08:00"]
    })
    res = NegativePriceAnalyzer.analyze_daily_negative_prices(df_pos)
    assert res["negative_price_periods"] == 0
    assert res["negative_price_hours"] == 0.0
    assert res["lowest_price"] == 200.0
