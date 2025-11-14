"""
Data pipeline for fetching, converting, and writing PTrade-compatible data
"""

import logging
from datetime import datetime, timedelta
from typing import List, Literal, Optional

from tqdm import tqdm

from simtradedata.converters.data_converter import DataConverter
from simtradedata.fetchers.baostock_fetcher import BaoStockFetcher
from simtradedata.fetchers.mootdx_fetcher import MootdxFetcher
from simtradedata.utils.code_utils import convert_to_ptrade_code
from simtradedata.writers.h5_writer import HDF5Writer

logger = logging.getLogger(__name__)


class DataPipeline:
    """
    End-to-end data pipeline for generating PTrade-compatible HDF5 files

    This orchestrates:
    1. Fetching data from multiple sources (Mootdx for K-line, BaoStock for others)
    2. Converting to PTrade format
    3. Writing to HDF5 files

    Hybrid Data Source Strategy:
    - K-line market data (OHLCV): Mootdx (fast, ~0.2s per stock)
    - Valuation, adjust, dividend, fundamentals: BaoStock (comprehensive)
    """

    def __init__(
        self,
        output_dir: str = "data",
        market_source: Literal["baostock", "mootdx"] = "mootdx",
    ):
        """
        Initialize data pipeline

        Args:
            output_dir: Directory to save HDF5 files
            market_source: Data source for K-line market data
                - "mootdx" (default): Fast, reliable (recommended)
                - "baostock": Slower but includes valuation in same call

        Note:
            Regardless of market_source, valuation/adjust/dividend/fundamentals
            always come from BaoStock (Mootdx doesn't provide these).
        """
        self.market_source = market_source

        # Initialize fetchers based on market_source
        if market_source == "mootdx":
            self.market_fetcher = MootdxFetcher()
            logger.info("Using Mootdx for K-line market data (fast mode)")
        else:
            self.market_fetcher = BaoStockFetcher()
            logger.info("Using BaoStock for K-line market data")

        # Always use BaoStock for non-market data
        self.baostock_fetcher = BaoStockFetcher()

        self.converter = DataConverter()
        self.writer = HDF5Writer(output_dir=output_dir)

    def cleanup(self):
        """Cleanup resources (ensure logout from all fetchers)"""
        try:
            if hasattr(self, "market_fetcher"):
                self.market_fetcher.logout()
        except Exception as e:
            logger.warning(f"Market fetcher cleanup error: {e}")

        try:
            if hasattr(self, "baostock_fetcher"):
                self.baostock_fetcher.logout()
        except Exception as e:
            logger.warning(f"BaoStock fetcher cleanup error: {e}")

    def __enter__(self):
        """Context manager entry"""
        if self.market_source == "baostock":
            self.market_fetcher.login()
        else:
            self.market_fetcher.login()  # No-op for Mootdx
        self.baostock_fetcher.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup"""
        self.cleanup()
        return False

    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            self.cleanup()
        except:
            pass

    def fetch_and_write_stock(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        include_fundamentals: bool = True,
        only_fundamentals: bool = False,
        silent: bool = False,
    ) -> bool:
        """
        Fetch and write all data for a single stock

        Args:
            symbol: Stock code in PTrade format (e.g., '000001.SZ')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            include_fundamentals: Whether to fetch fundamental data
            only_fundamentals: If True, only fetch fundamentals (skip market/valuation/adjust)
            silent: If True, suppress INFO logs (to avoid interrupting progress bars)

        Returns:
            True if successful, False otherwise
        """
        try:
            if not silent:
                logger.info(f"Processing {symbol}...")

            # If only_fundamentals is True, skip market/valuation/adjust data
            if not only_fundamentals:
                # 1. Fetch market data from chosen source
                market_df = self.market_fetcher.fetch_market_data(
                    symbol, start_date, end_date
                )
                market_df = self.converter.convert_market_data(market_df, symbol)

                # 2. Fetch valuation data from BaoStock
                valuation_df = self.baostock_fetcher.fetch_valuation_data(
                    symbol, start_date, end_date
                )
                valuation_df = self.converter.convert_valuation_data(
                    valuation_df, market_df, symbol
                )

                # 3. Fetch adjust factor from BaoStock
                adjust_df = self.baostock_fetcher.fetch_adjust_factor(
                    symbol, start_date, end_date
                )
                adjust_series = self.converter.convert_adjust_factor(adjust_df, symbol)

                # 4. Fetch dividend data (for exrights) from BaoStock
                current_year = datetime.now().year
                dividend_dfs = []
                for year in range(int(start_date[:4]), current_year + 1):
                    div_df = self.baostock_fetcher.fetch_dividend_data(symbol, year)
                    if not div_df.empty:
                        dividend_dfs.append(div_df)

                if dividend_dfs:
                    import pandas as pd

                    dividend_df = pd.concat(dividend_dfs, ignore_index=True)
                    exrights_df = self.converter.convert_exrights_data(
                        dividend_df, adjust_df, symbol
                    )
                else:
                    exrights_df = None

                # 5. Fetch stock basic info from BaoStock
                basic_df = self.baostock_fetcher.fetch_stock_basic(symbol)
                metadata = self.converter.convert_stock_metadata(basic_df, symbol)
            else:
                # Skip all non-fundamental data
                market_df = None
                valuation_df = None
                adjust_series = None
                exrights_df = None
                metadata = None

            # 6. Fetch fundamentals if requested (from BaoStock)
            fundamentals_df = None
            if include_fundamentals:
                # Fetch quarterly data for recent years
                start_year = int(start_date[:4])
                end_year = int(end_date[:4])

                all_profit = []
                all_operation = []
                all_growth = []
                all_balance = []

                for year in range(start_year, end_year + 1):
                    for quarter in range(1, 5):
                        profit_df = self.baostock_fetcher.fetch_profit_data(
                            symbol, year, quarter
                        )
                        operation_df = self.baostock_fetcher.fetch_operation_data(
                            symbol, year, quarter
                        )
                        growth_df = self.baostock_fetcher.fetch_growth_data(
                            symbol, year, quarter
                        )
                        balance_df = self.baostock_fetcher.fetch_balance_data(
                            symbol, year, quarter
                        )

                        if not profit_df.empty:
                            all_profit.append(profit_df)
                        if not operation_df.empty:
                            all_operation.append(operation_df)
                        if not growth_df.empty:
                            all_growth.append(growth_df)
                        if not balance_df.empty:
                            all_balance.append(balance_df)

                import pandas as pd

                profit_combined = (
                    pd.concat(all_profit, ignore_index=True)
                    if all_profit
                    else pd.DataFrame()
                )
                operation_combined = (
                    pd.concat(all_operation, ignore_index=True)
                    if all_operation
                    else pd.DataFrame()
                )
                growth_combined = (
                    pd.concat(all_growth, ignore_index=True)
                    if all_growth
                    else pd.DataFrame()
                )
                balance_combined = (
                    pd.concat(all_balance, ignore_index=True)
                    if all_balance
                    else pd.DataFrame()
                )
                cash_combined = pd.DataFrame()  # Not fetched yet

                fundamentals_df = self.converter.convert_fundamentals(
                    profit_combined,
                    operation_combined,
                    growth_combined,
                    balance_combined,
                    cash_combined,
                    symbol,
                )

            # 7. Write all data
            self.writer.write_all_for_stock(
                symbol=symbol,
                market_data=market_df,
                valuation_data=valuation_df,
                fundamentals_data=fundamentals_df,
                adjust_factor=adjust_series,
                exrights_data=exrights_df,
                metadata=metadata,
            )

            if not silent:
                logger.info(f"Successfully processed {symbol}")
            return True

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}", exc_info=True)
            return False

    def fetch_and_write_benchmark(
        self, start_date: str, end_date: str, index_code: str = "000001.SH"
    ) -> bool:
        """
        Fetch and write benchmark index data

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            index_code: Index code (default: Shanghai Composite)

        Returns:
            True if successful
        """
        try:
            logger.info(f"Fetching benchmark index {index_code}...")

            # Fetch index data
            benchmark_df = self.fetcher.fetch_market_data(
                index_code, start_date, end_date
            )
            benchmark_df = self.converter.convert_market_data(benchmark_df, index_code)

            # Write to file
            self.writer.write_benchmark(benchmark_df)

            logger.info(f"Successfully wrote benchmark data: {len(benchmark_df)} rows")
            return True

        except Exception as e:
            logger.error(f"Error processing benchmark: {e}", exc_info=True)
            return False

    def fetch_and_write_all_stocks(
        self,
        stock_list: Optional[List[str]] = None,
        start_date: str = None,
        end_date: str = None,
        include_fundamentals: bool = True,
        only_fundamentals: bool = False,
        skip_existing: bool = True,
    ) -> dict:
        """
        Fetch and write data for multiple stocks

        Args:
            stock_list: List of stock codes in PTrade format.
                       If None, fetch all A-share stocks
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            include_fundamentals: Whether to fetch fundamental data
            only_fundamentals: If True, only fetch fundamentals (skip market data)
            skip_existing: Skip stocks already in HDF5 file

        Returns:
            Dictionary with success/failure counts
        """
        # Default date range: last 5 years
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")

        # Get stock list
        if stock_list is None:
            logger.info("Fetching stock list from BaoStock...")
            with self.baostock_fetcher:
                stock_df = self.baostock_fetcher.fetch_stock_list()
                stock_list = [
                    convert_to_ptrade_code(code, "baostock")
                    for code in stock_df["code"].tolist()
                ]
            logger.info(f"Found {len(stock_list)} stocks")

        # Filter existing stocks if needed
        if skip_existing:
            existing = self.writer.get_existing_stocks("market")
            stock_list = [s for s in stock_list if s not in existing]
            # Important: Use print to bypass logging suppression
            print(
                f"[INFO] Skipping {len(existing)} existing stocks, {len(stock_list)} remaining"
            )
            logger.info(
                f"Skipping {len(existing)} existing stocks, "
                f"{len(stock_list)} remaining"
            )

        # Process stocks sequentially (BaoStock doesn't support concurrent requests)
        results = {"success": 0, "failure": 0, "total": len(stock_list)}

        # Temporarily raise logging level to ERROR to prevent INFO/WARNING messages
        # from interrupting the progress bar
        root_logger = logging.getLogger()
        original_level = root_logger.level
        root_logger.setLevel(logging.ERROR)

        try:
            # Login to both fetchers
            with self.market_fetcher, self.baostock_fetcher:
                # Use tqdm progress bar
                with tqdm(
                    total=len(stock_list),
                    desc="Downloading stocks",
                    unit="stock",
                    disable=None,  # Auto-detect if terminal supports progress bar
                    file=None,  # Use default stderr output
                ) as pbar:
                    for symbol in stock_list:
                        pbar.set_postfix_str(f"Current: {symbol}")

                        try:
                            success = self.fetch_and_write_stock(
                                symbol,
                                start_date,
                                end_date,
                                include_fundamentals,
                                only_fundamentals,  # Pass through only_fundamentals flag
                                silent=True,  # Suppress logs to avoid interrupting progress bar
                            )

                            if success:
                                results["success"] += 1
                            else:
                                results["failure"] += 1
                        except Exception as e:
                            tqdm.write(f"ERROR: Unexpected error for {symbol}: {e}")
                            results["failure"] += 1

                        pbar.update(1)
                        pbar.set_postfix_str(
                            f"✓ {results['success']} | ✗ {results['failure']}"
                        )
        finally:
            # Restore original logging level
            root_logger.setLevel(original_level)

        logger.info(
            f"Completed: {results['success']}/{results['total']} stocks successful"
        )

        return results

    def incremental_update(
        self,
        stock_list: Optional[List[str]] = None,
        days: int = 30,
    ) -> dict:
        """
        Incrementally update existing data

        Args:
            stock_list: List of stocks to update. If None, update all existing
            days: Number of days to update (default: last 30 days)

        Returns:
            Dictionary with update results
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        if stock_list is None:
            # Get all existing stocks
            stock_list = self.writer.get_existing_stocks("market")
            logger.info(f"Updating {len(stock_list)} existing stocks")

        return self.fetch_and_write_all_stocks(
            stock_list=stock_list,
            start_date=start_date,
            end_date=end_date,
            include_fundamentals=False,  # Skip fundamentals for incremental update
            skip_existing=False,
        )
