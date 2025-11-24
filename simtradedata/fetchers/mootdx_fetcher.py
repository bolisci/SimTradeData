"""
Mootdx data fetcher implementation for market K-line data

Mootdx provides fast access to:
- Real-time quotes
- Historical K-line data (日K)
- Minute-level data

Note: Mootdx does NOT provide:
- Valuation metrics (PE, PB, etc.) -> use BaoStock
- Adjust factors -> use BaoStock
- Dividend data -> use BaoStock
- Fundamental data -> use BaoStock
"""

import logging
from datetime import datetime

import pandas as pd
from mootdx.quotes import Quotes

from simtradedata.fetchers.base_fetcher import BaseFetcher
from simtradedata.utils.code_utils import convert_from_ptrade_code, retry_on_failure

logger = logging.getLogger(__name__)


class MootdxFetcher(BaseFetcher):
    """
    Fetch K-line market data from Mootdx (通达信) servers

    Advantages over BaoStock:
    - Much faster (0.2s vs 4s per stock)
    - More reliable connection
    - Supports real-time data

    Limitations:
    - Only provides market K-line data (OHLCV)
    - No valuation metrics (PE, PB, PS, etc.)
    - No adjust factors
    - No dividend data
    - No fundamental data

    Therefore, this fetcher is designed to be used in combination with
    BaoStockFetcher for a hybrid data pipeline.
    """

    def __init__(self, timeout: int = 15):
        """
        Initialize Mootdx fetcher

        Args:
            timeout: Request timeout in seconds
        """
        super().__init__()  # Initialize BaseFetcher
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        """Get or create Mootdx client (lazy initialization)"""
        if self._client is None:
            self._client = Quotes.factory(
                market="std",
                timeout=self.timeout,
                quiet=True,  # Suppress mootdx logs
                multithread=True,  # Enable multithreading
            )
            logger.info("Mootdx client initialized with multithreading")
        return self._client

    def _do_login(self):
        """
        Initialize Mootdx client (no-op for API compatibility)

        Mootdx doesn't require login, but we keep this for
        compatibility with BaseFetcher interface.
        """
        self._get_client()

    def _do_logout(self):
        """Logout (no-op for Mootdx)"""
        pass

    @retry_on_failure
    def fetch_market_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        frequency: int = 9,
    ) -> pd.DataFrame:
        """
        Fetch historical K-line data (OHLCV only)

        Args:
            symbol: Stock code in PTrade format (e.g., '000001.SZ')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            frequency: K-line type (9=daily, default)
                      4 or 9 = daily
                      5 = weekly
                      6 = monthly

        Returns:
            DataFrame with columns:
            - date (index): Trading date
            - open: Opening price
            - high: Highest price
            - low: Lowest price
            - close: Closing price
            - volume: Trading volume
            - amount: Trading amount

        Note:
            Does NOT include valuation metrics (PE, PB, turnover_rate, etc.)
            Use BaoStockFetcher for those fields.
        """
        client = self._get_client()

        # Convert PTrade code to simple code (000001.SZ -> 000001)
        code = convert_from_ptrade_code(symbol, target_source="mootdx")

        # Parse date range
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # Fetch data in chunks to overcome the 800-bar limit
        all_data = []
        offset = 0
        chunk_size = 800

        while True:
            df_chunk = client.bars(
                symbol=code, frequency=frequency, start=offset, offset=chunk_size
            )

            if df_chunk is None or df_chunk.empty:
                # No more data
                break

            all_data.append(df_chunk)

            # Check if we have fetched enough data
            # Data is returned from newest to oldest
            oldest_date_in_chunk = df_chunk.index.min()
            if oldest_date_in_chunk <= start_dt:
                break

            offset += chunk_size

        if not all_data:
            logger.warning(f"No market data found for {symbol}")
            return pd.DataFrame()

        # Concatenate all chunks
        df = pd.concat(all_data)
        # Remove duplicate index entries, keeping the first occurrence
        df = df[~df.index.duplicated(keep="first")]

        # Filter by the exact date range
        df = df.loc[(df.index >= start_dt) & (df.index <= end_dt)]

        if df.empty:
            logger.warning(f"No market data found for {symbol} in the given date range")
            return pd.DataFrame()

        # Select and rename columns to match BaoStock format
        # Mootdx returns: open, close, high, low, vol, amount, volume
        # We use 'vol' as the volume (in shares), not 'volume'
        df = df[["open", "high", "low", "close", "vol", "amount"]].copy()
        df = df.rename(columns={"vol": "volume"})

        # Reset index to have 'date' column
        df = df.reset_index()
        df = df.rename(columns={"datetime": "date"})

        # Keep date as datetime column for converter to handle
        df["date"] = pd.to_datetime(df["date"])

        logger.info(f"Fetched {len(df)} market data rows for {symbol} " f"from Mootdx")

        return df

    @retry_on_failure
    def fetch_stock_list(self) -> pd.DataFrame:
        """
        Fetch list of all stocks

        Returns:
            DataFrame with columns: code, name

        Note:
            This is a simplified version. For comprehensive stock list
            with IPO dates, status, etc., use BaoStockFetcher.
        """
        client = self._get_client()

        # Get all quotes from A-share market
        # Note: This gets current trading stocks only
        df = client.quotes(symbol=[])

        if df is None or df.empty:
            logger.warning("No stock list found from Mootdx")
            return pd.DataFrame()

        # Extract code column
        df = df[["code"]].copy()
        df = df.rename(columns={"code": "code"})

        logger.info(f"Fetched {len(df)} stocks from Mootdx")

        return df
