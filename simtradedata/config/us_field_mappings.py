# -*- coding: utf-8 -*-
"""
US stock (yfinance) field mapping configurations

Maps yfinance data fields to PTrade internal format.
"""

# yfinance OHLCV -> PTrade stocks table
# yfinance uses capitalized column names: Open, High, Low, Close, Volume
YFINANCE_MARKET_FIELD_MAP = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}

# NASDAQ trader file URL for stock list
NASDAQ_TRADED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqtraded.txt"
