"""
数据源基础抽象类

定义所有数据源适配器的统一接口。
"""

import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


class DataSourceError(Exception):
    """数据源错误基类"""


class DataSourceConnectionError(DataSourceError):
    """数据源连接错误"""


class DataSourceDataError(DataSourceError):
    """数据源数据错误"""


class BaseDataSource(ABC):
    """数据源基础抽象类"""

    def __init__(self, name: str, config: Dict[str, Any] = None):
        """
        初始化数据源

        Args:
            name: 数据源名称
            config: 配置参数
        """
        self.name = name
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.timeout = self.config.get("timeout", 10)
        self.retry_times = self.config.get("retry_times", 3)
        self.retry_delay = self.config.get("retry_delay", 1)
        self.rate_limit = self.config.get("rate_limit", 100)

        self._connected = False
        self._last_request_time = None
        self._request_count = 0

        logger.info(f"数据源 {self.name} 初始化完成")

    @abstractmethod
    def connect(self) -> bool:
        """
        连接数据源

        Returns:
            bool: 连接是否成功
        """

    @abstractmethod
    def disconnect(self):
        """断开数据源连接"""

    @abstractmethod
    def is_connected(self) -> bool:
        """
        检查连接状态

        Returns:
            bool: 是否已连接
        """

    @abstractmethod
    def get_daily_data(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Union[str, date] = None,
    ) -> Dict[str, Any]:
        """
        获取日线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Dict[str, Any]: 日线数据
        """

    @abstractmethod
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

    @abstractmethod
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

    @abstractmethod
    def get_fundamentals(
        self, symbol: str, report_date: Union[str, date], report_type: str = "Q4"
    ) -> Dict[str, Any]:
        """
        获取财务数据

        Args:
            symbol: 股票代码
            report_date: 报告期
            report_type: 报告类型 (Q1/Q2/Q3/Q4)

        Returns:
            Dict[str, Any]: 财务数据
        """

    def get_trade_calendar(
        self, start_date: Union[str, date], end_date: Union[str, date] = None
    ) -> List[Dict[str, Any]]:
        """
        获取交易日历 (可选实现)

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            List[Dict]: 交易日历数据
        """
        raise NotImplementedError(f"数据源 {self.name} 不支持交易日历查询")

    def get_adjustment_data(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Union[str, date] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取除权除息数据 (可选实现)

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            List[Dict]: 除权除息数据
        """
        raise NotImplementedError(f"数据源 {self.name} 不支持除权除息数据查询")

    def get_valuation_data(
        self, symbol: str, trade_date: Union[str, date]
    ) -> Dict[str, Any]:
        """
        获取估值数据 (可选实现)

        Args:
            symbol: 股票代码
            trade_date: 交易日期

        Returns:
            Dict: 估值数据
        """
        raise NotImplementedError(f"数据源 {self.name} 不支持估值数据查询")

    def _check_rate_limit(self):
        """检查请求频率限制"""
        import time

        current_time = time.time()

        # 重置计数器 (每分钟)
        if (
            self._last_request_time is None
            or current_time - self._last_request_time > 60
        ):
            self._request_count = 0
            self._last_request_time = current_time

        # 检查频率限制
        if self._request_count >= self.rate_limit:
            sleep_time = 60 - (current_time - self._last_request_time)
            if sleep_time > 0:
                logger.warning(
                    f"数据源 {self.name} 达到频率限制，等待 {sleep_time:.1f} 秒"
                )
                time.sleep(sleep_time)
                self._request_count = 0
                self._last_request_time = time.time()

        self._request_count += 1

    def _retry_request(self, func, *args, **kwargs):
        """重试请求"""
        import time

        last_error = None

        for attempt in range(self.retry_times):
            try:
                self._check_rate_limit()
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.retry_times - 1:
                    wait_time = self.retry_delay * (2**attempt)  # 指数退避
                    logger.warning(
                        f"数据源 {self.name} 请求失败 (尝试 {attempt + 1}/{self.retry_times}): {e}"
                    )
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"数据源 {self.name} 请求最终失败: {e}")

        raise last_error

    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码"""
        if not symbol:
            raise ValueError("股票代码不能为空")

        # 移除空格
        symbol = symbol.strip().upper()

        # 确保有市场后缀
        if "." not in symbol:
            # 根据代码前缀推断市场
            if symbol.startswith(("00", "30")):
                symbol += ".SZ"
            elif symbol.startswith(("60", "68")):
                symbol += ".SS"

        return symbol

    def _normalize_date(self, date_input: Union[str, date, datetime]) -> str:
        """标准化日期格式"""
        if isinstance(date_input, str):
            return date_input
        elif isinstance(date_input, (date, datetime)):
            return date_input.strftime("%Y-%m-%d")
        else:
            raise ValueError(f"不支持的日期格式: {type(date_input)}")

    def _validate_frequency(self, frequency: str) -> str:
        """验证频率参数"""
        valid_frequencies = ["1m", "5m", "15m", "30m", "60m", "120m", "1d", "1w", "1y"]
        if frequency not in valid_frequencies:
            raise ValueError(
                f"不支持的频率: {frequency}，支持的频率: {valid_frequencies}"
            )
        return frequency

    def get_capabilities(self) -> Dict[str, Any]:
        """
        获取数据源能力信息

        Returns:
            Dict: 能力信息
        """
        return {
            "name": self.name,
            "enabled": self.enabled,
            "supports_daily": True,
            "supports_minute": True,
            "supports_fundamentals": True,
            "supports_stock_info": True,
            "supports_trade_calendar": False,
            "supports_adjustment": False,
            "supports_valuation": False,
            "supported_frequencies": ["1d", "5m", "15m", "30m", "60m"],
            "supported_markets": ["SZ", "SS"],
            "rate_limit": self.rate_limit,
            "timeout": self.timeout,
        }

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()

    def __str__(self):
        return f"DataSource({self.name}, enabled={self.enabled})"

    def __repr__(self):
        return self.__str__()
