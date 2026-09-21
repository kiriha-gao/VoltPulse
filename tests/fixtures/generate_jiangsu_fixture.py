import csv
import math
from datetime import datetime, timedelta
from pathlib import Path


def generate_jiangsu_benchmark_data(start_date: str = "2026-08-01", days: int = 14) -> Path:
    """
    Generates synthetic Jiangsu Power Spot Market benchmark electricity prices
    reflecting typical East China industrial dual-peak load curves:
      - Deep valley (overnight): 00:00 - 06:30 (~220 - 320 RMB/MWh)
      - Morning peak (industrial morning): 09:00 - 11:30 (~850 - 1100 RMB/MWh)
      - Midday sub-valley / flat (rooftop solar relief): 12:00 - 15:30 (~420 - 560 RMB/MWh)
      - Evening peak (lighting & commercial): 18:30 - 21:30 (~950 - 1280 RMB/MWh)
      - Late night transition: 22:00 - 24:00 (~350 - 450 RMB/MWh)
    """
    records = []
    base_dt = datetime.strptime(start_date, "%Y-%m-%d")

    for d_idx in range(days):
        curr_dt = base_dt + timedelta(days=d_idx)
        curr_date = curr_dt.strftime("%Y-%m-%d")
        is_weekend = curr_dt.weekday() >= 5
        weekend_discount = 80.0 if is_weekend else 0.0

        for p in range(1, 97):  # 96 periods (15-min each)
            minutes = (p - 1) * 15
            hour = minutes / 60.0

            # 1. Overnight Deep Valley (00:00 - 06:30)
            if 0.0 <= hour < 6.5:
                base = 250.0 + 25.0 * math.sin(hour * math.pi / 6.5)
                price = base + (d_idx % 3) * 6.0 - (weekend_discount * 0.4)

            # 2. Morning Ramp-up (06:30 - 09:00)
            elif 6.5 <= hour < 9.0:
                prog = (hour - 6.5) / 2.5
                price = 280.0 + 600.0 * (prog ** 1.3)

            # 3. Morning Industrial Peak (09:00 - 11:30)
            elif 9.0 <= hour < 11.5:
                prog = (hour - 9.0) / 2.5
                price = 920.0 + 160.0 * math.sin(prog * math.pi) - weekend_discount

            # 4. Midday Sub-valley / Lunch Dip (11:50 - 15:30)
            elif 11.5 <= hour < 15.5:
                prog = (hour - 11.5) / 4.0
                price = 680.0 - 200.0 * math.sin(prog * math.pi) + (d_idx % 2) * 10.0

            # 5. Afternoon Pre-peak Ramp (15:50 - 18:30)
            elif 15.5 <= hour < 18.5:
                prog = (hour - 15.5) / 3.0
                price = 540.0 + 380.0 * prog

            # 6. Evening Peak (18:30 - 21:30)
            elif 18.5 <= hour < 21.5:
                prog = (hour - 18.5) / 3.0
                price = 980.0 + 220.0 * math.sin(prog * math.pi) - (weekend_discount * 0.6)

            # 7. Night Wind-down (21:30 - 24:00)
            else:
                prog = (hour - 21.5) / 2.5
                price = 850.0 - 520.0 * prog

            # Jiangsu bounds [0, 1400]
            price = max(0.0, min(1400.0, round(price, 2)))

            hh = int(minutes // 60)
            mm = int(minutes % 60)
            ts = f"{curr_date}T{hh:02d}:{mm:02d}:00+08:00"

            records.append({
                "market": "jiangsu",
                "date": curr_date,
                "timestamp": ts,
                "period": p,
                "interval": 15,
                "price_type": "day_ahead",
                "price_rmb_mwh": price,
                "source": "VoltPulse Jiangsu Benchmark (Dual-Peak Load Simulation)",
                "source_url": "synthetic://jiangsu-dual-peak-generator",
                "is_simulated": True
            })

    fixtures_dir = Path(__file__).resolve().parent
    output_path = fixtures_dir / "jiangsu_sample.csv"

    fieldnames = [
        "market", "date", "timestamp", "period", "interval",
        "price_type", "price_rmb_mwh", "source", "source_url", "is_simulated"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Generated {len(records)} records saved to {output_path}")
    return output_path


if __name__ == "__main__":
    generate_jiangsu_benchmark_data()
