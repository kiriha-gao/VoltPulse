"""Analyze published weekly Guangdong market summaries without treating them as 96-point prices."""

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "data" / "public" / "guangdong_weekly_2026_june.csv"
PRICE_FIELDS = ("day_ahead_weighted_avg_rmb_mwh", "real_time_weighted_avg_rmb_mwh")


def load_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"market", "period_start", "period_end", *PRICE_FIELDS, "source_url", "is_simulated"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing columns: {sorted(required - set(reader.fieldnames or []))}")
        rows = list(reader)

    if not rows:
        raise ValueError("No weekly observations found")

    seen = set()
    for row in rows:
        start = date.fromisoformat(row["period_start"])
        end = date.fromisoformat(row["period_end"])
        if (end - start).days != 6 or start in seen:
            raise ValueError("Each observation must describe one unique seven-day period")
        seen.add(start)
        if row["market"] != "guangdong" or row["is_simulated"].lower() != "false":
            raise ValueError("Expected source-linked, non-simulated Guangdong observations")
        if urlparse(row["source_url"]).hostname != "www.gzpec.cn":
            raise ValueError("Unexpected source domain")
        for field in PRICE_FIELDS:
            value = float(row[field])
            if not math.isfinite(value):
                raise ValueError(f"Non-finite price in {field}")
            row[field] = value
    return sorted(rows, key=lambda row: row["period_start"])


def summarize(rows: list[dict]) -> dict:
    spreads = [row["day_ahead_weighted_avg_rmb_mwh"] - row["real_time_weighted_avg_rmb_mwh"] for row in rows]
    return {
        "market": "guangdong",
        "observation_count": len(rows),
        "day_ahead_mean_of_reported_weekly_prices_rmb_mwh": round(sum(row[PRICE_FIELDS[0]] for row in rows) / len(rows), 2),
        "real_time_mean_of_reported_weekly_prices_rmb_mwh": round(sum(row[PRICE_FIELDS[1]] for row in rows) / len(rows), 2),
        "day_ahead_minus_real_time_by_week_rmb_mwh": dict(zip((row["period_start"] for row in rows), spreads)),
        "day_ahead_range_rmb_mwh": [min(row[PRICE_FIELDS[0]] for row in rows), max(row[PRICE_FIELDS[0]] for row in rows)],
        "note": "Unweighted mean of four published weekly weighted averages; not a monthly price or 15-minute series.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze source-linked Guangdong weekly market summaries")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    print(json.dumps(summarize(load_rows(args.input)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
