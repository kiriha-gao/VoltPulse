import argparse
import sys
from pathlib import Path

# Add src to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from voltpulse.utils.config import get_config
from voltpulse.utils.logging import get_logger
from voltpulse.storage.database import DatabaseManager
from voltpulse.reporting.dashboard_builder import DashboardBuilder
from voltpulse.reporting.daily_report import DailyReportGenerator
import pandas as pd

logger = get_logger("voltpulse.build_dashboard")


def build(market: str = "shandong"):
    config = get_config()
    results_dir = config.get_path("results_dir")
    parquet_prices = config.get_path("spot_prices_parquet")
    daily_metrics_file = results_dir / "daily_metrics.parquet"
    backtest_file = results_dir / "backtest_results.parquet"

    public_dir = project_root / "public"
    public_html = public_dir / "index.html"
    reports_dir = project_root / "reports" / "daily"

    # Ensure datasets are loaded or fallback to 14-day benchmark fixtures
    if not parquet_prices.exists() or not daily_metrics_file.exists() or not backtest_file.exists():
        prices_df = None
    else:
        try:
            prices_df = pd.read_parquet(parquet_prices)
            metrics_df = pd.read_parquet(daily_metrics_file)
            backtest_df = pd.read_parquet(backtest_file)
            # Filter strictly by requested market to avoid cross-market mixture
            if "market" in prices_df.columns:
                prices_df = prices_df[prices_df["market"] == market]
            if "market" in metrics_df.columns:
                metrics_df = metrics_df[metrics_df["market"] == market]
            if "market" in backtest_df.columns:
                backtest_df = backtest_df[backtest_df["market"] == market]
            if prices_df.empty or metrics_df.empty or backtest_df.empty:
                prices_df = None
        except Exception:
            prices_df = None

    if prices_df is None:
        fixture_filename = f"{market}_sample.csv"
        fixture_path = project_root / "tests" / "fixtures" / fixture_filename
        if not fixture_path.exists():
            raise FileNotFoundError(f"No benchmark fixture for market={market}: {fixture_path}")
        logger.info(f"Production dataset not available for market={market}; using isolated benchmark fixture from {fixture_path.name}...")
        prices_df = pd.read_csv(fixture_path)
        if "market" in prices_df.columns:
            prices_df = prices_df[prices_df["market"] == market]
        from voltpulse.analytics.price_metrics import PriceMetricsCalculator
        from voltpulse.backtest.engine import BacktestEngine
        # Isolated demo output path in sandbox to avoid writing to production results_dir
        demo_dir = project_root / "data" / "sandbox" / "results"
        demo_metrics_file = demo_dir / f"demo_metrics_{market}.parquet"
        metrics_df = PriceMetricsCalculator.compute_and_save_all(prices_df, demo_metrics_file)
        storage_cfg = config.get_storage_config()
        benchmark_cfg = config.get_benchmark_config()
        engine = BacktestEngine(storage_config=storage_cfg, benchmark_config=benchmark_cfg)
        backtest_df = engine.run_backtest(prices_df, market=market)

    # 1. Build Static Dashboard HTML
    logger.info("Compiling mobile-responsive HTML application...")
    storage_cfg = config.get_storage_config()
    DashboardBuilder.build_dashboard(prices_df, metrics_df, backtest_df, public_html, storage_config=storage_cfg)

    # 2. Build Latest Daily Analytical Report (Markdown)
    latest_date = str(metrics_df["date"].max())
    logger.info(f"Generating daily analytical report for {latest_date}...")
    DailyReportGenerator.generate_report(market, latest_date, metrics_df, backtest_df, reports_dir)

    logger.info("=" * 60)
    logger.info(f"DASHBOARD BUILD COMPLETE:")
    logger.info(f"- Web Dashboard: file:///{public_html.as_posix()}")
    logger.info(f"- Daily Report:  file:///{(reports_dir / f'{latest_date}.md').as_posix()}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VoltPulse Dashboard Compiler")
    parser.add_argument("--market", default="shandong", help="Target market (default: shandong)")
    args = parser.parse_args()
    build(market=args.market)
