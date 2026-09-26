from pathlib import Path

import pytest

from scripts.analyze_public_weekly import load_rows, summarize


def test_guangdong_weekly_case_preserves_published_values():
    source = Path(__file__).resolve().parents[1] / "data" / "public" / "guangdong_weekly_2026_june.csv"
    rows = load_rows(source)
    result = summarize(rows)

    assert result["observation_count"] == 4
    assert result["day_ahead_mean_of_reported_weekly_prices_rmb_mwh"] == 449.0
    assert result["real_time_mean_of_reported_weekly_prices_rmb_mwh"] == 440.75
    assert result["day_ahead_minus_real_time_by_week_rmb_mwh"]["2026-06-29"] == -39.0
    assert all(row["source_url"].startswith("https://www.gzpec.cn/") for row in rows)


def test_weekly_case_rejects_missing_provenance(tmp_path):
    source = Path(__file__).resolve().parents[1] / "data" / "public" / "guangdong_weekly_2026_june.csv"
    damaged = tmp_path / "missing_source.csv"
    damaged.write_text(source.read_text(encoding="utf-8").replace("https://www.gzpec.cn/", "https://example.com/", 1), encoding="utf-8")

    with pytest.raises(ValueError, match="Unexpected source domain"):
        load_rows(damaged)
