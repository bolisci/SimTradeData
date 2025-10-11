"""
PTrade API兼容层

提供与PTrade原生API兼容的接口，确保现有代码无缝迁移。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Union

import pandas as pd

from ..api import APIRouter
from ..config import Config
from ..database import DatabaseManager

logger = logging.getLogger(__name__)


class PTradeAPIAdapter:
    """PTrade API适配器"""

    def __init__(
        self, db_manager: DatabaseManager, api_router: APIRouter, config: Config = None
    ):
        """
        初始化PTrade API适配器

        Args:
            db_manager: 数据库管理器
            api_router: API路由器
            config: 配置对象
        """
        self.db_manager = db_manager
        self.api_router = api_router
        self.config = config or Config()

        # API兼容性配置
        self.enable_legacy_format = self.config.get(
            "ptrade_api.enable_legacy_format", True
        )
        self.default_market = self.config.get("ptrade_api.default_market", "SZ")
        self.max_records = self.config.get("ptrade_api.max_records", 10000)

        logger.info("PTrade API adapter initialized")

    def get_stock_list(self, market: str = None) -> pd.DataFrame:
        """
        获取股票列表 (兼容PTrade原生API)

        Args:
            market: 市场代码 ('SZ', 'SS', 'HK', 'US')

        Returns:
            pd.DataFrame: 股票列表
        """
        try:
            # 调用API路由器获取股票信息
            result = self.api_router.get_stock_info(
                market=market, format_type="dataframe"
            )

            if isinstance(result, pd.DataFrame):
                # 确保兼容PTrade格式
                return self._format_stock_list(result)
            else:
                logger.warning("API router returned non-DataFrame format")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"retrieving stock list failed : {e}")
            return pd.DataFrame()

    def get_price(
        self,
        symbol: Union[str, List[str]],
        start_date: str = None,
        end_date: str = None,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """
        获取股票价格数据 (兼容PTrade原生API)

        Args:
            symbol: 股票代码或代码列表
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            frequency: 数据频率 ('1d', '1m', '5m', '15m', '30m', '60m')

        Returns:
            pd.DataFrame: 价格数据
        """
        try:
            # 标准化参数
            if isinstance(symbol, str):
                symbols = [symbol]
            else:
                symbols = symbol

            if end_date is None:
                end_date = datetime.now().strftime("%Y-%m-%d")

            if start_date is None:
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

            # 调用API路由器获取历史数据
            result = self.api_router.get_history(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                format_type="dataframe",
            )

            if isinstance(result, pd.DataFrame):
                # 确保兼容PTrade格式
                return self._format_price_data(result)
            else:
                logger.warning("API router returned non-DataFrame format")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"retrieving price data failed : {e}")
            return pd.DataFrame()

    def get_fundamentals(
        self, symbol: Union[str, List[str]], fields: List[str] = None
    ) -> pd.DataFrame:
        """
        获取基本面数据 (兼容PTrade原生API)

        Args:
            symbol: 股票代码或代码列表
            fields: 字段列表

        Returns:
            pd.DataFrame: 基本面数据
        """
        try:
            # 标准化参数
            if isinstance(symbol, str):
                symbols = [symbol]
            else:
                symbols = symbol

            if fields is None:
                fields = ["pe", "pb", "ps", "market_cap", "total_share", "float_share"]

            # 调用API路由器获取财务数据
            result = self.api_router.get_fundamentals(
                symbols=symbols, fields=fields, format_type="dataframe"
            )

            if isinstance(result, pd.DataFrame):
                return self._format_fundamentals(result)
            else:
                logger.warning("API router returned non-DataFrame format")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"failed to retrieve fundamental data : {e}")
            return pd.DataFrame()

    def get_industry(
        self, symbol: Union[str, List[str]], standard: str = "sw"
    ) -> pd.DataFrame:
        """
        获取行业分类数据 (兼容PTrade原生API)

        Args:
            symbol: 股票代码或代码列表
            standard: 分类标准 ('sw', 'citic', 'zjh', 'gics')

        Returns:
            pd.DataFrame: 行业分类数据
        """
        try:
            # 标准化参数
            if isinstance(symbol, str):
                symbols = [symbol]
            else:
                symbols = symbol

            # 构建查询参数
            query_params = {
                "data_type": "industry_classification",
                "symbols": symbols,
                "standard": standard,
                "format": "dataframe",
            }

            # 调用API路由器
            result = self.api_router.query(query_params)

            if isinstance(result, pd.DataFrame):
                return self._format_industry_data(result)
            else:
                logger.warning("API router returned non-DataFrame format")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"failed to retrieve industry classification : {e}")
            return pd.DataFrame()

    def get_etf_holdings(self, etf_symbol: str, date: str = None) -> pd.DataFrame:
        """
        获取ETF成分股 (扩展PTrade API)

        Args:
            etf_symbol: ETF代码
            date: 持仓日期

        Returns:
            pd.DataFrame: ETF成分股数据
        """
        try:
            # 构建查询参数
            query_params = {
                "data_type": "etf_holdings",
                "etf_symbol": etf_symbol,
                "format": "dataframe",
            }

            if date:
                query_params["date"] = date

            # 调用API路由器
            result = self.api_router.query(query_params)

            if isinstance(result, pd.DataFrame):
                return self._format_etf_holdings(result)
            else:
                logger.warning("API router returned non-DataFrame format")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"failed to retrieve ETF constituent stocks : {e}")
            return pd.DataFrame()

    def get_technical_indicators(
        self,
        symbol: str,
        indicators: List[str],
        start_date: str = None,
        end_date: str = None,
    ) -> pd.DataFrame:
        """
        获取技术指标 (扩展PTrade API)

        Args:
            symbol: 股票代码
            indicators: 指标列表 ['ma', 'rsi', 'macd', 'bollinger', 'kdj']
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            pd.DataFrame: 技术指标数据
        """
        try:
            if end_date is None:
                end_date = datetime.now().strftime("%Y-%m-%d")

            if start_date is None:
                start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

            # 构建查询参数
            query_params = {
                "data_type": "technical_indicators",
                "symbol": symbol,
                "indicators": indicators,
                "start_date": start_date,
                "end_date": end_date,
                "format": "dataframe",
            }

            # 调用API路由器
            result = self.api_router.query(query_params)

            if isinstance(result, pd.DataFrame):
                return self._format_technical_indicators(result)
            else:
                logger.warning("API router returned non-DataFrame format")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"failed to retrieve technical indicators : {e}")
            return pd.DataFrame()

    def _format_stock_list(self, df: pd.DataFrame) -> pd.DataFrame:
        """格式化股票列表为PTrade兼容格式"""
        if df.empty:
            return df

        # PTrade标准字段映射
        column_mapping = {
            "symbol": "code",
            "stock_name": "name",
            "market": "market",
            "exchange": "exchange",
            "list_date": "list_date",
            "status": "status",
        }

        # 重命名列
        formatted_df = df.copy()
        for old_col, new_col in column_mapping.items():
            if old_col in formatted_df.columns:
                formatted_df = formatted_df.rename(columns={old_col: new_col})

        # 确保必需字段存在
        required_fields = ["code", "name", "market"]
        for field in required_fields:
            if field not in formatted_df.columns:
                formatted_df[field] = ""

        return formatted_df

    def _format_price_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """格式化价格数据为PTrade兼容格式"""
        if df.empty:
            return df

        # 重置索引，将symbol和trade_date变为列
        formatted_df = df.reset_index()

        # PTrade标准字段映射
        column_mapping = {
            "symbol": "code",
            "trade_date": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "money": "amount",
        }

        # 重命名列
        for old_col, new_col in column_mapping.items():
            if old_col in formatted_df.columns:
                formatted_df = formatted_df.rename(columns={old_col: new_col})

        # 设置索引
        if "date" in formatted_df.columns:
            formatted_df["date"] = pd.to_datetime(formatted_df["date"])
            if "code" in formatted_df.columns:
                formatted_df = formatted_df.set_index(["code", "date"])
            else:
                formatted_df = formatted_df.set_index("date")

        return formatted_df

    def _format_fundamentals(self, df: pd.DataFrame) -> pd.DataFrame:
        """格式化基本面数据为PTrade兼容格式"""
        if df.empty:
            return df

        # PTrade标准字段映射
        column_mapping = {
            "symbol": "code",
            "pe": "pe_ratio",
            "pb": "pb_ratio",
            "ps": "ps_ratio",
            "market_cap": "market_cap",
            "total_share": "total_shares",
            "float_share": "float_shares",
        }

        # 重命名列
        formatted_df = df.copy()
        for old_col, new_col in column_mapping.items():
            if old_col in formatted_df.columns:
                formatted_df = formatted_df.rename(columns={old_col: new_col})

        return formatted_df

    def _format_industry_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """格式化行业数据为PTrade兼容格式"""
        if df.empty:
            return df

        # PTrade标准字段映射
        column_mapping = {
            "symbol": "code",
            "level1_name": "industry_l1",
            "level2_name": "industry_l2",
            "level3_name": "industry_l3",
            "standard": "classification",
        }

        # 重命名列
        formatted_df = df.copy()
        for old_col, new_col in column_mapping.items():
            if old_col in formatted_df.columns:
                formatted_df = formatted_df.rename(columns={old_col: new_col})

        return formatted_df

    def _format_etf_holdings(self, df: pd.DataFrame) -> pd.DataFrame:
        """格式化ETF成分股为PTrade兼容格式"""
        if df.empty:
            return df

        # PTrade标准字段映射
        column_mapping = {
            "stock_symbol": "code",
            "stock_name": "name",
            "weight": "weight",
            "shares": "shares",
            "market_value": "market_value",
        }

        # 重命名列
        formatted_df = df.copy()
        for old_col, new_col in column_mapping.items():
            if old_col in formatted_df.columns:
                formatted_df = formatted_df.rename(columns={old_col: new_col})

        return formatted_df

    def _format_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """格式化技术指标为PTrade兼容格式"""
        if df.empty:
            return df

        # 技术指标通常保持原格式，只需要确保日期索引
        formatted_df = df.copy()

        if "trade_date" in formatted_df.columns:
            formatted_df["trade_date"] = pd.to_datetime(formatted_df["trade_date"])
            formatted_df = formatted_df.set_index("trade_date")

        return formatted_df

    def get_adapter_info(self) -> Dict[str, Any]:
        """获取适配器信息"""
        return {
            "adapter_name": "PTrade API Adapter",
            "version": "1.0.0",
            "compatible_apis": [
                "get_stock_list",
                "get_price",
                "get_fundamentals",
                "get_industry",
                "get_etf_holdings",
                "get_technical_indicators",
            ],
            "enable_legacy_format": self.enable_legacy_format,
            "default_market": self.default_market,
            "max_records": self.max_records,
            "supported_markets": ["SZ", "SS", "HK", "US"],
            "supported_frequencies": ["1m", "5m", "15m", "30m", "60m", "1d"],
        }
