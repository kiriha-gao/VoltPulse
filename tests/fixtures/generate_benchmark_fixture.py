import csv
import math
from datetime import datetime, timedelta
from pathlib import Path


def generate_shandong_benchmark_data(start_date: str = "2026-08-01", days: int = 14):
    """
    Generates synthetic Duck Curve benchmark electricity prices
    for testing and algorithm verification.
    Clearly and transparently labeled as is_simulated = True.
    """
    records = []
    base_dt = datetime.strptime(start_date, "%Y-%m-%d")

    for d_idx in range(days):
        curr_date = (base_dt + timedelta(days=d_idx)).strftime("%Y-%m-%d")
        is_weekend = (base_dt + timedelta(days=d_idx)).weekday() >= 5
        solar_intensity = 1.0 if (d_idx % 3 != 0) else 0.4

        for p in range(1, 97):  # 96 periods (15-min each)
            minutes = (p - 1) * 15
            hour = minutes / 60.0

            if 0.0 <= hour < 6.5:
                price = 230.0 + 30.0 * math.sin(hour * math.pi / 6.0) + (d_idx % 4) * 8.0
            elif 6.5 <= hour < 9.5:
                progress = (hour - 6.5) / 3.0
                price = 280.0 + 200.0 * math.sin(progress * math.pi)
            elif 9.5 <= hour < 16.0:
                mid_dist = abs(hour - 12.5) / 3.0
                if solar_intensity > 0.7:
                    price = -50.0 + 120.0 * (mid_dist ** 1.5) - (d_idx % 2) * 15.0
                else:
                    price = 80.0 + 140.0 * (mid_dist ** 1.5)
            elif 16.0 <= hour < 17.5:
                progress = (hour - 16.0) / 1.5
                price = 180.0 + 250.0 * progress
            elif 17.5 <= hour < 21.5:
                progress = (hour - 17.5) / 4.0
                price = 550.0 + 320.0 * math.sin(progress * math.pi) - (50.0 if is_weekend else 0.0)
            else:
                progress = (hour - 21.5) / 2.5
                price = 500.0 - 240.0 * progress

            price = max(-75.0, min(1200.0, round(price, 2)))

            hh = int(minutes // 60)
            mm = int(minutes % 60)
            ts = f"{curr_date}T{hh:02d}:{mm:02d}:00+08:00"

            records.append({
                "market": "shandong",
                "date": curr_date,
                "timestamp": ts,
                "period": p,
                "interval": 15,
                "price_type": "day_ahead",
                "price_rmb_mwh": price,
                "source": "VoltPulse Synthetic Benchmark (Duck Curve Simulation)",
                "source_url": "fixture://shandong/synthetic_duck_curve",
                "retrieved_at": f"{curr_date}T22:00:00+08:00",
                "is_simulated": True,
                "schema_version": "2.0.0"
            })

    out_dir = Path(__file__).resolve().parent
    out_file = out_dir / "shandong_sample.csv"
    fieldnames = [
        "market", "date", "timestamp", "period", "interval", "price_type",
        "price_rmb_mwh", "source", "source_url", "retrieved_at",
        "is_simulated", "schema_version"
    ]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Generated {len(records)} rows across {days} days at {out_file}")


if __name__ == "__main__":
    generate_shandong_benchmark_data(start_date="2026-08-01", days=14)
