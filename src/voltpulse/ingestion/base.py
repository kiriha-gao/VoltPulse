from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import hashlib
import json
import pandas as pd

from voltpulse.storage.schemas import SPOT_PRICE_COLUMNS
from voltpulse.utils.logging import get_logger

logger = get_logger("voltpulse.ingestion.base")


class MarketDataSource(ABC):
    """
    Abstract Base Class for all market data source adapters conforming
    to VoltPulse Specification V2.0 Section 9.3.
    """

    def __init__(self, market_name: str, config: Dict[str, Any], raw_base_dir: Path):
        self.market_name = market_name
        self.config = config
        self.raw_base_dir = Path(raw_base_dir)

    @abstractmethod
    def fetch(self, target_date: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Fetches raw data payload for a specific date (YYYY-MM-DD).
        Returns raw bytes and fetch metadata (source, url, content_type, etc.).
        """
        pass

    @abstractmethod
    def parse(self, raw_content: bytes, target_date: str, metadata: Dict[str, Any]) -> pd.DataFrame:
        """
        Parses raw bytes into an intermediate DataFrame.
        """
        pass

    @abstractmethod
    def normalize(self, raw_df: pd.DataFrame, target_date: str, metadata: Dict[str, Any]) -> pd.DataFrame:
        """
        Normalizes intermediate DataFrame strictly into standard SPOT_PRICE_COLUMNS.
        """
        pass

    def save_raw_archive(self, raw_content: bytes, target_date: str, file_ext: str, metadata: Dict[str, Any]) -> Path:
        """
        Saves raw data payload immutably in:
        data/raw/{market}/{YYYY}/{MM}/{YYYY-MM-DD}/
        conforming to V2.0 Specification Section 9.3.

        Immutability & Revision Rules:
        - If original.{ext} doesn't exist, save as original.{ext}.
        - If original.{ext} exists with identical hash: do not duplicate.
        - If original.{ext} exists with different hash: save as revision_{n}.{ext}, preserving original.
        - Update metadata.json tracking all revision hashes and timestamps.
        """
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        year_str = dt.strftime("%Y")
        month_str = dt.strftime("%m")
        date_dir = self.raw_base_dir / self.market_name / year_str / month_str / target_date
        date_dir.mkdir(parents=True, exist_ok=True)

        sha256_hash = hashlib.sha256(raw_content).hexdigest()
        metadata["sha256"] = sha256_hash

        original_file = date_dir / f"original.{file_ext}"
        meta_file = date_dir / "metadata.json"

        # Load existing metadata if present
        existing_meta = {}
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    existing_meta = json.load(f)
            except Exception:
                existing_meta = {}

        revisions = existing_meta.get("revisions", [])

        if not original_file.exists():
            target_file = original_file
            revision_id = 0
            with open(target_file, "wb") as f:
                f.write(raw_content)
        else:
            orig_hash = hashlib.sha256(original_file.read_bytes()).hexdigest()
            existing_rev_files = list(date_dir.glob(f"revision_*_{sha256_hash[:8]}.{file_ext}"))
            matched_rev = next((r for r in revisions if r.get("sha256") == sha256_hash), None)

            if orig_hash == sha256_hash:
                # Content matches original; no-op per Spec 9.3
                target_file = original_file
                revision_id = 0
            elif matched_rev is not None or existing_rev_files:
                # Content already exists in a previous revision; deduplicate and do not create new file
                target_file = existing_rev_files[0] if existing_rev_files else (date_dir / matched_rev.get("file_name", f"original.{file_ext}"))
                revision_id = matched_rev.get("revision_id", 0) if matched_rev else 0
                return target_file
            else:
                # Genuinely new content revision!
                rev_num = len(revisions) + 1
                target_file = date_dir / f"revision_{rev_num}_{sha256_hash[:8]}.{file_ext}"
                revision_id = rev_num
                with open(target_file, "wb") as f:
                    f.write(raw_content)

        retrieved_time = metadata.get("retrieved_at", datetime.now(timezone(timedelta(hours=8))).isoformat())
        rev_record = {
            "revision_id": revision_id,
            "file_name": target_file.name,
            "sha256": sha256_hash,
            "size_bytes": len(raw_content),
            "retrieved_at": retrieved_time,
            "status": metadata.get("status", "SUCCESS")
        }

        # Avoid duplicate entries in revisions list
        if not any(r.get("sha256") == sha256_hash for r in revisions):
            revisions.append(rev_record)

        metadata_to_save = {
            "market": self.market_name,
            "date": target_date,
            "source": metadata.get("source", self.config.get("data_source", {}).get("provider", "Unknown")),
            "source_url": metadata.get("source_url", self.config.get("data_source", {}).get("url", "")),
            "status": metadata.get("status", "SUCCESS"),
            "latest_sha256": sha256_hash,
            "sha256": sha256_hash,
            "latest_file": target_file.name,
            "file_name": target_file.name,
            "retrieved_at": retrieved_time,
            "revisions": revisions
        }

        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata_to_save, f, ensure_ascii=False, indent=2)

        logger.info(f"Raw data archived at: {target_file} (SHA256: {sha256_hash[:8]}...)")
        return target_file

    def ingest_date(self, target_date: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Full end-to-end ingestion pipeline for a single day:
        fetch -> archive raw -> parse -> normalize.
        """
        logger.info(f"[{self.market_name}] Ingestion initiated for date: {target_date}")
        raw_bytes, meta = self.fetch(target_date)
        file_ext = meta.get("file_ext", "csv")
        archived_file = self.save_raw_archive(raw_bytes, target_date, file_ext, meta)

        raw_df = self.parse(raw_bytes, target_date, meta)
        normalized_df = self.normalize(raw_df, target_date, meta)

        logger.info(f"[{self.market_name}] Ingestion normalized {len(normalized_df)} records for date: {target_date}")
        return normalized_df, meta
