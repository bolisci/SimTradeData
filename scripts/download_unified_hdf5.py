# -*- coding: utf-8 -*-
"""
Download all data types to unified HDF5 file using BaoStock backend
Compatible with PTrade data format
"""

import json
import logging
import warnings

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from tables import NaturalNameWarning
from tqdm import tqdm

# Import PTrade-compatible API
from simtradedata.fetchers.baostock_fetcher import BaoStockFetcher
from simtradedata.interfaces.ptrade_data_api import (
    get_Ashares,
    get_index_stocks,
    get_price,
    get_stock_blocks,
    get_stock_exrights,
    get_stock_info,
    get_stock_status,
    get_trade_days,
)

warnings.filterwarnings("ignore", category=NaturalNameWarning)

# Configuration
OUTPUT_FILE = "ptrade_data.h5"
LOG_FILE = "download_unified.log"
CHECKPOINT_INTERVAL = 100


HDF5_COMPLEVEL = 9
HDF5_COMPLIB = "blosc"

# Data fields
REQUIRED_PRICE_FIELDS = ["close", "open", "high", "low", "volume", "money"]

# Date range configuration
START_DATE = "2017-01-01"
END_DATE = None  # None means use current date
INCREMENTAL_DAYS = None  # Set to N to only update last N days for incremental updates)

# Logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
)
logger = logging.getLogger(__name__)


# Download functions
def download_stock_price(stock, start_date, end_date):
    """Download price data"""
    try:
        price_data = get_price(
            stock,
            start_date=start_date,
            end_date=end_date,
            frequency="1d",
            fields=REQUIRED_PRICE_FIELDS,
            fq="none",
        )
        if price_data is None or len(price_data) < 60:
            return None

        if isinstance(price_data, dict):
            df = pd.DataFrame(price_data)
        else:
            df = price_data

        # Ensure numeric column types for PyTables
        for col in REQUIRED_PRICE_FIELDS:
            if col in df.columns:
                df[col] = df[col].astype("float64")

        return df
    except Exception as e:
        logger.error("Price download failed: {} - {}".format(stock, e))
        return None


def download_stock_metadata(stock):
    """Download metadata"""
    metadata = {}
    info_success = False
    try:
        info = get_stock_info(
            stock, field=["stock_name", "listed_date", "de_listed_date"]
        )
        if info and stock in info:
            stock_info = info[stock]
            metadata["stock_name"] = stock_info.get("stock_name")
            metadata["listed_date"] = stock_info.get("listed_date")
            metadata["de_listed_date"] = stock_info.get("de_listed_date")
            info_success = True
        else:
            logger.warning("Stock info not found: {}".format(stock))
    except Exception as e:
        logger.warning("Failed to get stock info: {} - {}".format(stock, e))

    try:
        metadata["blocks"] = get_stock_blocks(stock)
    except Exception as e:
        logger.warning("Failed to get blocks: {} - {}".format(stock, e))
        metadata["blocks"] = []

    metadata["has_info"] = info_success
    return metadata


def download_stock_exrights(stock):
    """Download ex-rights data"""
    try:
        data = get_stock_exrights(stock)
        if data is not None and len(data) > 0:
            return data
    except Exception as e:
        logger.error("Ex-rights download failed: {} - {}".format(stock, e))
    return None





def download_index_constituents(sample_dates):
    """Download index constituents (quarterly sampling)"""
    indices = {
        "000016.SS": "SSE 50",
        "000300.SS": "CSI 300",
        "000905.SS": "CSI 500",
    }

    constituents = {}
    print("\nDownloading index constituents...")

    for date_obj in tqdm(sample_dates, desc="Downloading index constituents"):
        date_str = date_obj.strftime("%Y%m%d")
        constituents[date_str] = {}

        for index_code, index_name in indices.items():
            try:
                stocks = get_index_stocks(index_code, date=date_str)
                if stocks:
                    constituents[date_str][index_code] = stocks
                    logger.info(
                        "Index constituents: {} {} - {} stocks".format(
                            date_str, index_name, len(stocks)
                        )
                    )
                else:
                    constituents[date_str][index_code] = []
            except Exception as e:
                logger.error(
                    "Index constituents download failed: {} {} - {}".format(
                        date_str, index_name, e
                    )
                )
                constituents[date_str][index_code] = []

    return constituents


