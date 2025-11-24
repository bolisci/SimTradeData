"""
Market capitalization calculator

Calculate total_value and float_value from share data and price
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_market_cap(
    valuation_df: pd.DataFrame,
    fundamental_df: pd.DataFrame,
    symbol: str
) -> pd.DataFrame:
    """
    Calculate market cap fields for valuation data

    Adds three fields to valuation data:
    - total_shares: Total outstanding shares (forward-filled from quarterly data)
    - total_value: Total market cap = close * total_shares
    - float_value: Float market cap = close * float_shares

    Args:
        valuation_df: Daily valuation data with 'close' price
                     Index must be DatetimeIndex
        fundamental_df: Quarterly fundamental data containing:
                       - totalShare: Total shares (in units, e.g., 100 million shares)
                       - liqaShare: Float shares (in units)
                       Index must be DatetimeIndex (end_date of quarter)
        symbol: Stock code for logging

    Returns:
        valuation_df with added fields: total_shares, total_value, float_value

    Notes:
        - BaoStock totalShare/liqaShare units are in "亿股" (100 million shares)
        - Share data is quarterly, forward-filled to daily frequency
        - If no share data available, fields are set to NaN
    """
    if valuation_df.empty:
        return valuation_df

    # Ensure valuation has close price (from split market data)
    if 'close' not in valuation_df.columns:
        logger.warning(
            f"{symbol}: Cannot calculate market cap without 'close' price. "
            f"Available columns: {list(valuation_df.columns)}"
        )
        valuation_df['total_shares'] = np.nan
        valuation_df['total_value'] = np.nan
        valuation_df['float_value'] = np.nan
        return valuation_df

    # Check if fundamental data has share information
    if fundamental_df.empty or 'totalShare' not in fundamental_df.columns:
        logger.warning(
            f"{symbol}: No fundamental data or totalShare field. "
            f"Market cap fields will be NaN."
        )
        valuation_df['total_shares'] = np.nan
        valuation_df['total_value'] = np.nan
        valuation_df['float_value'] = np.nan
        return valuation_df

    try:
        # Extract share data from fundamentals
        share_data = fundamental_df[['totalShare']].copy()
        if 'liqaShare' in fundamental_df.columns:
            share_data['liqaShare'] = fundamental_df['liqaShare']
        else:
            logger.warning(f"{symbol}: No liqaShare field, using totalShare for float")
            share_data['liqaShare'] = fundamental_df['totalShare']

        # Convert to numeric (handle potential string values)
        share_data['totalShare'] = pd.to_numeric(share_data['totalShare'], errors='coerce')
        share_data['liqaShare'] = pd.to_numeric(share_data['liqaShare'], errors='coerce')

        # Remove rows with NaN shares
        share_data = share_data.dropna()

        if share_data.empty:
            logger.warning(f"{symbol}: All share data is NaN after conversion")
            valuation_df['total_shares'] = np.nan
            valuation_df['total_value'] = np.nan
            valuation_df['float_value'] = np.nan
            return valuation_df

        # Merge quarterly share data with daily valuation (forward fill)
        # Create a combined dataframe with both datasets
        combined = pd.DataFrame(index=valuation_df.index)
        combined['close'] = valuation_df['close']

        # Reindex share data to daily frequency and forward fill
        share_daily = share_data.reindex(
            combined.index.union(share_data.index)
        ).sort_index()
        share_daily = share_daily.ffill()  # Forward fill quarterly data to daily

        # Align with valuation dates
        share_daily = share_daily.reindex(combined.index)

        # Calculate market cap
        # Note: BaoStock shares are in units of 100 million (亿股)
        # total_value should be in same units as close price
        # If close is in yuan, and shares are in 100M, then:
        # market_cap = close * shares * 100000000
        valuation_df['total_shares'] = share_daily['totalShare']
        valuation_df['total_value'] = (
            valuation_df['close'] * share_daily['totalShare'] * 1e8
        )
        valuation_df['float_value'] = (
            valuation_df['close'] * share_daily['liqaShare'] * 1e8
        )

        # Check for NaN values
        nan_count = valuation_df['total_shares'].isna().sum()
        if nan_count > 0:
            logger.warning(
                f"{symbol}: {nan_count}/{len(valuation_df)} days have NaN market cap "
                f"(no share data available for those dates)"
            )

        logger.info(
            f"{symbol}: Calculated market cap for {len(valuation_df)} days, "
            f"{nan_count} NaN values"
        )

    except Exception as e:
        logger.error(f"{symbol}: Failed to calculate market cap: {e}")
        valuation_df['total_shares'] = np.nan
        valuation_df['total_value'] = np.nan
        valuation_df['float_value'] = np.nan

    return valuation_df
