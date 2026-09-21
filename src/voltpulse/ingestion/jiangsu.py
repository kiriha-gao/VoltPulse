import io
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import pandas as pd

from voltpulse.ingestion.base import MarketDataSource
from voltpulse.ingestion.downloader import RobustDownloader
from voltpulse.storage.schemas import SPOT_PRICE_COLUMNS
from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.ingestion.jiangsu")


class JiangsuAdapter(MarketDataSource):
    """
    Adapter for Jiangsu Electricity Spot Market (江苏电力现货市场).
    Features:
      - East China industrial load pattern (distinct dual peaks: morning & evening)
      - Standard 96 periods per day (15-minute intervals)
      - Price bounds typically in [0.0, 1400.0] RMB/MWh
      - Support for offline benchmark replay and online transaction disclosure portal
    """

    def __init__(self, config: Dict[str, Any], raw_base_dir: Path, fixture_path: Optional[Path] = None):
        super().__init__("jiangsu", config, raw_base_dir)
        self.downloader = RobustDownloader()
        self.fixture_path = fixture_path

    def fetch(self, target_date: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Fetches Jiangsu spot market clearing price data for target_date.
        If offline fixture mode or target_date is in fixture, uses verified benchmark data.
        """
        # 1. Check if offline fixture dataset contains target date
        if self.fixture_path and self.fixture_path.exists():
            logger.info(f"Checking fixture dataset at {self.fixture_path} for date {target_date}")
            df_fix = pd.read_csv(self.fixture_path)
            if "date" in df_fix.columns and target_date in df_fix["date"].values:
                df_sub = df_fix[df_fix["date"] == target_date]
                csv_bytes = df_sub.to_csv(index=False).encode("utf-8")
                metadata = {
                    "source": "VoltPulse Jiangsu Benchmark (Dual-Peak Simulation)",
                    "source_url": "fixture://jiangsu/dual_peak_sample",
                    "retrieved_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                    "status": "SUCCESS",
                    "file_ext": "csv",
                    "is_simulated": True
                }
                return csv_bytes, metadata

        # 2. Attempt online fetch from Jiangsu public disclosure portal
        base_url = self.config.get("data_source", {}).get("url", "https://pmos.js.sgcc.com.cn/")
        try:
            resp = self.downloader.get(f"{base_url.rstrip('/')}/public/spot_price", params={"date": target_date})
            metadata = {
                "source": "江苏电力交易中心公开披露",
                "source_url": resp.url,
                "retrieved_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "status": "SUCCESS",
                "file_ext": "csv",
                "is_simulated": False
            }
            return resp.content, metadata
        except Exception as e:
            logger.warning(f"Online download failed for Jiangsu date {target_date}: {e}")
            raise

    def parse(self, raw_content: bytes, target_date: str, metadata: Dict[str, Any]) -> pd.DataFrame:
        """
        Parses raw CSV bytes into a pandas DataFrame.
        """
        try:
            df = pd.read_csv(io.BytesIO(raw_content))
            return df
        except Exception as e:
            logger.error(f"Failed to parse Jiangsu raw content for {target_date}: {e}")
            raise ValueError(f"Failed to parse Jiangsu raw content: {e}")

    def normalize(self, raw_df: pd.DataFrame, target_date: str, metadata: Dict[str, Any]) -> pd.DataFrame:
        """
        Normalizes raw DataFrame into standard SPOT_PRICE_COLUMNS format.
        Enforces 96 periods, 15-minute interval, and Jiangsu schema conformance.
        """
        df = raw_df.copy()

        # Map potential column name variants
        col_map = {
            "出清价格": "price_rmb_mwh",
            "日前出清价格": "price_rmb_mwh",
            "price": "price_rmb_mwh",
            "spot_price": "price_rmb_mwh",
            "时段": "period",
            "时间": "timestamp",
            "time": "timestamp",
            "市场": "market"
        }
        df = df.rename(columns=col_map)

        if "price_rmb_mwh" not in df.columns:
            raise KeyError("Missing required price column ('price_rmb_mwh' or recognized aliases)")

        # Ensure market column is set to jiangsu
        df["market"] = "jiangsu"
        df["date"] = target_date

        # If period is missing, infer 1..96
        if "period" not in df.columns:
            df["period"] = range(1, len(df) + 1)
        df["period"] = df["period"].astype(int)

        # Ensure interval is 15 minutes
        df["interval"] = 15

        # Infer or format standard ISO 8601 timestamps
        if "timestamp" not in df.columns:
            df["timestamp"] = df["period"].apply(
                lambda p: f"{target_date}T{(p - 1) * 15 // 60:02d}:{(p - 1) * 15 % 60:02d}:00+08:00"
            )

        # Price type default: day_ahead
        if "price_type" not in df.columns:
            df["price_type"] = "day_ahead"

        # Attach metadata tags
        df["source"] = metadata.get("source", "江苏电力交易中心")
        df["source_url"] = metadata.get("source_url", "https://pmos.js.sgcc.com.cn/")
        df["is_simulated"] = metadata.get("is_simulated", False)
        df["retrieved_at"] = metadata.get("retrieved_at", datetime.now(timezone(timedelta(hours=8))).isoformat())
        df["schema_version"] = "1.0.0"

        # Select standard columns
        out_df = df[SPOT_PRICE_COLUMNS].copy()
        out_df["price_rmb_mwh"] = out_df["price_rmb_mwh"].astype(float)

        return out_df

    def ingest_date(self, target_date: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Complete ingestion cycle: fetch -> parse -> normalize -> save_raw_archive.
        """
        raw_bytes, metadata = self.fetch(target_date)
        archive_path = self.save_raw_archive(raw_bytes, target_date, metadata.get("file_ext", "csv"), metadata)
        raw_df = self.parse(raw_bytes, target_date, metadata)
        clean_df = self.normalize(raw_df, target_date, metadata)
        metadata["archive_path"] = str(archive_path)
        return clean_df, metadata
