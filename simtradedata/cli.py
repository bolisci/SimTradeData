"""
Command-line interface for SimTradeData
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta

from simtradedata.pipeline import DataPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("simtradedata.log"),
    ],
)

logger = logging.getLogger(__name__)


def cmd_fetch_all(args):
    """Fetch data for all stocks"""
    logger.info("Starting full data fetch...")
    logger.info(f"Using {args.market_source} for K-line market data")
    if args.market_source == "mootdx":
        logger.info("Fast mode enabled - K-line download will be much faster")

    if args.only_fundamentals:
        logger.info("Only-fundamentals mode - skipping market/valuation/adjust data")

    logger.warning(
        "BaoStock only supports sequential downloads - this may take a while"
    )

    pipeline = DataPipeline(
        output_dir=args.output_dir,
        market_source=args.market_source,
    )

    results = pipeline.fetch_and_write_all_stocks(
        start_date=args.start_date,
        end_date=args.end_date,
        include_fundamentals=not args.skip_fundamentals,
        only_fundamentals=args.only_fundamentals,
        skip_existing=not args.overwrite,
    )

    logger.info(
        f"Fetch completed: {results['success']}/{results['total']} stocks successful"
    )


def cmd_fetch_stock(args):
    """Fetch data for specific stocks"""
    symbols = args.symbols.split(",")
    logger.info(f"Fetching data for {len(symbols)} stocks: {symbols}")
    logger.info(f"Using {args.market_source} for K-line market data")

    pipeline = DataPipeline(
        output_dir=args.output_dir,
        market_source=args.market_source,
    )

    with pipeline.market_fetcher, pipeline.baostock_fetcher:
        for symbol in symbols:
            success = pipeline.fetch_and_write_stock(
                symbol=symbol.strip(),
                start_date=args.start_date,
                end_date=args.end_date,
                include_fundamentals=not args.skip_fundamentals,
            )

            if success:
                logger.info(f"✓ {symbol} completed")
            else:
                logger.error(f"✗ {symbol} failed")


def cmd_fetch_benchmark(args):
    """Fetch benchmark index data"""
    logger.info(f"Fetching benchmark index: {args.index_code}")

    pipeline = DataPipeline(output_dir=args.output_dir)

    with pipeline.fetcher:
        success = pipeline.fetch_and_write_benchmark(
            start_date=args.start_date,
            end_date=args.end_date,
            index_code=args.index_code,
        )

    if success:
        logger.info("✓ Benchmark data fetched successfully")
    else:
        logger.error("✗ Benchmark data fetch failed")


def cmd_update(args):
    """Incremental update of existing data"""
    logger.info(f"Updating data for last {args.days} days...")

    pipeline = DataPipeline(output_dir=args.output_dir)

    results = pipeline.incremental_update(days=args.days)

    logger.info(
        f"Update completed: {results['success']}/{results['total']} stocks updated"
    )


def cmd_validate(args):
    """Validate HDF5 files"""
    logger.info(f"Validating HDF5 files in {args.output_dir}...")

    from simtradedata.writers.h5_writer import HDF5Writer

    writer = HDF5Writer(output_dir=args.output_dir)

    # Check file integrity
    files = ["market", "fundamentals", "adjust"]
    for file_type in files:
        is_valid = writer.check_file_integrity(file_type)
        status = "✓" if is_valid else "✗"
        logger.info(f"{status} {file_type} file: {is_valid}")

        if is_valid:
            stocks = writer.get_existing_stocks(file_type)
            logger.info(f"  - Contains {len(stocks)} stocks")


def cmd_stats(args):
    """Show statistics of HDF5 files"""

    from simtradedata.writers.h5_writer import HDF5Writer

    logger.info(f"Statistics for {args.output_dir}...")

    writer = HDF5Writer(output_dir=args.output_dir)

    # Market data stats
    market_stocks = writer.get_existing_stocks("market")
    logger.info(f"Market data: {len(market_stocks)} stocks")

    # Fundamentals stats
    fund_stocks = writer.get_existing_stocks("fundamentals")
    logger.info(f"Fundamentals data: {len(fund_stocks)} stocks")

    # Adjust factor stats
    adj_stocks = writer.get_existing_stocks("adjust")
    logger.info(f"Adjust factor data: {len(adj_stocks)} stocks")

    # File sizes
    import os

    files = {
        "ptrade_data.h5": writer.ptrade_data_path,
        "ptrade_fundamentals.h5": writer.ptrade_fundamentals_path,
        "ptrade_adj_pre.h5": writer.ptrade_adj_pre_path,
    }

    logger.info("\nFile sizes:")
    for name, path in files.items():
        if path.exists():
            size_mb = os.path.getsize(path) / (1024 * 1024)
            logger.info(f"  - {name}: {size_mb:.2f} MB")
        else:
            logger.info(f"  - {name}: Not found")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="SimTradeData - Generate PTrade-compatible HDF5 data files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--version", action="version", version="SimTradeData 0.1.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # fetch-all command
    parser_fetch_all = subparsers.add_parser(
        "fetch-all", help="Fetch data for all stocks"
    )
    parser_fetch_all.add_argument(
        "--start-date",
        default=(datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d"),
        help="Start date (YYYY-MM-DD), default: 5 years ago",
    )
    parser_fetch_all.add_argument(
        "--end-date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD), default: today",
    )
    parser_fetch_all.add_argument(
        "--output-dir", default="data", help="Output directory for HDF5 files"
    )
    parser_fetch_all.add_argument(
        "--skip-fundamentals",
        action="store_true",
        help="Skip fundamental data (faster)",
    )
    parser_fetch_all.add_argument(
        "--only-fundamentals",
        action="store_true",
        help="Only download fundamentals (skip market/valuation/adjust data)",
    )
    parser_fetch_all.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing data"
    )
    parser_fetch_all.add_argument(
        "--market-source",
        choices=["baostock", "mootdx"],
        default="mootdx",
        help="Data source for K-line market data (default: mootdx for speed)",
    )
    parser_fetch_all.set_defaults(func=cmd_fetch_all)

    # fetch command
    parser_fetch = subparsers.add_parser("fetch", help="Fetch data for specific stocks")
    parser_fetch.add_argument(
        "symbols", help="Comma-separated stock codes (e.g., 000001.SZ,600000.SH)"
    )
    parser_fetch.add_argument(
        "--start-date",
        default=(datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d"),
        help="Start date (YYYY-MM-DD)",
    )
    parser_fetch.add_argument(
        "--end-date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD)",
    )
    parser_fetch.add_argument("--output-dir", default="data", help="Output directory")
    parser_fetch.add_argument(
        "--skip-fundamentals", action="store_true", help="Skip fundamental data"
    )
    parser_fetch.add_argument(
        "--market-source",
        choices=["baostock", "mootdx"],
        default="mootdx",
        help="Data source for K-line market data (default: mootdx for speed)",
    )
    parser_fetch.set_defaults(func=cmd_fetch_stock)

    # fetch-benchmark command
    parser_benchmark = subparsers.add_parser(
        "fetch-benchmark", help="Fetch benchmark index data"
    )
    parser_benchmark.add_argument(
        "--index-code",
        default="000001.SH",
        help="Index code (default: 000001.SH for Shanghai Composite)",
    )
    parser_benchmark.add_argument(
        "--start-date",
        default=(datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d"),
        help="Start date (YYYY-MM-DD)",
    )
    parser_benchmark.add_argument(
        "--end-date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD)",
    )
    parser_benchmark.add_argument(
        "--output-dir", default="data", help="Output directory"
    )
    parser_benchmark.set_defaults(func=cmd_fetch_benchmark)

    # update command
    parser_update = subparsers.add_parser(
        "update", help="Incrementally update existing data"
    )
    parser_update.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to update (default: 30)",
    )
    parser_update.add_argument("--output-dir", default="data", help="Output directory")
    parser_update.set_defaults(func=cmd_update)

    # validate command
    parser_validate = subparsers.add_parser("validate", help="Validate HDF5 files")
    parser_validate.add_argument(
        "--output-dir", default="data", help="Directory containing HDF5 files"
    )
    parser_validate.set_defaults(func=cmd_validate)

    # stats command
    parser_stats = subparsers.add_parser("stats", help="Show file statistics")
    parser_stats.add_argument(
        "--output-dir", default="data", help="Directory containing HDF5 files"
    )
    parser_stats.set_defaults(func=cmd_stats)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    try:
        args.func(args)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
