"""
查询构建器

负责构建各种类型的SQL查询，包括历史数据、快照数据、财务数据等。
"""

import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, List, Tuple, Union

from ..config import Config

logger = logging.getLogger(__name__)


class BaseQueryBuilder(ABC):
    """查询构建器基类"""

    def __init__(self, config: Config = None):
        """
        初始化查询构建器

        Args:
            config: 配置对象
        """
        self.config = config or Config()

        # 查询配置
        self.max_symbols_per_query = self.config.get("api.max_symbols_per_query", 100)
        self.max_date_range_days = self.config.get("api.max_date_range_days", 365)
        self.default_limit = self.config.get("api.default_limit", 1000)

        # 支持的频率
        self.supported_frequencies = self.config.get(
            "api.supported_frequencies", ["1d", "5m", "15m", "30m", "60m"]
        )

        # 支持的市场
        self.supported_markets = self.config.get(
            "api.supported_markets", ["SZ", "SS", "HK", "US"]
        )

        logger.debug(f"{self.__class__.__name__} initialized")

    @abstractmethod
    def build_query(self, **kwargs) -> Tuple[str, List[Any]]:
        """
        构建SQL查询

        Returns:
            Tuple[str, List[Any]]: (SQL语句, 参数列表)
        """

    def normalize_symbol(self, symbol: str) -> str:
        """
        标准化股票代码

        Args:
            symbol: 原始股票代码

        Returns:
            str: 标准化后的股票代码
        """
        if not symbol:
            raise ValueError("股票代码不能为空")

        # 移除空格并转换为大写
        symbol = symbol.strip().upper()

        # 确保有市场后缀
        if "." not in symbol:
            # 根据代码前缀推断市场
            if symbol.startswith(("00", "30")):
                symbol += ".SZ"
            elif symbol.startswith(("60", "68")):
                symbol += ".SS"
            elif len(symbol) == 5 and symbol.isdigit():
                symbol += ".HK"  # 港股
            elif symbol.isalpha():
                symbol += ".US"  # 美股

        return symbol

    def normalize_symbols(self, symbols: Union[str, List[str]]) -> List[str]:
        """
        标准化股票代码列表

        Args:
            symbols: 股票代码或代码列表

        Returns:
            List[str]: 标准化后的股票代码列表
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        if not symbols:
            raise ValueError("股票代码列表不能为空")

        if len(symbols) > self.max_symbols_per_query:
            raise ValueError(
                f"股票代码数量超过限制: {len(symbols)} > {self.max_symbols_per_query}"
            )

        normalized = []
        for symbol in symbols:
            try:
                normalized.append(self.normalize_symbol(symbol))
            except ValueError as e:
                logger.warning(f"skipping invalid stock code {symbol}: {e}")

        if not normalized:
            raise ValueError("没有有效的股票代码")

        return normalized

    def parse_date_range(
        self, start_date: Union[str, date], end_date: Union[str, date] = None
    ) -> Tuple[str, str]:
        """
        解析日期范围

        Args:
            start_date: 开始日期
            end_date: 结束日期，默认为今天

        Returns:
            Tuple[str, str]: (开始日期, 结束日期)
        """
        # 标准化开始日期
        if isinstance(start_date, str):
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        elif isinstance(start_date, date):
            start_dt = start_date
        else:
            raise ValueError(f"不支持的开始日期格式: {type(start_date)}")

        # 标准化结束日期
        if end_date is None:
            end_dt = datetime.now().date()
        elif isinstance(end_date, str):
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        elif isinstance(end_date, date):
            end_dt = end_date
        else:
            raise ValueError(f"不支持的结束日期格式: {type(end_date)}")

        # 验证日期范围
        if start_dt > end_dt:
            raise ValueError(f"开始日期不能晚于结束日期: {start_dt} > {end_dt}")

        date_range_days = (end_dt - start_dt).days
        if date_range_days > self.max_date_range_days:
            raise ValueError(
                f"日期范围超过限制: {date_range_days} > {self.max_date_range_days} 天"
            )

        return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")

    def validate_frequency(self, frequency: str) -> str:
        """
        验证频率参数

        Args:
            frequency: 频率字符串

        Returns:
            str: 验证后的频率
        """
        if frequency not in self.supported_frequencies:
            raise ValueError(
                f"不支持的频率: {frequency}，支持的频率: {self.supported_frequencies}"
            )

        return frequency

    def validate_market(self, market: str) -> str:
        """
        验证市场参数

        Args:
            market: 市场代码

        Returns:
            str: 验证后的市场代码
        """
        market = market.upper()
        if market not in self.supported_markets:
            raise ValueError(
                f"不支持的市场: {market}，支持的市场: {self.supported_markets}"
            )

        return market

    def build_symbol_filter(self, symbols: List[str]) -> Tuple[str, List[str]]:
        """
        构建股票代码过滤条件

        Args:
            symbols: 股票代码列表

        Returns:
            Tuple[str, List[str]]: (WHERE条件, 参数列表)
        """
        if len(symbols) == 1:
            return "symbol = ?", symbols
        else:
            placeholders = ",".join(["?"] * len(symbols))
            return f"symbol IN ({placeholders})", symbols

    def build_date_filter(
        self, start_date: str, end_date: str, date_column: str = "trade_date"
    ) -> Tuple[str, List[str]]:
        """
        构建日期过滤条件

        Args:
            start_date: 开始日期
            end_date: 结束日期
            date_column: 日期列名

        Returns:
            Tuple[str, List[str]]: (WHERE条件, 参数列表)
        """
        return f"{date_column} >= ? AND {date_column} <= ?", [start_date, end_date]

    def build_order_clause(
        self, order_by: List[str] = None, ascending: bool = True
    ) -> str:
        """
        构建排序子句

        Args:
            order_by: 排序字段列表
            ascending: 是否升序

        Returns:
            str: ORDER BY子句
        """
        if not order_by:
            order_by = ["symbol", "trade_date"]

        direction = "ASC" if ascending else "DESC"
        order_fields = [f"{field} {direction}" for field in order_by]

        return f"ORDER BY {', '.join(order_fields)}"

    def build_limit_clause(self, limit: int = None, offset: int = 0) -> str:
        """
        构建限制子句

        Args:
            limit: 限制数量
            offset: 偏移量

        Returns:
            str: LIMIT子句
        """
        if limit is None:
            limit = self.default_limit

        if offset > 0:
            return f"LIMIT {limit} OFFSET {offset}"
        else:
            return f"LIMIT {limit}"


class HistoryQueryBuilder(BaseQueryBuilder):
    """历史数据查询构建器"""

    def build_query(
        self,
        symbols: Union[str, List[str]],
        start_date: Union[str, date],
        end_date: Union[str, date] = None,
        frequency: str = "1d",
        fields: List[str] = None,
        limit: int = None,
        offset: int = 0,
    ) -> Tuple[str, List[Any]]:
        """
        构建历史数据查询

        Args:
            symbols: 股票代码或代码列表
            start_date: 开始日期
            end_date: 结束日期
            frequency: 频率
            fields: 查询字段列表
            limit: 限制数量
            offset: 偏移量

        Returns:
            Tuple[str, List[Any]]: (SQL语句, 参数列表)
        """
        try:
            # 参数验证和标准化
            symbols = self.normalize_symbols(symbols)
            start_date, end_date = self.parse_date_range(start_date, end_date)
            frequency = self.validate_frequency(frequency)

            # 构建字段列表
            if fields is None:
                if frequency == "1d":
                    fields = [
                        "symbol",
                        "market",
                        "trade_date",
                        "frequency",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "money",
                        "price",
                        "preclose",
                        "high_limit",
                        "low_limit",
                        "unlimited",
                        "pe_ratio",
                        "pb_ratio",
                        "turnover_rate",
                        "ma5",
                        "ma10",
                        "ma20",
                        "ma60",
                        "quality_score",
                    ]
                else:
                    fields = [
                        "symbol",
                        "market",
                        "trade_date",
                        "trade_time",
                        "frequency",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "money",
                        "price",
                        "quality_score",
                    ]

            # 构建WHERE条件
            where_conditions = []
            params = []

            # 股票代码过滤
            symbol_condition, symbol_params = self.build_symbol_filter(symbols)
            where_conditions.append(symbol_condition)
            params.extend(symbol_params)

            # 日期范围过滤
            date_condition, date_params = self.build_date_filter(start_date, end_date)
            where_conditions.append(date_condition)
            params.extend(date_params)

            # 频率过滤
            where_conditions.append("frequency = ?")
            params.append(frequency)

            # 构建完整SQL
            fields_str = ", ".join(fields)
            where_str = " AND ".join(where_conditions)
            order_str = self.build_order_clause()
            limit_str = self.build_limit_clause(limit, offset)

            sql = f"""
            SELECT {fields_str}
            FROM market_data
            WHERE {where_str}
            {order_str}
            {limit_str}
            """

            logger.debug(f"historical data query SQL: {sql}")
            logger.debug(f"query parameters : {params}")

            return sql.strip(), params

        except Exception as e:
            logger.error(f"failed to build historical data query : {e}")
            raise


class SnapshotQueryBuilder(BaseQueryBuilder):
    """快照数据查询构建器"""

    def build_query(
        self,
        symbols: Union[str, List[str]] = None,
        trade_date: Union[str, date] = None,
        market: str = None,
        fields: List[str] = None,
        limit: int = None,
        offset: int = 0,
    ) -> Tuple[str, List[Any]]:
        """
        构建快照数据查询

        Args:
            symbols: 股票代码列表，为None时查询所有
            trade_date: 交易日期，为None时查询最新
            market: 市场过滤
            fields: 查询字段列表
            limit: 限制数量
            offset: 偏移量

        Returns:
            Tuple[str, List[Any]]: (SQL语句, 参数列表)
        """
        try:
            # 构建字段列表
            if fields is None:
                fields = [
                    "symbol",
                    "market",
                    "trade_date",
                    "frequency",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "money",
                    "price",
                    "preclose",
                    "high_limit",
                    "low_limit",
                    "pe_ratio",
                    "pb_ratio",
                    "turnover_rate",
                    "quality_score",
                ]

            # 构建WHERE条件
            where_conditions = ["frequency = '1d'"]  # 快照只查日线数据
            params = []

            # 股票代码过滤
            if symbols:
                symbols = self.normalize_symbols(symbols)
                symbol_condition, symbol_params = self.build_symbol_filter(symbols)
                where_conditions.append(symbol_condition)
                params.extend(symbol_params)

            # 日期过滤
            if trade_date:
                if isinstance(trade_date, str):
                    trade_date_str = trade_date
                else:
                    trade_date_str = trade_date.strftime("%Y-%m-%d")
                where_conditions.append("trade_date = ?")
                params.append(trade_date_str)
            else:
                # 查询最新数据
                where_conditions.append(
                    """
                trade_date = (
                    SELECT MAX(trade_date) 
                    FROM market_data 
                    WHERE frequency = '1d'
                )
                """
                )

            # 市场过滤
            if market:
                market = self.validate_market(market)
                where_conditions.append("market = ?")
                params.append(market)

            # 构建完整SQL
            fields_str = ", ".join(fields)
            where_str = " AND ".join(where_conditions)
            order_str = self.build_order_clause()
            limit_str = self.build_limit_clause(limit, offset)

            sql = f"""
            SELECT {fields_str}
            FROM market_data
            WHERE {where_str}
            {order_str}
            {limit_str}
            """

            logger.debug(f"snapshot data query SQL: {sql}")
            logger.debug(f"query parameters : {params}")

            return sql.strip(), params

        except Exception as e:
            logger.error(f"failed to build snapshot data query : {e}")
            raise


class FundamentalsQueryBuilder(BaseQueryBuilder):
    """财务数据查询构建器"""

    def build_query(
        self,
        symbols: Union[str, List[str]],
        report_date: Union[str, date] = None,
        report_type: str = None,
        fields: List[str] = None,
        limit: int = None,
        offset: int = 0,
    ) -> Tuple[str, List[Any]]:
        """
        构建财务数据查询

        Args:
            symbols: 股票代码列表
            report_date: 报告期
            report_type: 报告类型 (Q1/Q2/Q3/Q4)
            fields: 查询字段列表
            limit: 限制数量
            offset: 偏移量

        Returns:
            Tuple[str, List[Any]]: (SQL语句, 参数列表)
        """
        try:
            # 参数验证和标准化
            symbols = self.normalize_symbols(symbols)

            # 构建字段列表
            if fields is None:
                fields = [
                    "symbol",
                    "report_date",
                    "report_type",
                    "revenue",
                    "net_profit",
                    "total_assets",
                    "total_equity",
                    "eps",
                    "bps",
                    "roe",
                    "roa",
                    "gross_margin",
                    "net_margin",
                    "pe_ratio",
                    "pb_ratio",
                    "ps_ratio",
                ]

            # 构建WHERE条件
            where_conditions = []
            params = []

            # 股票代码过滤
            symbol_condition, symbol_params = self.build_symbol_filter(symbols)
            where_conditions.append(symbol_condition)
            params.extend(symbol_params)

            # 报告期过滤
            if report_date:
                if isinstance(report_date, str):
                    report_date_str = report_date
                else:
                    report_date_str = report_date.strftime("%Y-%m-%d")
                where_conditions.append("report_date = ?")
                params.append(report_date_str)

            # 报告类型过滤
            if report_type:
                if report_type not in ["Q1", "Q2", "Q3", "Q4"]:
                    raise ValueError(f"不支持的报告类型: {report_type}")
                where_conditions.append("report_type = ?")
                params.append(report_type)

            # 构建完整SQL
            fields_str = ", ".join(fields)
            where_str = " AND ".join(where_conditions)
            order_str = self.build_order_clause(["symbol", "report_date"], False)
            limit_str = self.build_limit_clause(limit, offset)

            sql = f"""
            SELECT {fields_str}
            FROM ptrade_fundamentals
            WHERE {where_str}
            {order_str}
            {limit_str}
            """

            logger.debug(f"financial data query SQL: {sql}")
            logger.debug(f"query parameters : {params}")

            return sql.strip(), params

        except Exception as e:
            logger.error(f"failed to build financial data query : {e}")
            raise


class StockInfoQueryBuilder(BaseQueryBuilder):
    """股票信息查询构建器"""

    def build_query(
        self,
        symbols: Union[str, List[str]] = None,
        market: str = None,
        industry: str = None,
        status: str = "active",
        fields: List[str] = None,
        limit: int = None,
        offset: int = 0,
    ) -> Tuple[str, List[Any]]:
        """
        构建股票信息查询

        Args:
            symbols: 股票代码列表，为None时查询所有
            market: 市场过滤
            industry: 行业过滤
            status: 状态过滤
            fields: 查询字段列表
            limit: 限制数量
            offset: 偏移量

        Returns:
            Tuple[str, List[Any]]: (SQL语句, 参数列表)
        """
        try:
            # 构建字段列表
            if fields is None:
                fields = [
                    "symbol",
                    "name",
                    "market",
                    "exchange",
                    "industry",
                    "sector",
                    "list_date",
                    "delist_date",
                    "total_share",
                    "float_share",
                    "currency",
                    "timezone",
                    "trading_hours",
                    "status",
                ]

            # 构建WHERE条件
            where_conditions = []
            params = []

            # 股票代码过滤
            if symbols:
                symbols = self.normalize_symbols(symbols)
                symbol_condition, symbol_params = self.build_symbol_filter(symbols)
                where_conditions.append(symbol_condition)
                params.extend(symbol_params)

            # 市场过滤
            if market:
                market = self.validate_market(market)
                where_conditions.append("market = ?")
                params.append(market)

            # 行业过滤
            if industry:
                where_conditions.append("industry LIKE ?")
                params.append(f"%{industry}%")

            # 状态过滤
            if status:
                where_conditions.append("status = ?")
                params.append(status)

            # 构建完整SQL
            fields_str = ", ".join(fields)
            where_str = " AND ".join(where_conditions) if where_conditions else "1=1"
            order_str = self.build_order_clause(["market", "symbol"])
            limit_str = self.build_limit_clause(limit, offset)

            sql = f"""
            SELECT {fields_str}
            FROM stocks
            WHERE {where_str}
            {order_str}
            {limit_str}
            """

            logger.debug(f"stock info query SQL: {sql}")
            logger.debug(f"query parameters : {params}")

            return sql.strip(), params

        except Exception as e:
            logger.error(f"failed to build stock info query : {e}")
            raise
