import json
import sys
import hashlib
import runpy
import tempfile
from pathlib import Path
from unittest.mock import patch
import pandas as pd

def run_extra_probes(root_path: Path, output_path: Path = None):
    sys.path.insert(0, str(root_path / "src"))
    from voltpulse.processing.quality import DataQualityValidator
    from voltpulse.optimization.benchmark import FixedPeakValleyStrategy
    from voltpulse.backtest.engine import BacktestEngine
    from voltpulse.utils.config import get_config
    from voltpulse.ingestion.shandong import ShandongAdapter

    cfg = get_config()
    df = pd.read_csv(root_path / "evidence/processed_sample_2026-08-01.csv")
    out = {}

    with tempfile.TemporaryDirectory() as t:
        v = DataQualityValidator(Path(t))
        for name, x in [
            ("date_column_wrong", df.assign(date="2026-08-02")),
            ("simulation_null", df.assign(is_simulated=None)),
            ("synthetic_source_false_flag", df.assign(source_url="synthetic://generator", is_simulated=False)),
        ]:
            out[name] = v.validate_daily_spot_prices(x, "shandong", "2026-08-01")[0]
        a = ShandongAdapter({}, Path(t) / "raw")
        for b in [b"first", b"second", b"second"]:
            a.save_raw_archive(b, "2026-08-01", "csv", {})
        out["same_revision_repeat_files"] = [x.name for x in (Path(t) / "raw").rglob("*.csv")]

    b = FixedPeakValleyStrategy(
        {"soc_initial": 0.5, "soc_final": 0.6}, charging_windows=[], discharging_windows=[]
    ).simulate(df.price_rmb_mwh.to_numpy(), df.timestamp.tolist())
    out["unequal_initial_final_fallback"] = {k: b[k] for k in ["status", "final_soc"]}

    e = BacktestEngine(cfg.get_storage_config(), cfg.get_benchmark_config())
    x = df.copy()
    x["timestamp"] = (pd.to_datetime(x.timestamp) + pd.Timedelta(days=1)).astype(str)
    out["backtest_wrong_timestamp_date_rows"] = len(e.run_backtest(x, "shandong"))

    pipe = runpy.run_path(str(root_path / "scripts/pipeline.py"))
    page = root_path / "public/index.html"
    before = hashlib.sha256(page.read_bytes()).hexdigest()
    pipe["run_pipeline"](backfill_days=1, mode="fixture")
    out["fixture_preserved_preexisting_page"] = before == hashlib.sha256(page.read_bytes()).hexdigest()

    # Clean up results_dir to avoid pre-existing daily_metrics from previous test runs
    metric_file = cfg.get_path("results_dir") / "daily_metrics.parquet"
    if metric_file.exists():
        metric_file.unlink()

    prod = cfg.get_path("spot_prices_parquet")
    prod.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(prod, index=False)

    status = cfg.get_path("status_file")
    status.parent.mkdir(parents=True, exist_ok=True)
    status.write_text(json.dumps({"status": "healthy", "last_success": "prior-success"}))

    with patch.object(
        ShandongAdapter, "ingest_date", return_value=(df, {"source": "audit fault injection", "sha256": "test"})
    ), patch.object(BacktestEngine, "run_backtest", side_effect=RuntimeError("INJECTED_MODEL_FAILURE")):
        try:
            out["model_failure_return"] = pipe["run_pipeline"](backfill_days=1, mode="live")
        except Exception as ex:
            out["model_failure_exception"] = str(ex)

    out["status_after_model_failure"] = json.loads(status.read_text())
    out["metrics_written_before_failure"] = (cfg.get_path("results_dir") / "daily_metrics.parquet").exists()
    out["old_evidence_simulation_values"] = df.is_simulated.unique().tolist()

    print(json.dumps(out, ensure_ascii=False, indent=2))
    if output_path:
        output_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    failures = []
    if out.get("date_column_wrong") is not False:
        failures.append("date_column_wrong was accepted (expected False)")
    if out.get("simulation_null") is not False:
        failures.append("simulation_null was accepted (expected False)")
    if out.get("synthetic_source_false_flag") is not False:
        failures.append("synthetic_source_false_flag was accepted (expected False)")
    reps = out.get("same_revision_repeat_files", [])
    if len(reps) != 2 or any("revision_3" in r for r in reps):
        failures.append(f"same_revision_repeat_files has duplicate revision files: {reps}")
    if out.get("backtest_wrong_timestamp_date_rows") != 0:
        failures.append(f"backtest_wrong_timestamp_date_rows is {out.get('backtest_wrong_timestamp_date_rows')}, expected 0")
    if not out.get("fixture_preserved_preexisting_page"):
        failures.append("fixture pipeline modified public/index.html")
    if out.get("status_after_model_failure", {}).get("status") != "failed":
        failures.append("status after model failure was not 'failed'")
    if out.get("metrics_written_before_failure"):
        failures.append("daily_metrics.parquet was written before model failure (staging leakage)")
    if out.get("old_evidence_simulation_values") != [True]:
        failures.append(f"evidence is_simulated values are {out.get('old_evidence_simulation_values')}, expected [True]")

    if failures:
        print("\nEXTRA PROBE SUITE FAILED:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("\nALL EXTRA PROBE ASSERTIONS PASSED 100% (EXIT CODE: 0)")
        sys.exit(0)

if __name__ == "__main__":
    root_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".").resolve()
    out_arg = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    run_extra_probes(root_arg, out_arg)
