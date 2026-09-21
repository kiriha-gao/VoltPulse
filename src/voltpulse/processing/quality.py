import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pandas as pd

from voltpulse.storage.schemas import SPOT_PRICE_COLUMNS
from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.quality")


class QualityValidationError(Exception):
    """Raised when data quality validation fails."""
    pass


class DataQualityValidator:
    """
    Comprehensive Data Quality Gate conforming strictly to
    VoltPulse Specification V2.0 Section 9.2.
    
    Verifies 10 dimensions before any data reaches processed database:
    1. schema_mismatch: all required schema fields present
    2. market_identity: data matches requested market
    3. date_consistency: timestamps match target_date and span 00:00 to 23:45
    4. interval_consistency: interval column matches expected minutes
    5. source_authenticity: source_url non-null and valid
    6. simulation_gate: reject simulated data when allow_simulated=False
    7. row_count: exactly expected_rows (e.g. 96 for 15-min)
    8. missing_values: no nulls or NaNs in price
    9. duplicate_timestamp: zero duplicate timestamps
    10. timestamp_continuity & price_range
    """

    def __init__(self, quality_dir: Path, expected_rows_per_day: int = 96,
                 min_price: float = -80.0, max_price: float = 1300.0,
                 allow_simulated: bool = False, expected_interval: int = 15):
        self.quality_dir = Path(quality_dir)
        self.quality_dir.mkdir(parents=True, exist_ok=True)
        self.expected_rows = expected_rows_per_day
        self.min_price = min_price
        self.max_price = max_price
        self.allow_simulated = allow_simulated
        self.expected_interval = expected_interval

    def validate_daily_spot_prices(self, df: pd.DataFrame, market: str, target_date: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Executes complete quality audit on candidate daily spot prices.
        Generates and saves quality audit report data/metadata/quality/YYYY-MM-DD.json.
        """
        logger.info(f"[{market}] Commencing quality audit for date: {target_date} ({len(df)} candidate rows)")

        issues: List[str] = []
        checks: Dict[str, Any] = {}

        if df is None or df.empty:
            issues.append("Empty dataset provided for quality audit")
            return False, {"status": "FAIL", "issues": issues, "checked_at": datetime.now().isoformat()}

        # 1. Schema Mismatch Check
        missing_cols = [col for col in SPOT_PRICE_COLUMNS if col not in df.columns]
        if missing_cols:
            issues.append(f"Schema mismatch: missing columns {missing_cols}")
            checks["schema_mismatch"] = False
        else:
            checks["schema_mismatch"] = True

        # 2. Market Identity Check
        if "market" in df.columns:
            invalid_markets = df[df["market"] != market]
            if not invalid_markets.empty:
                issues.append(f"Market mismatch: expected '{market}', found {invalid_markets['market'].unique().tolist()}")
                checks["market_valid"] = False
            else:
                checks["market_valid"] = True
        else:
            checks["market_valid"] = False

        # 2.5 Date Column Integrity Check
        if "date" in df.columns:
            invalid_dates = df[df["date"].astype(str) != target_date]
            if not invalid_dates.empty:
                issues.append(f"Date column mismatch: expected '{target_date}', found {invalid_dates['date'].unique().tolist()}")
                checks["date_column_valid"] = False
            else:
                checks["date_column_valid"] = True
        else:
            issues.append("Missing required 'date' column")
            checks["date_column_valid"] = False

        # 3. Target Date and Timestamp Consistency Check
        if "timestamp" in df.columns:
            try:
                ts_series = pd.to_datetime(df["timestamp"])
                ts_dates = ts_series.dt.strftime("%Y-%m-%d")
                date_mismatches = ts_dates[ts_dates != target_date]
                if not date_mismatches.empty:
                    issues.append(f"Date mismatch: timestamps do not belong to target_date {target_date}")
                    checks["date_consistent"] = False
                else:
                    checks["date_consistent"] = True

                # Check day boundary coverage (00:00 to 23:45 for 96 periods)
                if len(df) == self.expected_rows and self.expected_rows == 96:
                    first_time = ts_series.iloc[0].strftime("%H:%M")
                    last_time = ts_series.iloc[-1].strftime("%H:%M")
                    if first_time != "00:00" or last_time != "23:45":
                        issues.append(f"Day boundary invalid: starts at {first_time}, ends at {last_time}")
                # Timezone check
                first_ts_str = str(df["timestamp"].iloc[0])
                timezone_valid = ("+08:00" in first_ts_str) or ("+0800" in first_ts_str) or (getattr(ts_series.dt.tz, "zone", None) == "Asia/Shanghai")
                checks["timezone_valid"] = bool(timezone_valid)
                if not timezone_valid:
                    issues.append("Timezone invalid: expected Asia/Shanghai (+08:00)")
            except Exception as err:
                issues.append(f"Timestamp parsing error: {err}")
                checks["date_consistent"] = False
                checks["timezone_valid"] = False

        # 4. Interval Consistency Check
        if "interval" in df.columns:
            invalid_intervals = df[df["interval"] != self.expected_interval]
            if not invalid_intervals.empty:
                issues.append(f"Interval mismatch: expected {self.expected_interval} min, got {invalid_intervals['interval'].unique().tolist()}")
                checks["interval_valid"] = False
            else:
                checks["interval_valid"] = True

        # 5. Source URL Non-Null Check
        if "source_url" in df.columns:
            null_source_count = int(df["source_url"].isna().sum() + (df["source_url"] == "").sum())
            if null_source_count > 0:
                issues.append(f"Missing source_url: {null_source_count} rows have null or empty source_url")
                checks["source_valid"] = False
            else:
                checks["source_valid"] = True
        else:
            checks["source_valid"] = False

        # 6. Simulation Gate Check & Null Rejection
        if "is_simulated" in df.columns:
            null_sim_count = int(df["is_simulated"].isna().sum())
            if null_sim_count > 0:
                issues.append(f"Missing is_simulated flag: {null_sim_count} rows have null simulation status")
                checks["simulation_check"] = False
            else:
                has_simulated = bool(df["is_simulated"].any())
                if not self.allow_simulated and has_simulated:
                    issues.append("Simulation gate rejection: is_simulated=True data rejected in production QC")
                    checks["simulation_check"] = False
                else:
                    checks["simulation_check"] = True
        else:
            issues.append("Missing required 'is_simulated' column")
            checks["simulation_check"] = False

        # 6.5 Integrity Check: Source URL protocol vs is_simulated flag
        if "source_url" in df.columns and "is_simulated" in df.columns:
            urls = df["source_url"].astype(str)
            is_sim = df["is_simulated"].fillna(False).astype(bool)
            synthetic_urls = urls.str.startswith("synthetic://") | urls.str.contains("synthetic|simulation", case=False)
            conflicting_flags = synthetic_urls & (~is_sim)
            if conflicting_flags.any():
                issues.append("Integrity conflict: source_url indicates synthetic data but is_simulated=False")
                checks["source_valid"] = False

        # 7. Row Count Check
        actual_rows = len(df)
        checks["rows"] = actual_rows
        checks["expected_rows"] = self.expected_rows
        if actual_rows != self.expected_rows:
            issues.append(f"Row count mismatch: expected {self.expected_rows}, got {actual_rows}")

        # 8. Missing Values Check (Null / NaN)
        missing_count = int(df["price_rmb_mwh"].isna().sum()) if "price_rmb_mwh" in df.columns else actual_rows
        checks["missing"] = missing_count
        if missing_count > 0:
            issues.append(f"Missing price values detected: {missing_count} nulls")

        # 9. Duplicate Timestamp Check
        duplicates_count = int(df["timestamp"].duplicated().sum()) if "timestamp" in df.columns else 0
        checks["duplicates"] = duplicates_count
        if duplicates_count > 0:
            issues.append(f"Duplicate timestamps detected: {duplicates_count} duplicated rows")

        # 10. Timestamp Continuity Check
        continuity_score = 1.0
        if "timestamp" in df.columns and actual_rows > 1:
            try:
                diffs = ts_series.diff().dropna()
                expected_delta = pd.Timedelta(minutes=self.expected_interval)
                valid_steps = (diffs == expected_delta).sum()
                continuity_score = round(float(valid_steps) / float(len(diffs)), 4)
                if continuity_score < 1.0:
                    issues.append(f"Discontinuous timestamps: continuity score {continuity_score} < 1.0")
            except Exception as e:
                continuity_score = 0.0
                issues.append(f"Timestamp continuity error: {e}")
        else:
            continuity_score = 0.0 if actual_rows == 0 else 1.0
        checks["continuity"] = continuity_score

        # 11. Price Boundary Checks
        if "price_rmb_mwh" in df.columns and not df.empty:
            prices = df["price_rmb_mwh"].dropna()
            # Absolute physical sanity bounds [-500, 5000]
            invalid_count = int(((prices < -500.0) | (prices > 5000.0)).sum())
            if invalid_count > 0:
                issues.append(f"Invalid physical price values: {invalid_count} points outside [-500, 5000]")

            # Provincial regulatory limits
            extreme_count = int(((prices < self.min_price) | (prices > self.max_price)).sum())
            checks["extreme_prices"] = extreme_count
            checks["extreme_price_count"] = extreme_count
            if extreme_count > 0:
                issues.append(f"Extreme prices exceeding provincial market rules [{self.min_price}, {self.max_price}]: {extreme_count} points")

        is_valid = (len(issues) == 0)
        report_status = "PASS" if is_valid else "FAIL"

        now_cst = datetime.now(timezone(timedelta(hours=8)))
        report = {
            "market": market,
            "target_date": target_date,
            "status": report_status,
            "checks": checks,
            "issues": issues,
            "rows": actual_rows,
            "missing": missing_count,
            "duplicates": duplicates_count,
            "continuity": continuity_score,
            "checked_at": now_cst.isoformat()
        }

        # Save QC report to metadata directory
        report_file = self.quality_dir / f"{target_date}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        if is_valid:
            logger.info(f"[{market}] Quality audit PASSED for date {target_date}. Report saved at: {report_file}")
        else:
            logger.warning(f"[{market}] Quality audit FAILED for date {target_date}: {issues}")

        return is_valid, report
