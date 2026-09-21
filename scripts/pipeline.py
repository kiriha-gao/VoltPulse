import argparse
import json
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add src to sys.path to allow execution without installation
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root / "src"))

from voltpulse.utils.config import get_config
from voltpulse.utils.logging import get_logger
from voltpulse.ingestion.shandong import ShandongAdapter
from voltpulse.processing.quality import DataQualityValidator
from voltpulse.storage.database import DatabaseManager
from voltpulse.analytics.price_metrics import PriceMetricsCalculator
from voltpulse.backtest.engine import BacktestEngine
from typing import Optional
from voltpulse.optimization.sensitivity import SensitivityAnalyzer

logger = get_logger("voltpulse.pipeline")


def run_pipeline(market_name: str = "shandong", target_date: Optional[str] = None,
                 backfill_days: int = 14, mode: str = "live") -> int:
    """
    Executes VoltPulse data and optimization pipeline conforming strictly to
    V2.0 Specification Section 8, 13 & 17.

    Mode Isolation:
      - mode='fixture': Writes exclusively to data/sandbox/ paths; never touches production assets.
      - mode='live': Connects to production endpoints. Fails hard on network/quality errors;
                     never reports healthy when downloads or quality checks fail.
    """
    logger.info("=" * 60)
    logger.info(f"VOLTPULSE PIPELINE START: mode={mode}, market={market_name}, date={target_date}, days={backfill_days}")
    logger.info("=" * 60)

    now_cst = datetime.now(timezone(timedelta(hours=8)))
    now_iso = now_cst.isoformat()
    next_check_iso = (now_cst + timedelta(hours=24)).strftime("%Y-%m-%dT17:00:00+08:00")

    config = get_config()
    market_cfg = config.get_market_config(market_name)
    storage_cfg = config.get_storage_config()
    benchmark_cfg = config.get_benchmark_config()
    fixtures_dir = config.get_path("fixtures_dir")

    # If target_date is not specified, dynamically resolve:
    # In fixture mode: defaults to benchmark fixture start "2026-08-01"
    # In live mode: defaults to past backfill_days ending on current date in Asia/Shanghai
    if target_date is None:
        if mode == "fixture":
            target_date = "2026-08-01"
            base_dt = datetime.strptime(target_date, "%Y-%m-%d")
            dates_to_run = [(base_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(backfill_days)]
        else:
            end_dt = now_cst
            start_dt = end_dt - timedelta(days=backfill_days - 1)
            dates_to_run = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(backfill_days)]
            target_date = end_dt.strftime("%Y-%m-%d")
    else:
        base_dt = datetime.strptime(target_date, "%Y-%m-%d")
        dates_to_run = [(base_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(backfill_days)]

    # 1. Path & Sandbox Isolation (Spec Section 8 & Reviewer Audit Finding 4)
    if mode == "fixture":
        sandbox_dir = project_root / "data" / "sandbox"
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        raw_dir = sandbox_dir / "raw"
        quality_dir = sandbox_dir / "quality"
        parquet_path = sandbox_dir / "spot_prices.parquet"
        sqlite_path = sandbox_dir / "voltpulse.db"
        results_dir = sandbox_dir / "results"
        status_file = sandbox_dir / "status.json"
        public_html = sandbox_dir / "public" / "index.html"
        reports_dir = sandbox_dir / "reports"
        allow_simulated = True

        fixture_path = fixtures_dir / "shandong_sample.csv"
        adapter = ShandongAdapter(market_cfg, raw_dir, fixture_path=fixture_path)
        logger.info(f"Running in FIXTURE mode: Isolated in sandbox {sandbox_dir}")
    else:
        # Production Paths
        raw_dir = config.get_path("raw_dir")
        quality_dir = config.get_path("quality_dir")
        parquet_path = config.get_path("spot_prices_parquet")
        sqlite_path = config.get_path("database_sqlite")
        results_dir = config.get_path("results_dir")
        status_file = config.get_path("status_file")
        public_html = project_root / "public" / "index.html"
        reports_dir = project_root / "reports" / "daily"
        allow_simulated = False

        adapter = ShandongAdapter(market_cfg, raw_dir, fixture_path=None)
        logger.info("Running in LIVE mode: processing production dataset.")

    results_dir.mkdir(parents=True, exist_ok=True)
    quality_dir.mkdir(parents=True, exist_ok=True)

    validator = DataQualityValidator(
        quality_dir=quality_dir,
        expected_rows_per_day=market_cfg.get("periods_per_day", 96),
        min_price=market_cfg.get("price_limits", {}).get("min", -80.0),
        max_price=market_cfg.get("price_limits", {}).get("max", 1300.0),
        allow_simulated=allow_simulated
    )

    db = DatabaseManager(parquet_path=parquet_path, sqlite_path=sqlite_path)

    # 2. Check and Ingest Dates
    successful_ingestions = 0
    failed_dates = []

    for d in dates_to_run:
        logger.info(f">> Ingestion attempt for date: {d}")
        try:
            normalized_df, meta = adapter.ingest_date(d)
        except Exception as e:
            logger.error(f"Download/Ingestion failed for date {d}: {e}")
            failed_dates.append((d, str(type(e).__name__)))
            continue

        # Quality Audit Gate
        is_valid, quality_report = validator.validate_daily_spot_prices(normalized_df, market_name, d)

        db.record_quality_check(
            market=market_name,
            target_date=d,
            status=quality_report["status"],
            rows=quality_report.get("rows", 0),
            missing=quality_report.get("missing", 0),
            duplicates=quality_report.get("duplicates", 0),
            continuity=quality_report.get("continuity", 0.0),
            report_path=str(quality_dir / f"{d}.json"),
            checked_at=quality_report.get("checked_at", now_iso)
        )

        if not is_valid:
            logger.error(f"Quality gate rejected {d}: {quality_report.get('issues')}")
            failed_dates.append((d, "QUALITY_GATE_FAILURE"))
            continue

        # Atomic Storage Update
        db.append_and_deduplicate(normalized_df)
        db.record_ingestion_batch(
            market=market_name,
            target_date=d,
            rows=len(normalized_df),
            source=meta.get("source", "Unknown"),
            retrieved_at=meta.get("retrieved_at", now_iso),
            sha256=meta.get("sha256", ""),
            status="SUCCESS"
        )
        successful_ingestions += 1

    # In LIVE mode, if any download or quality check failed, report FAIL and do NOT claim healthy
    if mode == "live" and failed_dates:
        err_cat = failed_dates[0][1]
        logger.error(f"LIVE PIPELINE FAILED: {len(failed_dates)} date(s) failed ingestion. Primary error: {err_cat}")
        existing_last_success = _read_existing_last_success(status_file)
        _write_status(
            status_file=status_file,
            status="failed",
            last_attempt=now_iso,
            last_success=existing_last_success,
            next_check=next_check_iso,
            error_category=err_cat,
            market=market_name
        )
        return 1

    # If no data at all exists in database
    all_prices_df = db.load_market_prices(market_name)
    if all_prices_df.empty:
        logger.error("No prices available in database.")
        _write_status(
            status_file=status_file,
            status="unavailable",
            last_attempt=now_iso,
            last_success=None,
            next_check=next_check_iso,
            error_category="NO_DATA",
            market=market_name
        )
        return 1

    # 3. Downstream Processing with Transactional Staging
    stage_dir = results_dir / ".staging"
    if stage_dir.exists():
        shutil.rmtree(stage_dir, ignore_errors=True)
    stage_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 3. Analytics Engine -> Staged Output
        logger.info(">> Running Price Analytics Engine...")
        staged_metrics_file = stage_dir / "daily_metrics.parquet"
        metrics_df = PriceMetricsCalculator.compute_and_save_all(all_prices_df, staged_metrics_file)

        # 4. HiGHS MILP BESS Optimization & Rolling Backtest Engine -> Staged Output
        logger.info(">> Running HiGHS MILP BESS Optimization & Rolling Backtest Engine...")
        backtest_engine = BacktestEngine(storage_config=storage_cfg, benchmark_config=benchmark_cfg)
        backtest_df = backtest_engine.run_backtest(all_prices_df, market=market_name, price_type="day_ahead")
        staged_backtest_file = stage_dir / "backtest_results.parquet"
        BacktestEngine.save_results(backtest_df, staged_backtest_file)

        # 5. Sensitivity Analysis -> Staged Output
        latest_date = db.get_latest_date(market_name) or target_date
        latest_day_prices = all_prices_df[all_prices_df["date"] == latest_date]["price_rmb_mwh"].values
        sensitivity_analyzer = SensitivityAnalyzer.from_config(storage_cfg)
        sensitivity_results = sensitivity_analyzer.analyze(latest_day_prices, interval_minutes=15)
        staged_sensitivity_file = stage_dir / "sensitivity_results.json"
        with open(staged_sensitivity_file, "w", encoding="utf-8") as f:
            json.dump(sensitivity_results, f, ensure_ascii=False, indent=2)

        # 6. Dashboard & Daily Report Generation -> Staged Output
        from voltpulse.reporting.dashboard_builder import DashboardBuilder
        from voltpulse.reporting.daily_report import DailyReportGenerator

        tracked_days = db.get_tracked_days_count(market_name)
        staged_html = stage_dir / "index.html"
        DashboardBuilder.build_dashboard(all_prices_df, metrics_df, backtest_df, staged_html, storage_config=storage_cfg)
        staged_report = stage_dir / f"{latest_date}.md"
        DailyReportGenerator.generate_report(market_name, latest_date, metrics_df, backtest_df, stage_dir)

        # Atomic Commit: copy all staged artifacts to production paths only after 100% success
        results_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        public_html.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(staged_metrics_file, results_dir / "daily_metrics.parquet")
        shutil.copy2(staged_backtest_file, results_dir / "backtest_results.parquet")
        shutil.copy2(staged_sensitivity_file, results_dir / "sensitivity_results.json")
        shutil.copy2(staged_html, public_html)
        if staged_report.exists():
            shutil.copy2(staged_report, reports_dir / f"{latest_date}.md")

        shutil.rmtree(stage_dir, ignore_errors=True)

        # 7. Write Health Status Beacon (5-Level)
        latest_backtest_pf = backtest_df[
            (backtest_df["strategy"] == "perfect_foresight") & (backtest_df["date"] == latest_date)
        ]
        latest_pnl = float(latest_backtest_pf["net_profit"].iloc[0]) if not latest_backtest_pf.empty else 0.0
        total_pnl_pf = float(
            backtest_df[backtest_df["strategy"] == "perfect_foresight"]["net_profit"].sum()
        ) if not backtest_df.empty else 0.0

        status_payload = {
            "status": "healthy",
            "pipeline": "healthy",
            "mode": mode,
            "last_attempt": now_iso,
            "last_success": now_iso,
            "latest_market_date": latest_date,
            "last_data_change": now_iso if successful_ingestions > 0 else _read_existing_last_change(status_file, now_iso),
            "expected_next_check": next_check_iso,
            "error_category": None,
            "market": market_name,
            "data_quality": 1.0,
            "days_tracked": tracked_days,
            "total_records": len(all_prices_df),
            "optimization_engine": {
                "solver": "HiGHS_MILP",
                "integrality": "Binary charge/discharge mutual exclusion u_t in {0, 1}",
                "throughput_formula": "Q = sum_t (eta_c * c_t + d_t / eta_d) * dt",
                "latest_date_net_profit_rmb": round(latest_pnl, 2),
                "cumulative_net_profit_rmb": round(total_pnl_pf, 2),
                "bess_rating": "100MW_200MWh"
            },
            "schema_version": "2.0.0"
        }
        status_file.parent.mkdir(parents=True, exist_ok=True)
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(status_payload, f, ensure_ascii=False, indent=2)

        logger.info("=" * 60)
        logger.info("VOLTPULSE PIPELINE COMPLETED SUCCESSFULLY:")
        logger.info(f"- Mode: {mode}")
        logger.info(f"- Health Status: healthy")
        logger.info(f"- Tracked Days: {tracked_days}")
        logger.info(f"- Latest Market Date: {latest_date}")
        logger.info(f"- Latest Day Storage Net Profit: RMB {latest_pnl:,.2f}")
        logger.info(f"- Cumulative Net Profit: RMB {total_pnl_pf:,.2f}")
        logger.info("=" * 60)
        return 0

    except Exception as err:
        logger.error(f"PIPELINE CRITICAL FAILURE: {err}")
        shutil.rmtree(stage_dir, ignore_errors=True)
        existing_last_success = _read_existing_last_success(status_file)
        _write_status(
            status_file=status_file,
            status="failed",
            last_attempt=now_iso,
            last_success=existing_last_success,
            next_check=next_check_iso,
            error_category=type(err).__name__,
            market=market_name
        )
        return 1


def _read_existing_last_success(status_file: Path) -> str:
    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d.get("last_success")
        except Exception:
            pass
    return None


def _read_existing_last_change(status_file: Path, default_val: str) -> str:
    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d.get("last_data_change", default_val)
        except Exception:
            pass
    return default_val


def _write_status(status_file: Path, status: str, last_attempt: str, last_success: str,
                  next_check: str, error_category: str = None, market: str = "shandong"):
    try:
        payload = {
            "status": status,
            "pipeline": status,
            "last_attempt": last_attempt,
            "last_success": last_success,
            "expected_next_check": next_check,
            "error_category": error_category,
            "market": market,
            "schema_version": "2.0.0"
        }
        status_file.parent.mkdir(parents=True, exist_ok=True)
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as err:
        logger.error(f"Failed to write status beacon: {err}")


def main():
    parser = argparse.ArgumentParser(description="VoltPulse Daily Ingestion & Optimization Pipeline")
    parser.add_argument("--market", default="shandong", help="Market name (default: shandong)")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (defaults to Asia/Shanghai today for live, 2026-08-01 for fixture)")
    parser.add_argument("--backfill-days", type=int, default=14, help="Number of days to ingest/backfill")
    parser.add_argument("--mode", default="live", choices=["live", "fixture"], help="Pipeline mode: live or fixture")
    parser.add_argument("--offline", action="store_true", help="Deprecated alias for --mode fixture")

    args = parser.parse_args()
    mode = "fixture" if args.offline else args.mode

    exit_code = run_pipeline(
        market_name=args.market,
        target_date=args.date,
        backfill_days=args.backfill_days,
        mode=mode
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
