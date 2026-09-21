from pathlib import Path
import json
import pytest
import pandas as pd

from voltpulse.ingestion.shandong import ShandongAdapter
from voltpulse.storage.schemas import SPOT_PRICE_COLUMNS


@pytest.fixture
def temp_raw_dir(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


@pytest.fixture
def fixture_path():
    p = Path(__file__).resolve().parent / "fixtures" / "shandong_sample.csv"
    assert p.exists(), f"Benchmark fixture must exist at {p}"
    return p


def test_shandong_adapter_ingest_from_fixture(temp_raw_dir, fixture_path):
    config = {
        "name": "shandong",
        "data_source": {
            "provider": "山东电力交易中心",
            "url": "https://pmos.sd.sgcc.com.cn/"
        }
    }
    adapter = ShandongAdapter(config, temp_raw_dir, fixture_path=fixture_path)
    target_date = "2026-08-01"

    normalized_df, metadata = adapter.ingest_date(target_date)

    # Verify rows & columns
    assert len(normalized_df) == 96
    assert list(normalized_df.columns) == SPOT_PRICE_COLUMNS
    assert (normalized_df["market"] == "shandong").all()
    assert (normalized_df["date"] == target_date).all()
    assert (normalized_df["interval"] == 15).all()
    assert (normalized_df["price_type"] == "day_ahead").all()
    assert (normalized_df["is_simulated"] == True).all()

    # Verify raw file and metadata.json archiving
    archive_dir = temp_raw_dir / "shandong" / "2026" / "08" / target_date
    assert (archive_dir / "original.csv").exists()
    assert (archive_dir / "metadata.json").exists()

    with open(archive_dir / "metadata.json", "r", encoding="utf-8") as f:
        saved_meta = json.load(f)
    assert saved_meta["market"] == "shandong"
    assert saved_meta["date"] == target_date
    assert len(saved_meta["sha256"]) == 64
    assert saved_meta["status"] == "SUCCESS"


def test_shandong_adapter_invalid_csv(temp_raw_dir):
    config = {"name": "shandong"}
    adapter = ShandongAdapter(config, temp_raw_dir)
    with pytest.raises(Exception):
        adapter.parse(b"corrupted,binary,\x00\xff\xfe", "2026-08-01", {})
