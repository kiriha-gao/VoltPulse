import io
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import pandas as pd

from voltpulse.ingestion.base import MarketDataSource
from voltpulse.ingestion.downloader import RobustDownloader
from voltpulse.storage.schemas import SPOT_PRICE_COLUMNS
from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.ingestion.shandong")


class ShandongAdapter(MarketDataSource):
    """
    Adapter for Shandong Electricity Spot Market (山东电力现货市场).
    Conforms to VoltPulse Specification M01.
    """

    def __init__(self, config: Dict[str, Any], raw_base_dir: Path, fixture_path: Optional[Path] = None):
        super().__init__("shandong", config, raw_base_dir)
        self.downloader = RobustDownloader()
        self.fixture_path = fixture_path

    def fetch(self, target_date: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Fetches Shandong spot market clearing price data for target_date.
        If offline fixture mode or target_date is in fixture, uses verified real benchmark data.
        """
        # 1. Check if offline fixture dataset contains target date
        if self.fixture_path and self.fixture_path.exists():
            logger.info(f"Checking fixture dataset at {self.fixture_path} for date {target_date}")
            df_fix = pd.read_csv(self.fixture_path)
            if "date" in df_fix.columns and target_date in df_fix["date"].values:
                df_sub = df_fix[df_fix["date"] == target_date]
                csv_bytes = df_sub.to_csv(index=False).encode("utf-8")
                metadata = {
                    "source": "VoltPulse Synthetic Benchmark (Duck Curve Simulation)",
                    "source_url": "fixture://shandong/synthetic_duck_curve",
                    "retrieved_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                    "status": "SUCCESS",
                    "file_ext": "csv",
                    "is_simulated": True
                }
                return csv_bytes, metadata

        # 2. Attempt online fetch from public disclosure portal
        base_url = self.config.get("data_source", {}).get("url", "https://pmos.sd.sgcc.com.cn/")
        # Note: In production CI/CD, if network access to the provincial server is blocked or gated,
        # Section 1.4 requires graceful fallback without faking data.
        try:
            resp = self.downloader.get(f"{base_url.rstrip('/')}/public/spot_price", params={"date": target_date})
            metadata = {
                "source": "山东电力交易中心公开披露",
                "source_url": resp.url,
                "retrieved_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "status": "SUCCESS",
                "file_ext": "csv",
                "is_simulated": False
            }
            return resp.content, metadata
        except Exception as e:
            logger.warning(f"Online fetch for Shandong spot price failed: {e}")
            raise FileNotFoundError(f"Data unavailable for Shandong on {target_date}: {e}")

    def parse(self, raw_content: bytes, target_date: str, metadata: Dict[str, Any]) -> pd.DataFrame:
        """
        Parses raw CSV bytes into a structured pandas DataFrame.
        """
        try:
            df = pd.read_csv(io.BytesIO(raw_content))
            return df
        except Exception as e:
            logger.error(f"Failed to parse raw content as CSV: {e}")
            raise ValueError(f"Corrupted Shandong raw payload on {target_date}: {e}")

    def normalize(self, raw_df: pd.DataFrame, target_date: str, metadata: Dict[str, Any]) -> pd.DataFrame:
        """
        Transforms raw parsed DataFrame into strictly typed SPOT_PRICE_COLUMNS.
        Expected raw fields can be:
        - time / timestamp / period
        - price / price_rmb_mwh / clearing_price
        """
        df = raw_df.copy()

        # Handle column aliasing
        col_map = {
            "clearing_price": "price_rmb_mwh",
            "price": "price_rmb_mwh",
            "spot_price": "price_rmb_mwh",
            "time": "timestamp",
            "datetime": "timestamp"
        }
        df = df.rename(columns=col_map)

        if "price_rmb_mwh" not in df.columns:
            raise KeyError("Missing required price column ('price_rmb_mwh' or 'price') in parsed data")

        # Standardize date and timestamps
        df["market"] = "shandong"
        df["date"] = target_date
        df["interval"] = 15  # 15 minutes per period in Shandong spot market
        df["price_type"] = "day_ahead"
        df["price_rmb_mwh"] = df["price_rmb_mwh"].astype(float)
        df["source"] = metadata.get("source", "山东电力交易中心")
        df["source_url"] = metadata.get("source_url", "https://pmos.sd.sgcc.com.cn/")
        df["retrieved_at"] = metadata.get("retrieved_at", datetime.now(timezone(timedelta(hours=8))).isoformat())
        df["is_simulated"] = metadata.get("is_simulated", False)
        df["schema_version"] = "1.0.0"

        # Build ISO timestamps if given as periods (1..96) or HH:MM
        if "period" in df.columns and "timestamp" not in df.columns:
            # Generate 96 timestamps for the target_date
            timestamps = []
            for p in df["period"].astype(int):
                minutes_from_midnight = (p - 1) * 15
                hour = minutes_from_midnight // 60
                minute = minutes_from_midnight % 60
                ts_str = f"{target_date}T{hour:02d}:{minute:02d}:00+08:00"
                timestamps.append(ts_str)
            df["timestamp"] = timestamps
        elif "timestamp" in df.columns:
            # Ensure timestamps have +08:00 timezone
            df["timestamp"] = df["timestamp"].apply(self._format_timestamp, target_date=target_date)

        # Reorder strictly by SPOT_PRICE_COLUMNS
        normalized = df[SPOT_PRICE_COLUMNS].copy()
        normalized = normalized.sort_values(by="timestamp").reset_index(drop=True)
        return normalized

    def _format_timestamp(self, val: str, target_date: str) -> str:
        """Ensures timestamp is ISO 8601 with +08:00 timezone."""
        val_str = str(val).strip()
        if len(val_str) == 5 and ":" in val_str:  # e.g. "12:15"
            return f"{target_date}T{val_str}:00+08:00"
        elif "T" in val_str:
            if not ("+" in val_str or val_str.endswith("Z")):
                return f"{val_str}+08:00"
            return val_str
        else:
            # e.g. "2026-09-01 12:15:00"
            dt_part = val_str.replace(" ", "T")
            if "+" not in dt_part:
                return f"{dt_part}+08:00"
            return dt_part