def download_stock_status_history(
    stocks, sample_dates, start_date, end_date, fetcher
):
    """Download stock status history (ST/HALT/DELISTING)"""
    status_types = ["ST", "HALT", "DELISTING"]
    status_history = {}

    print("\nDownloading stock status history...")

    # Optimized: Fetch all delisting info at once
    all_stock_basics = _get_all_stock_basics(stocks, fetcher)

    # Optimized: Fetch all ST history at once
    st_history = _get_st_stock_history(stocks, start_date, end_date, fetcher)

    for date_obj in tqdm(sample_dates, desc="Processing stock status history"):
        date_str = date_obj.strftime("%Y%m%d")
        date_iso = date_obj.strftime("%Y-%m-%d")
        status_history[date_str] = {}

        for status_type in status_types:
            try:
                result = {}
                if status_type == "DELISTING":
                    # Use pre-fetched data
                    date_int = int(date_iso.replace("-", ""))
                    for stock, basic_info in all_stock_basics.items():
                        is_delisted = basic_info["status"] == "0"
                        out_date = basic_info["outDate"]
                        if not is_delisted and out_date and out_date.strip():
                            out_date_int = int(out_date.replace("-", ""))
                            if date_int >= out_date_int:
                                is_delisted = True
                        if is_delisted:
                            result[stock] = True

                elif status_type == "ST":
                    # Use pre-fetched history
                    for stock, st_df in st_history.items():
                        if not st_df.empty:
                            # Check if the date is in the history
                            if pd.Timestamp(date_iso) in st_df.index:
                                if st_df.loc[pd.Timestamp(date_iso)]["isST"] == "1":
                                    result[stock] = True

                elif status_type == "HALT":
                    # Use the optimized API call
                    result = get_stock_status(
                        stocks, query_type="HALT", query_date=date_str
                    )

                if result:
                    # Only save True values to save space
                    status_history[date_str][status_type] = {
                        k: v for k, v in result.items() if v
                    }
                    count = len(status_history[date_str][status_type])
                    if count > 0:
                        logger.info(
                            "Stock status: {} {} - {} stocks".format(
                                date_str, status_type, count
                            )
                        )
                else:
                    status_history[date_str][status_type] = {}

            except Exception as e:
                logger.error(
                    "Stock status processing failed: {} {} - {}".format(
                        date_str, status_type, e
                    )
                )
                status_history[date_str][status_type] = {}

    return status_history


def _get_all_stock_basics(stocks, fetcher):
    """Helper to fetch basic info for all stocks at once."""
    print("Fetching all stock basic info for delisting checks...")
    all_stock_basics = {}
    for stock in tqdm(stocks, desc="Fetching stock basics"):
        try:
            basic_df = fetcher.fetch_stock_basic(stock)
            if basic_df is not None and not basic_df.empty:
                all_stock_basics[stock] = {
                    "status": str(basic_df["status"].values[0]),
                    "outDate": basic_df["outDate"].values[0],
                }
        except Exception as e:
            logger.error(f"Failed to get basic info for {stock}: {e}")
    return all_stock_basics


def _get_st_stock_history(stocks, start_date, end_date, fetcher):
    """Helper to fetch ST history for all stocks in a date range."""
    print("Fetching ST history for all stocks...")
    st_history = {}
    for stock in tqdm(stocks, desc="Fetching ST history"):
        try:
            df = fetcher.fetch_market_data(
                symbol=stock,
                start_date=start_date,
                end_date=end_date,
                extra_fields=["isST"],
            )
            if df is not None and not df.empty:
                df = df.set_index("date")
                # Filter for only ST days to save memory
                st_days = df[df["isST"] == "1"]
                if not st_days.empty:
                    st_history[stock] = st_days

        except Exception as e:
            logger.error(f"Failed to get ST history for {stock}: {e}")
            st_history[stock] = pd.DataFrame()

    return st_history


