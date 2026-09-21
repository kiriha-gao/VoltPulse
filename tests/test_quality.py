from pathlib import Path
import json
import pytest
import pandas as pd

from voltpulse.processing.quality import DataQualityValidator
from voltpulse.storage.schemas import SPOT_PRICE_COLUMNS


@pytest.fixture
def quality_validator(tmp_path):
    q_dir = tmp_path / "metadata" / "quality"
    return DataQualityValidator(quality_dir=q_dir, expected_rows_per_day=96, min_price=-80.0, max_price=1300.0, allow_simulated=True)


@pytest.fixture
def valid_daily_df():
    # Load 1 valid day (96 points) from fixture
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "shandong_sample.csv"
    df = pd.read_csv(fixture_path)
    day_df = df[df["date"] == "2026-08-01"].copy()
    return day_df[SPOT_PRICE_COLUMNS]


def test_quality_validator_passes_valid_data(quality_validator, valid_daily_df):
    target_date = "2026-08-01"
    is_valid, report = quality_validator.validate_daily_spot_prices(valid_daily_df, "shandong", target_date)

    assert is_valid is True
    assert report["status"] == "PASS"
    assert report["rows"] == 96
    assert report["missing"] == 0
    assert report["duplicates"] == 0
    assert report["continuity"] == 1.0
    assert report["checks"]["schema_mismatch"] is True
    assert report["checks"]["timezone_valid"] is True

    # Verify JSON report file was created
    report_file = quality_validator.quality_dir / f"{target_date}.json"
    assert report_file.exists()
    with open(report_file, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["status"] == "PASS"


def test_quality_validator_catches_missing_rows(quality_validator, valid_daily_df):
    # Drop 5 rows -> 91 rows instead of 96
    tampered_df = valid_daily_df.iloc[:91].copy()
    is_valid, report = quality_validator.validate_daily_spot_prices(tampered_df, "shandong", "2026-08-01")

    assert is_valid is False
    assert report["status"] == "FAIL"
    assert any("Row count mismatch" in issue for issue in report["issues"])


def test_quality_validator_catches_missing_values(quality_validator, valid_daily_df):
    tampered_df = valid_daily_df.copy()
    tampered_df.loc[10, "price_rmb_mwh"] = None
    is_valid, report = quality_validator.validate_daily_spot_prices(tampered_df, "shandong", "2026-08-01")

    assert is_valid is False
    assert report["status"] == "FAIL"
    assert report["missing"] == 1
    assert any("Missing price values detected" in issue for issue in report["issues"])


def test_quality_validator_catches_duplicates(quality_validator, valid_daily_df):
    tampered_df = valid_daily_df.copy()
    # Duplicate first row
    tampered_df.loc[1, "timestamp"] = tampered_df.loc[0, "timestamp"]
    is_valid, report = quality_validator.validate_daily_spot_prices(tampered_df, "shandong", "2026-08-01")

    assert is_valid is False
    assert report["status"] == "FAIL"
    assert report["duplicates"] >= 1


def test_quality_validator_catches_extreme_price(quality_validator, valid_daily_df):
    tampered_df = valid_daily_df.copy()
    # Out of Shandong provincial boundary limit (-80 to 1300)
    tampered_df.loc[15, "price_rmb_mwh"] = 2500.0
    is_valid, report = quality_validator.validate_daily_spot_prices(tampered_df, "shandong", "2026-08-01")

    assert is_valid is False
    assert report["status"] == "FAIL"
    assert report["checks"]["extreme_prices"] == 1


def test_quality_validator_catches_simulated_in_production(tmp_path, valid_daily_df):
    prod_validator = DataQualityValidator(
        quality_dir=tmp_path / "prod_quality",
        expected_rows_per_day=96,
        allow_simulated=False
    )
    is_valid, report = prod_validator.validate_daily_spot_prices(valid_daily_df, "shandong", "2026-08-01")
    assert is_valid is False
    assert report["status"] == "FAIL"
    assert any("Simulation gate rejection" in issue for issue in report["issues"])
