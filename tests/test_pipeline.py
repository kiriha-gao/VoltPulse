import sys
from pathlib import Path
import pytest

# Ensure scripts directory is importable
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from pipeline import run_pipeline


def test_pipeline_fixture_shandong_execution():
    """Verify Shandong pipeline runs end-to-end cleanly in fixture mode."""
    exit_code = run_pipeline(market_name="shandong", mode="fixture", backfill_days=1)
    assert exit_code == 0


def test_pipeline_fixture_jiangsu_execution():
    """Verify Jiangsu pipeline runs end-to-end cleanly in fixture mode."""
    exit_code = run_pipeline(market_name="jiangsu", mode="fixture", backfill_days=1)
    assert exit_code == 0


def test_pipeline_live_mode_handles_missing_dates_safely():
    """Verify live mode gracefully handles uncontactable endpoints without crashing."""
    from unittest.mock import patch
    import requests
    with patch("voltpulse.ingestion.downloader.RobustDownloader.get", side_effect=requests.ConnectionError("Mocked network unreachable")):
        exit_code = run_pipeline(market_name="shandong", target_date="2099-01-01", mode="live", backfill_days=1)
        assert exit_code == 1
