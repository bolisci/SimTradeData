"""
Example: Fetch data for a single stock and save to HDF5

This demonstrates the basic usage of SimTradeData pipeline.
"""

import logging

from simtradedata.pipeline import DataPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def main():
    # Initialize pipeline
    pipeline = DataPipeline(output_dir="data")

    # Example 1: Fetch data for a single stock
    print("=" * 60)
    print("Example 1: Fetch single stock (平安银行 000001.SZ)")
    print("=" * 60)

    with pipeline.fetcher:  # Auto login/logout
        success = pipeline.fetch_and_write_stock(
            symbol="000001.SZ",
            start_date="2023-01-01",
            end_date="2024-12-31",
            include_fundamentals=True,
        )

    if success:
        print("✓ Data fetched successfully!")
        print(f"  Check: data/ptrade_data.h5")
        print(f"  Check: data/ptrade_fundamentals.h5")
        print(f"  Check: data/ptrade_adj_pre.h5")
    else:
        print("✗ Data fetch failed")

    # Example 2: Fetch benchmark index
    print("\n" + "=" * 60)
    print("Example 2: Fetch benchmark (上证综指)")
    print("=" * 60)

    with pipeline.fetcher:
        success = pipeline.fetch_and_write_benchmark(
            start_date="2023-01-01",
            end_date="2024-12-31",
            index_code="000001.SH",  # Shanghai Composite
        )

    if success:
        print("✓ Benchmark data fetched successfully!")

    # Example 3: Fetch multiple stocks
    print("\n" + "=" * 60)
    print("Example 3: Fetch multiple stocks")
    print("=" * 60)

    stock_list = ["000001.SZ", "600000.SH", "000002.SZ"]

    results = pipeline.fetch_and_write_all_stocks(
        stock_list=stock_list,
        start_date="2024-01-01",
        end_date="2024-12-31",
        include_fundamentals=False,  # Skip for speed
        skip_existing=True,
    )

    print(f"\nResults: {results['success']}/{results['total']} successful")

    # Show statistics
    print("\n" + "=" * 60)
    print("File Statistics")
    print("=" * 60)

    import os

    from simtradedata.writers.h5_writer import HDF5Writer

    writer = HDF5Writer(output_dir="data")

    files = {
        "Market Data": writer.ptrade_data_path,
        "Fundamentals": writer.ptrade_fundamentals_path,
        "Adjust Factor": writer.ptrade_adj_pre_path,
    }

    for name, path in files.items():
        if path.exists():
            size_mb = os.path.getsize(path) / (1024 * 1024)
            stock_count = len(writer.get_existing_stocks(name.split()[0].lower()))
            print(f"{name:20s}: {size_mb:8.2f} MB ({stock_count} stocks)")
        else:
            print(f"{name:20s}: Not created yet")


if __name__ == "__main__":
    main()
