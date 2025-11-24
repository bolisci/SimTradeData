"""
Configuration module for SimTradeData

This package contains centralized configuration definitions including
field mappings, routing configurations, and constants.
"""

from .field_mappings import (
    DATA_ROUTING,
    FUNDAMENTAL_FIELD_MAP,
    MARKET_FIELD_MAP,
    VALUATION_FIELD_MAP,
)

__all__ = [
    "MARKET_FIELD_MAP",
    "VALUATION_FIELD_MAP",
    "FUNDAMENTAL_FIELD_MAP",
    "DATA_ROUTING",
]
