from pathlib import Path
import pytest
import pandas as pd

from voltpulse.storage.database import DatabaseManager
from voltpulse.storage.schemas import SPOT_PRICE_COLUMNS


@pytest.fixture
def db_manager(tmp_path):
    parquet_file = tmp_path / "processed" / "spot_prices.parquet"
    sqlite_file = tmp_path / "processed" / "voltpulse.db"
    return DatabaseManager(parquet_file, sqlite_file)


@pytest.fixture
def sample_day_df():
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "shandong_sample.csv"
    df = pd.read_csv(fixture_path)
    return df[df["date"] == "2026-08-01"][SPOT_PRICE_COLUMNS].copy()


def test_database_manager_append_and_load(db_manager, sample_day_df):
    assert db_manager.load_all_prices().empty

    total_rows = db_manager.append_and_deduplicate(sample_day_df)
    assert total_rows == 96
    assert db_manager.parquet_path.exists()

    loaded_df = db_manager.load_market_prices("shandong")
    assert len(loaded_df) == 96
    assert db_manager.get_tracked_days_count("shandong") == 1
    assert db_manager.get_latest_date("shandong") == "2026-08-01"


def test_database_manager_deduplication(db_manager, sample_day_df):
    # First append 96 rows
    db_manager.append_and_deduplicate(sample_day_df)

    # Re-append same data with updated price on first timestamp
    updated_df = sample_day_df.copy()
    updated_df.loc[0, "price_rmb_mwh"] = 999.0
    updated_df.loc[0, "retrieved_at"] = "2026-08-01T23:59:59+08:00"

    total_rows = db_manager.append_and_deduplicate(updated_df)
    assert total_rows == 96  # Still 96, deduplicated!

    loaded_df = db_manager.load_market_prices("shandong")
    assert loaded_df.iloc[0]["price_rmb_mwh"] == 999.0


def test_database_manager_sqlite_audit(db_manager):
    db_manager.record_ingestion_batch(
        market="shandong",
        target_date="2026-08-01",
        rows=96,
        source="Test Source",
        retrieved_at="2026-08-01T12:00:00+08:00",
        sha256="abcdef123456",
        status="SUCCESS"
    )
    db_manager.record_quality_check(
        market="shandong",
        target_date="2026-08-01",
        status="PASS",
        rows=96,
        missing=0,
        duplicates=0,
        continuity=1.0,
        report_path="data/metadata/quality/2026-08-01.json",
        checked_at="2026-08-01T12:00:01+08:00"
    )

    # Verify tables exist and have entries
    import sqlite3
    with sqlite3.connect(db_manager.sqlite_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM ingestion_batches")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT count(*) FROM quality_checks")
        assert cursor.fetchone()[0] == 1
