"""
时区处理器

提供多时区的时间转换和交易时间管理功能。
"""

import logging
from datetime import datetime, time
from typing import Any, Dict, List, Optional, Union

import pytz

from ..config import Config

logger = logging.getLogger(__name__)


class TimezoneHandler:
    """时区处理器"""

    def __init__(self, config: Config = None):
        """
        初始化时区处理器

        Args:
            config: 配置对象
        """
        self.config = config or Config()

        # 默认时区
        self.default_timezone = self.config.get("timezone.default", "Asia/Shanghai")

        # 市场时区映射
        self.market_timezones = {
            "SZ": "Asia/Shanghai",  # 深圳
            "SS": "Asia/Shanghai",  # 上海
            "HK": "Asia/Hong_Kong",  # 香港
            "US": "America/New_York",  # 美国
            "EU": "Europe/London",  # 欧洲
            "JP": "Asia/Tokyo",  # 日本
        }

        # 常用时区
        self.common_timezones = {
            "UTC": pytz.UTC,
            "Asia/Shanghai": pytz.timezone("Asia/Shanghai"),
            "Asia/Hong_Kong": pytz.timezone("Asia/Hong_Kong"),
            "America/New_York": pytz.timezone("America/New_York"),
            "Europe/London": pytz.timezone("Europe/London"),
            "Asia/Tokyo": pytz.timezone("Asia/Tokyo"),
        }

        logger.info("时区处理器初始化完成")

    def convert_timezone(
        self,
        dt: datetime,
        from_tz: Union[str, pytz.BaseTzInfo],
        to_tz: Union[str, pytz.BaseTzInfo],
    ) -> datetime:
        """
        时区转换

        Args:
            dt: 日期时间对象
            from_tz: 源时区
            to_tz: 目标时区

        Returns:
            datetime: 转换后的日期时间
        """
        try:
            # 获取时区对象
            if isinstance(from_tz, str):
                from_tz = pytz.timezone(from_tz)
            if isinstance(to_tz, str):
                to_tz = pytz.timezone(to_tz)

            # 如果datetime没有时区信息，假设它是源时区的本地时间
            if dt.tzinfo is None:
                dt = from_tz.localize(dt)
            elif dt.tzinfo != from_tz:
                # 如果已有时区信息但不是源时区，先转换到源时区
                dt = dt.astimezone(from_tz)

            # 转换到目标时区
            converted_dt = dt.astimezone(to_tz)

            logger.debug(f"时区转换: {dt} ({from_tz}) -> {converted_dt} ({to_tz})")
            return converted_dt

        except Exception as e:
            logger.error(f"时区转换失败: {e}")
            return dt

    def get_market_timezone(self, market: str) -> pytz.BaseTzInfo:
        """
        获取市场时区

        Args:
            market: 市场代码

        Returns:
            pytz.BaseTzInfo: 时区对象
        """
        timezone_name = self.market_timezones.get(market.upper(), self.default_timezone)
        return pytz.timezone(timezone_name)

    def get_market_time(self, market: str, dt: datetime = None) -> datetime:
        """
        获取市场当前时间

        Args:
            market: 市场代码
            dt: 指定时间，默认为当前时间

        Returns:
            datetime: 市场时间
        """
        if dt is None:
            dt = datetime.now(pytz.UTC)
        elif dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)

        market_tz = self.get_market_timezone(market)
        return dt.astimezone(market_tz)

    def is_market_open(self, market: str, dt: datetime = None) -> bool:
        """
        判断市场是否开盘

        Args:
            market: 市场代码
            dt: 指定时间，默认为当前时间

        Returns:
            bool: 是否开盘
        """
        # 不再提供简化的市场开盘判断，应该使用专门的交易日历服务
        raise NotImplementedError("请使用专门的交易日历服务来判断市场是否开盘")

    def get_next_trading_time(
        self, market: str, dt: datetime = None
    ) -> Optional[datetime]:
        """
        获取下一个交易时间

        Args:
            market: 市场代码
            dt: 指定时间，默认为当前时间

        Returns:
            Optional[datetime]: 下一个交易时间
        """
        # 不再提供简化的下一个交易时间计算，应该使用专门的交易日历服务
        raise NotImplementedError("请使用专门的交易日历服务来获取下一个交易时间")

    def format_market_time(
        self, market: str, dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S %Z"
    ) -> str:
        """
        格式化市场时间

        Args:
            market: 市场代码
            dt: 日期时间
            format_str: 格式字符串

        Returns:
            str: 格式化后的时间字符串
        """
        try:
            market_time = self.get_market_time(market, dt)
            return market_time.strftime(format_str)
        except Exception as e:
            logger.error(f"格式化市场时间失败: {e}")
            return str(dt)

    def convert_trading_time(
        self, trade_time_str: str, from_market: str, to_market: str
    ) -> str:
        """
        转换交易时间到不同市场

        Args:
            trade_time_str: 交易时间字符串
            from_market: 源市场
            to_market: 目标市场

        Returns:
            str: 转换后的时间字符串
        """
        try:
            # 解析时间字符串
            dt = datetime.strptime(trade_time_str, "%Y-%m-%d %H:%M:%S")

            # 获取时区
            from_tz = self.get_market_timezone(from_market)
            to_tz = self.get_market_timezone(to_market)

            # 转换时区
            converted_dt = self.convert_timezone(dt, from_tz, to_tz)

            return converted_dt.strftime("%Y-%m-%d %H:%M:%S")

        except Exception as e:
            logger.error(f"转换交易时间失败: {e}")
            return trade_time_str

    def _get_trading_sessions(self, market: str) -> List[Dict[str, time]]:
        """获取交易时段"""
        trading_sessions = {
            "SZ": [
                {"start": time(9, 30), "end": time(11, 30)},
                {"start": time(13, 0), "end": time(15, 0)},
            ],
            "SS": [
                {"start": time(9, 30), "end": time(11, 30)},
                {"start": time(13, 0), "end": time(15, 0)},
            ],
            "HK": [
                {"start": time(9, 30), "end": time(12, 0)},
                {"start": time(13, 0), "end": time(16, 0)},
            ],
            "US": [
                {"start": time(9, 30), "end": time(16, 0)},
            ],
        }

        return trading_sessions.get(market.upper(), [])

    def get_timezone_info(self, timezone_name: str) -> Dict[str, Any]:
        """
        获取时区信息

        Args:
            timezone_name: 时区名称

        Returns:
            Dict[str, Any]: 时区信息
        """
        try:
            tz = pytz.timezone(timezone_name)
            now = datetime.now(tz)

            return {
                "timezone": timezone_name,
                "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "utc_offset": now.strftime("%z"),
                "dst_active": bool(now.dst()),
                "timezone_name": now.tzname(),
            }

        except Exception as e:
            logger.error(f"获取时区信息失败: {e}")
            return {}

    def get_all_market_times(self, dt: datetime = None) -> Dict[str, str]:
        """
        获取所有市场的当前时间

        Args:
            dt: 指定时间，默认为当前时间

        Returns:
            Dict[str, str]: 各市场时间
        """
        if dt is None:
            dt = datetime.now(pytz.UTC)

        market_times = {}

        for market in self.market_timezones.keys():
            try:
                market_time = self.get_market_time(market, dt)
                market_times[market] = market_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            except Exception as e:
                logger.error(f"获取市场时间失败 {market}: {e}")
                market_times[market] = "Error"

        return market_times

    def get_supported_timezones(self) -> List[str]:
        """获取支持的时区列表"""
        return list(self.common_timezones.keys())

    def get_handler_stats(self) -> Dict[str, Any]:
        """获取处理器统计信息"""
        return {
            "default_timezone": self.default_timezone,
            "market_timezones": self.market_timezones.copy(),
            "supported_timezones": self.get_supported_timezones(),
            "current_utc_time": datetime.now(pytz.UTC).isoformat(),
            "market_times": self.get_all_market_times(),
        }
