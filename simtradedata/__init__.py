"""
SimTradeData - Generate PTrade-compatible HDF5 data from open-source providers

This package fetches data from BaoStock, QStock, and Yahoo Finance,
then converts it to SimTradeLab-compatible HDF5 format.
"""

__version__ = "0.1.0"

from simtradedata.converters.data_converter import DataConverter
from simtradedata.fetchers.baostock_fetcher import BaoStockFetcher
from simtradedata.writers.h5_writer import HDF5Writer

__all__ = [
    "BaoStockFetcher",
    "DataConverter",
    "HDF5Writer",
]