def download_trade_days(start_date, end_date):
    """Download trading calendar"""
    try:
        trade_days = get_trade_days(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
        if trade_days:
            df = pd.DataFrame({"trade_date": pd.to_datetime(trade_days)})
            df.set_index("trade_date", inplace=True)
            logger.info(
                "Trading calendar downloaded: {} trading days".format(len(trade_days))
            )
            return df
        return None
    except Exception as e:
        logger.error("Trading calendar download failed: {}".format(e))
        return None


# Main download process
from simtradedata.writers.h5_writer import HDF5Writer

# Main download process
def download_all_data(incremental_days=None):
    """
    Download all data to single HDF5 file

    Args:
        incremental_days: If set, only update last N days for existing stocks
    """
    print("=" * 70)
    if incremental_days:
        print("Incremental update: last {} days".format(incremental_days))
    else:
        print("Download all data to unified HDF5 file")
    print("=" * 70)

    # Date range
    end_date = (
        datetime.now().date()
        if END_DATE is None
        else datetime.strptime(END_DATE, "%Y-%m-%d").date()
    )

    # Initialize HDF5 writer
    writer = HDF5Writer(output_dir=".")
    
    # For a full download, we don't delete the file, allowing for resume.
    # The user should delete the file manually if a full-from-scratch download is needed.
    if not incremental_days:
        print("Full download mode. Will resume if file exists.")
    
    start_date = datetime.strptime(START_DATE, "%Y-%m-%d").date()
    if incremental_days:
        # For incremental mode, only fetch data for the last N days
        start_date = end_date - timedelta(days=incremental_days)
        print("\nIncremental mode: updating last {} days".format(incremental_days))

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    print("\nDate range: {} ~ {}".format(start_date_str, end_date_str))

    # --- Get Full Stock Pool ---
    print("\nGetting full stock pool...")
    full_stock_pool = []
    
    # To get the full list, we sample across the entire history
    full_start_date = datetime.strptime(START_DATE, "%Y-%m-%d").date()
    sample_dates = (
        pd.date_range(start=full_start_date, end=end_date, freq="QS")
        .to_pydatetime()
        .tolist()
    )
    if end_date not in [d.date() for d in sample_dates]:
        sample_dates.append(datetime.combine(end_date, datetime.min.time()))

    all_stocks = set()
    for date_obj in tqdm(sample_dates, desc="Getting full stock list"):
        date_str = date_obj.strftime("%Y-%m-%d")
        try:
            stocks = get_Ashares(date_str)
            if stocks:
                all_stocks.update(stocks)
        except Exception as e:
            logger.error("Failed to get stock pool: {} - {}".format(date_str, e))
    
    full_stock_pool = sorted(list(all_stocks))
    print("  Full stock pool: {} stocks".format(len(full_stock_pool)))
    
    # --- Determine Stocks to Download ---
    existing_stocks = set(writer.get_existing_stocks(file_type="market"))
    
    if incremental_days:
        # In incremental mode, we only process stocks that are already in the file.
        stock_pool = sorted(list(existing_stocks))
        need_to_download = stock_pool
        print(f"\nIncremental mode: processing {len(stock_pool)} existing stocks.")
    else:
        # In full download mode, download all stocks not already present.
        stock_pool = full_stock_pool
        need_to_download = [s for s in stock_pool if s not in existing_stocks]
        print(f"\nFull mode: {len(existing_stocks)} stocks already exist.")
        print(f"  Need to download {len(need_to_download)} new stocks.")

    if not need_to_download:
        print("\nAll required stock data already exists. Nothing to download.")
    else:
        # --- Main Download Loop ---
        fetcher = BaoStockFetcher()
        fetcher.login()
        try:
            # Download and write data serially
            print("\nDownloading and writing stock data...")
            metadata_list = [] # Still collect metadata to write at the end
            success = 0
            fail = 0

            for stock in tqdm(need_to_download, desc="Downloading stock data"):
                try:
                    price_df = download_stock_price(stock, start_date_str, end_date_str)
                    if price_df is not None:
                        writer.write_market_data(stock, price_df, mode='a')

                    meta = download_stock_metadata(stock)
                    metadata_list.append({
                        "stock_code": stock,
                        "stock_name": meta.get("stock_name"),
                        "listed_date": meta.get("listed_date"),
                        "de_listed_date": meta.get("de_listed_date"),
                        "blocks": json.dumps(meta.get("blocks", {}), ensure_ascii=False) if meta.get("blocks") else None,
                        "has_info": meta.get("has_info", False),
                    })

                    ex_df = download_stock_exrights(stock)
                    if ex_df is not None:
                        writer.write_exrights(stock, ex_df, mode='a')
                    
                    success += 1
                except Exception as e:
                    logger.error("Download failed for {}: {}".format(stock, e))
                    fail += 1
            
            print(f"\nDownload summary: {success} success, {fail} failed.")

        finally:
            fetcher.logout()

    # --- Update Metadata and Other Global Data ---
    # This part runs regardless of whether new stocks were downloaded,
    # to ensure metadata is up-to-date.
    
    print("\nUpdating metadata and global data...")
    fetcher = BaoStockFetcher()
    fetcher.login()
    try:
        # Get metadata for ALL stocks in the pool (new and old)
        all_metadata_list = []
        print("Fetching metadata for all stocks...")
        for stock in tqdm(stock_pool, desc="Fetching metadata"):
            meta = download_stock_metadata(stock)
            all_metadata_list.append({
                "stock_code": stock,
                "stock_name": meta.get("stock_name"),
                "listed_date": meta.get("listed_date"),
                "de_listed_date": meta.get("de_listed_date"),
                "blocks": json.dumps(meta.get("blocks", {}), ensure_ascii=False) if meta.get("blocks") else None,
                "has_info": meta.get("has_info", False),
            })
        
        if all_metadata_list:
            meta_df = pd.DataFrame(all_metadata_list)
            meta_df.set_index("stock_code", inplace=True)
            meta_df = meta_df.sort_index()
            # Use 'w' mode for metadata to overwrite with the complete list
            writer.write_stock_metadata(meta_df, mode='w')

        # Download other global data
        index_constituents = download_index_constituents(sample_dates)
        trade_days_df = download_trade_days(start_date, end_date)
        stock_status_history = download_stock_status_history(
            stock_pool, sample_dates, start_date_str, end_date_str, fetcher
        )
        
        # Download and write benchmark
        print("Saving benchmark...")
        try:
            benchmark = get_price(
                "000300.SS",
                start_date=start_date_str,
                end_date=end_date_str,
                frequency="1d",
                fields=REQUIRED_PRICE_FIELDS,
                fq="none",
            )
            if benchmark is not None:
                 # Use 'w' mode to overwrite benchmark
                writer.write_benchmark(benchmark, mode='w')
        except Exception as e:
            logger.warning(f"Benchmark download failed: {e}")

        # Save trading calendar and global metadata
        if trade_days_df is not None:
            writer.write_trade_days(trade_days_df, mode='w')

        global_meta = {
            "download_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "start_date": start_date_str,
            "end_date": end_date_str,
            "stock_count": len(stock_pool),
            "sample_count": len(sample_dates),
            "format_version": 3,
        }
        if index_constituents:
            global_meta["index_constituents"] = json.dumps(
                index_constituents, ensure_ascii=False
            )
        if stock_status_history:
            global_meta["stock_status_history"] = json.dumps(
                stock_status_history, ensure_ascii=False
            )
        meta_series = pd.Series(global_meta)
        writer.write_global_metadata(meta_series, mode='w')

    finally:
        fetcher.logout()

    # Statistics
    file_size = Path(OUTPUT_FILE).stat().st_size / (1024 * 1024) if Path(OUTPUT_FILE).exists() else 0

    print("\n" + "=" * 70)
    print("Complete")
    print("=" * 70)
    print("Output file: {}".format(OUTPUT_FILE))
    print("File size: {:.1f} MB".format(file_size))

    if stock_pool:
        missing_info_stocks = writer.get_existing_stocks(file_type="market")
        # A simple check, can be improved
        print(f"\nTotal stocks in file: {len(missing_info_stocks)}")
        
    print("\nNote: valuation data needs to be downloaded separately")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download PTrade-compatible HDF5 data")
    parser.add_argument(
        "--incremental",
        type=int,
        metavar="DAYS",
        help="Incremental update: only update last N days for existing stocks",
    )

    args = parser.parse_args()

    # Use command line arg or config
    incremental = args.incremental or INCREMENTAL_DAYS
    download_all_data(incremental_days=incremental)
