"""
AkShare数据源适配器

提供AkShare数据源的统一接口实现。
"""

import logging
import os
from datetime import date
from typing import Any, Dict, List, Union

# 禁用AkShare的进度条
os.environ["TQDM_DISABLE"] = "1"


from .base import BaseDataSource, DataSourceDataError

logger = logging.getLogger(__name__)


class AkShareAdapter(BaseDataSource):
    """AkShare数据源适配器"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化AkShare适配器

        Args:
            config: 配置参数
        """
        super().__init__("akshare", config)
        self._akshare = None

        # AkShare特定配置
        self.tool = self.config.get("tool", "pandas")  # pandas/numpy
        self.timeout = self.config.get("timeout", 10)

    def connect(self) -> bool:
        """连接AkShare"""
        import akshare as ak

        self._akshare = ak
        self._connected = True
        return True

    def disconnect(self):
        """断开AkShare连接"""
        self._akshare = None
        self._connected = False
        logger.info("AkShare连接已断开")

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected and self._akshare is not None

    def get_daily_data(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Union[str, date] = None,
    ) -> Dict[str, Any]:
        """
        获取日线数据

        Args:
            symbol: 股票代码 (如: 000001.SZ)
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Dict[str, Any]: 日线数据
        """
        if not self.is_connected():
            self.connect()

        symbol = self._normalize_symbol(symbol)
        start_date = self._normalize_date(start_date)
        end_date = self._normalize_date(end_date) if end_date else start_date

        def _fetch_data():
            # 转换为AkShare格式
            ak_symbol = self._convert_to_akshare_symbol(symbol)

            # 获取日线数据
            df = self._akshare.stock_zh_a_hist(
                symbol=ak_symbol,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq",  # 前复权
            )

            return df

        return self._retry_request(_fetch_data)

    def get_minute_data(
        self, symbol: str, trade_date: Union[str, date], frequency: str = "5m"
    ) -> Dict[str, Any]:
        """
        获取分钟线数据

        Args:
            symbol: 股票代码
            trade_date: 交易日期
            frequency: 频率 (1m/5m/15m/30m/60m)

        Returns:
            Dict[str, Any]: 分钟线数据
        """
        if not self.is_connected():
            self.connect()

        symbol = self._normalize_symbol(symbol)
        trade_date = self._normalize_date(trade_date)
        frequency = self._validate_frequency(frequency)

        def _fetch_data():
            try:
                # 转换为AkShare格式
                ak_symbol = self._convert_to_akshare_symbol(symbol)

                # 转换频率
                period_map = {
                    "1m": "1",
                    "5m": "5",
                    "15m": "15",
                    "30m": "30",
                    "60m": "60",
                }

                if frequency not in period_map:
                    raise DataSourceDataError(f"AkShare不支持频率: {frequency}")

                period = period_map[frequency]

                # 获取分钟线数据
                df = self._akshare.stock_zh_a_hist_min_em(
                    symbol=ak_symbol,
                    period=period,
                    start_date=trade_date + " 09:00:00",
                    end_date=trade_date + " 15:30:00",
                    adjust="qfq",
                )

                if df.empty:
                    raise DataSourceDataError(
                        f"未获取到分钟线数据: {symbol} {trade_date}"
                    )

                # 转换为标准格式
                return self._convert_minute_data(df, symbol, trade_date, frequency)

            except Exception as e:
                logger.error(f"AkShare获取分钟线数据失败 {symbol} {trade_date}: {e}")
                raise DataSourceDataError(f"获取分钟线数据失败: {e}")

        return self._retry_request(_fetch_data)

    def get_stock_info(
        self, symbol: str = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        获取股票基础信息

        Args:
            symbol: 股票代码，为None时返回所有股票

        Returns:
            Union[Dict, List[Dict]]: 股票信息
        """
        if not self.is_connected():
            self.connect()

        def _fetch_data():
            if symbol:
                # 获取单个股票信息
                symbol_norm = self._normalize_symbol(symbol)
                ak_symbol = self._convert_to_akshare_symbol(symbol_norm)

                # 获取股票基本信息
                df = self._akshare.stock_individual_info_em(symbol=ak_symbol)
                return df
            else:
                # 获取所有股票列表
                df = self._akshare.stock_info_a_code_name()
                return df

        return self._retry_request(_fetch_data)

    def get_fundamentals(
        self, symbol: str, report_date: Union[str, date], report_type: str = "Q4"
    ) -> Dict[str, Any]:
        """
        获取财务数据

        Args:
            symbol: 股票代码
            report_date: 报告期
            report_type: 报告类型

        Returns:
            Dict[str, Any]: 财务数据
        """
        if not self.is_connected():
            self.connect()

        symbol = self._normalize_symbol(symbol)
        report_date = self._normalize_date(report_date)

        def _fetch_data():
            ak_symbol = self._convert_to_akshare_symbol(symbol)

            # 获取财务数据
            df = self._akshare.stock_financial_abstract_ths(symbol=ak_symbol)

            return df

        return self._retry_request(_fetch_data)

    def get_valuation_data(
        self, symbol: str, trade_date: Union[str, date]
    ) -> Dict[str, Any]:
        """获取估值数据"""
        if not self.is_connected():
            self.connect()

        symbol = self._normalize_symbol(symbol)
        trade_date = self._normalize_date(trade_date)

        def _fetch_data():
            try:
                ak_symbol = self._convert_to_akshare_symbol(symbol)

                # 获取实时数据 (包含估值指标)
                df = self._akshare.stock_zh_a_spot_em()
                stock_data = df[df["代码"] == ak_symbol]

                if stock_data.empty:
                    raise DataSourceDataError(f"未获取到估值数据: {symbol}")

                return self._convert_valuation_data(
                    stock_data.iloc[0], symbol, trade_date
                )

            except Exception as e:
                logger.error(f"AkShare获取估值数据失败 {symbol}: {e}")
                raise DataSourceDataError(f"获取估值数据失败: {e}")

        return self._retry_request(_fetch_data)

    def _convert_to_akshare_symbol(self, symbol: str) -> str:
        """转换为AkShare股票代码格式"""
        # 移除市场后缀
        if "." in symbol:
            return symbol.split(".")[0]
        return symbol
