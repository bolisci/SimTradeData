#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Benchmark script to test download speed for a single stock
"""

import time
from datetime import datetime
from pathlib import Path

from simtradedata.fetchers.baostock_fetcher import BaoStockFetcher
from simtradedata.fetchers.unified_fetcher import UnifiedDataFetcher
from simtradedata.utils.ttm_calculator import get_quarters_in_range

# Test configuration
TEST_SYMBOL = "600000.SS"  # 浦发银行
START_DATE = "2017-01-01"
END_DATE = datetime.now().strftime("%Y-%m-%d")

def main():
    print("=" * 70)
    print("Download Speed Benchmark")
    print("=" * 70)
    print(f"Stock: {TEST_SYMBOL}")
    print(f"Date range: {START_DATE} ~ {END_DATE}")
    print()

    # Initialize fetchers
    unified_fetcher = UnifiedDataFetcher()
    standard_fetcher = BaoStockFetcher()

    unified_fetcher.login()
    standard_fetcher.login()

    try:
        start_time = time.time()

        # 1. Unified daily data (market + valuation + status)
        t1 = time.time()
        unified_df = unified_fetcher.fetch_unified_daily_data(
            TEST_SYMBOL, START_DATE, END_DATE
        )
        t2 = time.time()
        print(f"[1/4] Unified data: {len(unified_df)} rows in {t2-t1:.2f}s")

        # 2. Adjust factor
        t1 = time.time()
        adj_factor = standard_fetcher.fetch_adjust_factor(
            TEST_SYMBOL, START_DATE, END_DATE
        )
        t2 = time.time()
        print(f"[2/4] Adjust factor: {len(adj_factor)} rows in {t2-t1:.2f}s")

        # 3. Basic info + Industry
        t1 = time.time()
        basic_info = standard_fetcher.fetch_stock_basic(TEST_SYMBOL)
        industry_info = standard_fetcher.fetch_stock_industry(TEST_SYMBOL)
        t2 = time.time()
        print(f"[3/4] Basic + Industry: {t2-t1:.2f}s")

        # 4. Quarterly fundamentals
        quarters = get_quarters_in_range(START_DATE, END_DATE)
        print(f"[4/4] Fundamentals: {len(quarters)} quarters to fetch...")

        t1 = time.time()
        total_rows = 0
        for year, quarter in quarters:
            fund_df = standard_fetcher.fetch_quarterly_fundamentals(
                TEST_SYMBOL, year, quarter
            )
            total_rows += len(fund_df)
        t2 = time.time()

        fundamentals_time = t2 - t1
        print(f"      Total: {total_rows} rows in {fundamentals_time:.2f}s")
        print(f"      Average: {fundamentals_time/len(quarters):.2f}s per quarter")
        print(f"      Average: {fundamentals_time/len(quarters)/5:.2f}s per API call")

        end_time = time.time()
        total_time = end_time - start_time

        print()
        print("=" * 70)
        print(f"Total time: {total_time:.2f}s ({total_time/60:.2f} minutes)")
        print("=" * 70)

        # Estimate batch performance
        print("\nBatch performance estimate (20 stocks):")
        print(f"  Expected time: {total_time * 20:.2f}s ({total_time * 20 / 60:.2f} minutes)")

    finally:
        unified_fetcher.logout()
        standard_fetcher.logout()


if __name__ == "__main__":
    main()
