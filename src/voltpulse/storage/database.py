import sqlite3
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from voltpulse.storage.schemas import SPOT_PRICE_COLUMNS
from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.storage")


class DatabaseManager:
    """
    Manages local Parquet storage and SQLite metadata index according to
    VoltPulse Specification Section 8 (M03).
    """

    PRIMARY_KEYS = ["market", "timestamp", "price_type"]

    def __init__(self, parquet_path: Path, sqlite_path: Path):
        self.parquet_path = Path(parquet_path)
        self.sqlite_path = Path(sqlite_path)

        self.parquet_path.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_sqlite()

    def _init_sqlite(self):
        """Initializes SQLite tables for metadata, audits, and ingestion runs."""
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_batches (
                    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market TEXT NOT NULL,
                    target_date TEXT NOT NULL,
                    rows_inserted INTEGER NOT NULL,
                    source TEXT,
                    retrieved_at TEXT NOT NULL,
                    sha256 TEXT,
                    status TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quality_checks (
                    check_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market TEXT NOT NULL,
                    target_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    rows INTEGER NOT NULL,
                    missing INTEGER NOT NULL,
                    duplicates INTEGER NOT NULL,
                    continuity REAL NOT NULL,
                    report_path TEXT,
                    checked_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def record_ingestion_batch(self, market: str, target_date: str, rows: int = 0,
                               source: str = "", retrieved_at: str = "", sha256: str = "", status: str = "SUCCESS",
                               rows_inserted: Optional[int] = None):
        """Logs an ingestion batch in SQLite."""
        actual_rows = rows_inserted if rows_inserted is not None else rows
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ingestion_batches (market, target_date, rows_inserted, source, retrieved_at, sha256, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (market, target_date, actual_rows, source, retrieved_at, sha256, status))
            conn.commit()

    def record_quality_check(self, market: str, target_date: str, status: str,
                             rows: int, missing: int, duplicates: int, continuity: float,
                             report_path: str, checked_at: str):
        """Logs a data quality audit in SQLite."""
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO quality_checks (market, target_date, status, rows, missing, duplicates, continuity, report_path, checked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (market, target_date, status, rows, missing, duplicates, continuity, report_path, checked_at))
            conn.commit()

    def load_all_prices(self) -> pd.DataFrame:
        """Loads complete spot prices dataframe from Parquet."""
        if not self.parquet_path.exists():
            return pd.DataFrame(columns=SPOT_PRICE_COLUMNS)
        return pd.read_parquet(self.parquet_path)

    def load_market_prices(self, market: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """Loads filtered spot prices for a specific market and date range."""
        df = self.load_all_prices()
        if df.empty:
            return df
        
        filtered = df[df["market"] == market]
        if start_date:
            filtered = filtered[filtered["date"] >= start_date]
        if end_date:
            filtered = filtered[filtered["date"] <= end_date]
        return filtered.sort_values(by=["price_type", "timestamp"]).reset_index(drop=True)

    def append_and_deduplicate(self, new_df: pd.DataFrame) -> int:
        """
        Appends new validated spot price records, deduplicates by (market, timestamp, price_type),
        sorts chronologically, and writes atomically using a temporary file.
        Returns the count of rows stored in total.
        """
        if new_df.empty:
            logger.warning("Empty dataframe supplied to append_and_deduplicate; skipping.")
            return len(self.load_all_prices())

        # Ensure column conformity
        for col in SPOT_PRICE_COLUMNS:
            if col not in new_df.columns:
                raise ValueError(f"Missing mandatory column '{col}' in candidate dataframe")

        existing_df = self.load_all_prices()
        if existing_df.empty:
            combined_df = new_df[SPOT_PRICE_COLUMNS].copy()
        else:
            combined_df = pd.concat([existing_df, new_df[SPOT_PRICE_COLUMNS]], ignore_index=True)

        # Deduplicate keeping the latest retrieved_at entry
        if "retrieved_at" in combined_df.columns:
            combined_df = combined_df.sort_values(by="retrieved_at", ascending=True)

        combined_df = combined_df.drop_duplicates(subset=self.PRIMARY_KEYS, keep="last")

        # Sort chronologically by market, price_type, timestamp
        combined_df = combined_df.sort_values(by=["market", "price_type", "timestamp"]).reset_index(drop=True)

        # Atomic write to temporary file then replace
        temp_parquet = self.parquet_path.with_suffix(".tmp.parquet")
        table = pa.Table.from_pandas(combined_df)
        pq.write_table(table, temp_parquet, compression="SNAPPY")

        # Safe atomic replace
        shutil.move(str(temp_parquet), str(self.parquet_path))
        logger.info(f"Parquet updated atomically: {len(combined_df)} total records stored at {self.parquet_path}")

        return len(combined_df)

    def get_tracked_days_count(self, market: str) -> int:
        """Returns the number of unique dates tracked for a market."""
        df = self.load_market_prices(market)
        if df.empty:
            return 0
        return df["date"].nunique()

    def get_latest_date(self, market: str) -> Optional[str]:
        """Returns the most recent date available for a market."""
        df = self.load_market_prices(market)
        if df.empty:
            return None
        return str(df["date"].max())
