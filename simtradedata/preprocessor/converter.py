"""
PTrade格式转换器

负责将清洗后的数据转换为PTrade标准格式。
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List

from ..config import Config

logger = logging.getLogger(__name__)


class PTradeConverter:
    """PTrade格式转换器"""

    def __init__(self, config: Config = None):
        """
        初始化PTrade转换器

        Args:
            config: 配置对象
        """
        self.config = config or Config()

        # 转换配置
        self.default_currency = self.config.get("conversion.default_currency", "CNY")
        self.default_timezone = self.config.get(
            "conversion.default_timezone", "Asia/Shanghai"
        )
        self.enable_valuation = self.config.get("conversion.enable_valuation", True)

        # 市场配置
        self.market_configs = self.config.get("markets", {})

        logger.info("PTrade format converting er initialized")

    def convert_to_ptrade(
        self,
        cleaned_data: Dict[str, Any],
        symbol: str,
        target_date: date,
        frequency: str,
        market: str,
    ) -> Dict[str, Any]:
        """
        转换为PTrade标准格式

        Args:
            cleaned_data: 清洗后的数据
            symbol: 股票代码
            target_date: 目标日期
            frequency: 频率
            market: 市场

        Returns:
            Dict[str, Any]: PTrade格式数据
        """
        if not cleaned_data:
            return {}

        try:
            logger.debug(
                f"starting PTrade format converting : {symbol} {target_date} {frequency}"
            )

            if frequency == "1d":
                # 日线数据转换
                ptrade_data = self._convert_daily_data(
                    cleaned_data, symbol, target_date, market
                )
            else:
                # 分钟线数据转换
                ptrade_data = self._convert_minute_data(
                    cleaned_data, symbol, target_date, frequency, market
                )

            # 添加通用字段
            ptrade_data.update(
                {
                    "symbol": symbol,
                    "market": market,
                    "frequency": frequency,
                    "date": str(target_date),
                    "currency": self._get_market_currency(market),
                    "timezone": self._get_market_timezone(market),
                    "quality_score": cleaned_data.get("quality_score", 100),
                    "last_update": datetime.now().isoformat(),
                }
            )

            logger.debug(f"PTrade format converting completed : {symbol}")
            return ptrade_data

        except Exception as e:
            logger.error(f"PTrade format converting failed {symbol} {frequency}: {e}")
            return {}

    def _convert_daily_data(
        self, data: Dict[str, Any], symbol: str, target_date: date, market: str
    ) -> Dict[str, Any]:
        """转换日线数据"""
        try:
            ptrade_data = {}

            # 基础OHLCV数据
            ptrade_data.update(
                {
                    "open": float(data.get("open", 0)),
                    "high": float(data.get("high", 0)),
                    "low": float(data.get("low", 0)),
                    "close": float(data.get("close", 0)),
                    "volume": float(data.get("volume", 0)),
                    "money": float(data.get("amount", 0) or data.get("money", 0)),
                    "price": float(data.get("close", 0)),  # price = close
                }
            )

            # A股特有字段
            if market in ["SZ", "SS"]:
                ptrade_data.update(
                    {
                        "preclose": float(data.get("preclose", 0)),
                        "high_limit": float(data.get("high_limit", 0)),
                        "low_limit": float(data.get("low_limit", 0)),
                        "unlimited": int(data.get("unlimited", 0)),
                    }
                )

                # 计算涨跌停价格 (如果没有提供)
                if ptrade_data["high_limit"] == 0 and ptrade_data["preclose"] > 0:
                    ptrade_data["high_limit"] = self._calculate_limit_price(
                        ptrade_data["preclose"], "up", symbol
                    )

                if ptrade_data["low_limit"] == 0 and ptrade_data["preclose"] > 0:
                    ptrade_data["low_limit"] = self._calculate_limit_price(
                        ptrade_data["preclose"], "down", symbol
                    )

            # 估值指标
            if self.enable_valuation:
                ptrade_data.update(
                    {
                        "pe_ratio": float(
                            data.get("pe_ratio", 0)
                            or data.get("pe", 0)
                            or data.get("pe_ttm", 0)
                        ),
                        "pb_ratio": float(
                            data.get("pb_ratio", 0)
                            or data.get("pb", 0)
                            or data.get("pb_mrq", 0)
                        ),
                        "turnover_rate": float(
                            data.get("turnover_rate", 0)
                            or data.get("turnover", 0)
                            or data.get("turn", 0)
                        ),
                    }
                )

            # 计算缺失的字段
            ptrade_data = self._calculate_derived_fields(ptrade_data)

            return ptrade_data

        except Exception as e:
            logger.error(f"daily data converting failed {symbol}: {e}")
            return {}

    def _convert_minute_data(
        self,
        data: Dict[str, Any],
        symbol: str,
        target_date: date,
        frequency: str,
        market: str,
    ) -> Dict[str, Any]:
        """转换分钟线数据"""
        try:
            if "data" not in data or not data["data"]:
                return {}

            ptrade_data = {"data": []}

            for minute_data in data["data"]:
                converted_minute = {
                    "time": str(minute_data.get("time", "")),
                    "open": float(minute_data.get("open", 0)),
                    "high": float(minute_data.get("high", 0)),
                    "low": float(minute_data.get("low", 0)),
                    "close": float(minute_data.get("close", 0)),
                    "volume": float(minute_data.get("volume", 0)),
                    "money": float(
                        minute_data.get("amount", 0) or minute_data.get("money", 0)
                    ),
                    "price": float(minute_data.get("close", 0)),
                }

                ptrade_data["data"].append(converted_minute)

            # 计算汇总信息
            if ptrade_data["data"]:
                first_minute = ptrade_data["data"][0]
                last_minute = ptrade_data["data"][-1]

                # 计算日汇总数据
                all_highs = [m["high"] for m in ptrade_data["data"] if m["high"] > 0]
                all_lows = [m["low"] for m in ptrade_data["data"] if m["low"] > 0]
                total_volume = sum(m["volume"] for m in ptrade_data["data"])
                total_money = sum(m["money"] for m in ptrade_data["data"])

                ptrade_data.update(
                    {
                        "open": first_minute["open"],
                        "high": max(all_highs) if all_highs else 0,
                        "low": min(all_lows) if all_lows else 0,
                        "close": last_minute["close"],
                        "volume": total_volume,
                        "money": total_money,
                        "price": last_minute["close"],
                    }
                )

            return ptrade_data

        except Exception as e:
            logger.error(f"minute data converting failed {symbol}: {e}")
            return {}

    def _calculate_limit_price(
        self, preclose: float, direction: str, symbol: str
    ) -> float:
        """计算涨跌停价格"""
        try:
            # 获取涨跌停比例
            limit_ratio = self._get_limit_ratio(symbol)

            if direction == "up":
                limit_price = preclose * (1 + limit_ratio)
            else:  # down
                limit_price = preclose * (1 - limit_ratio)

            # 价格精度处理
            return self._round_price(limit_price)

        except Exception as e:
            logger.error(f"failed to calculate limit price {symbol}: {e}")
            return 0.0

    def _get_limit_ratio(self, symbol: str) -> float:
        """获取涨跌停比例"""
        try:
            # ST股票5%，科创板和创业板20%，其他10%
            if "ST" in symbol or "st" in symbol:
                return 0.05
            elif symbol.startswith("688"):  # 科创板
                return 0.20
            elif symbol.startswith("300"):  # 创业板
                return 0.20
            else:
                return 0.10

        except Exception:
            return 0.10

    def _round_price(self, price: float) -> float:
        """价格精度处理"""
        try:
            if price >= 1000:
                # 1000元以上，精确到分
                return round(price, 2)
            elif price >= 100:
                # 100-1000元，精确到分
                return round(price, 2)
            elif price >= 10:
                # 10-100元，精确到分
                return round(price, 2)
            else:
                # 10元以下，精确到厘
                return round(price, 3)

        except Exception:
            return round(price, 2)

    def _calculate_derived_fields(self, ptrade_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算派生字段"""
        try:
            # 计算涨跌额和涨跌幅
            close = ptrade_data.get("close", 0)
            preclose = ptrade_data.get("preclose", 0)

            if close > 0 and preclose > 0:
                change = close - preclose
                pct_change = (change / preclose) * 100

                ptrade_data.update(
                    {
                        "change": round(change, 3),
                        "pct_change": round(pct_change, 2),
                    }
                )

            # 计算换手率 (如果有流通股本信息)
            volume = ptrade_data.get("volume", 0)
            if volume > 0 and "float_share" in ptrade_data:
                float_share = ptrade_data["float_share"]
                if float_share > 0:
                    turnover_rate = (volume / float_share) * 100
                    ptrade_data["turnover_rate"] = round(turnover_rate, 2)

            # 计算振幅
            high = ptrade_data.get("high", 0)
            low = ptrade_data.get("low", 0)
            if high > 0 and low > 0 and preclose > 0:
                amplitude = ((high - low) / preclose) * 100
                ptrade_data["amplitude"] = round(amplitude, 2)

            return ptrade_data

        except Exception as e:
            logger.error(f"failed to calculate derived fields : {e}")
            return ptrade_data

    def _get_market_currency(self, market: str) -> str:
        """获取市场货币"""
        market_config = self.market_configs.get(market, {})
        return market_config.get("currency", self.default_currency)

    def _get_market_timezone(self, market: str) -> str:
        """获取市场时区"""
        market_config = self.market_configs.get(market, {})
        return market_config.get("timezone", self.default_timezone)

    def _get_market_features(self, market: str) -> List[str]:
        """获取市场特性"""
        market_config = self.market_configs.get(market, {})
        return market_config.get("features", [])

    def convert_stock_info(
        self, raw_info: Dict[str, Any], symbol: str
    ) -> Dict[str, Any]:
        """转换股票基础信息为PTrade格式"""
        try:
            market = self._parse_market_from_symbol(symbol)

            ptrade_info = {
                "symbol": symbol,
                "name": str(raw_info.get("name", "")),
                "market": market,
                "exchange": self._get_exchange_name(market),
                "industry": str(raw_info.get("industry", "")),
                "sector": str(raw_info.get("sector", raw_info.get("industry", ""))),
                "list_date": str(raw_info.get("list_date", "")),
                "delist_date": str(raw_info.get("delist_date", "")),
                "total_share": float(raw_info.get("total_share", 0)),
                "float_share": float(raw_info.get("float_share", 0)),
                "currency": self._get_market_currency(market),
                "timezone": self._get_market_timezone(market),
                "trading_hours": self._get_trading_hours(market),
                "status": str(raw_info.get("status", "active")),
                "last_update": datetime.now().isoformat(),
            }

            return ptrade_info

        except Exception as e:
            logger.error(f"stock info converting failed {symbol}: {e}")
            return {}

    def convert_fundamentals(
        self, raw_fundamentals: Dict[str, Any], symbol: str
    ) -> Dict[str, Any]:
        """转换财务数据为PTrade格式"""
        try:
            ptrade_fundamentals = {
                "symbol": symbol,
                "report_date": str(raw_fundamentals.get("report_date", "")),
                "report_type": str(raw_fundamentals.get("report_type", "Q4")),
                # 基础财务指标
                "revenue": float(raw_fundamentals.get("revenue", 0)),
                "net_profit": float(raw_fundamentals.get("net_profit", 0)),
                "total_assets": float(raw_fundamentals.get("total_assets", 0)),
                "total_equity": float(raw_fundamentals.get("total_equity", 0)),
                # 每股指标
                "eps": float(raw_fundamentals.get("eps", 0)),
                "bps": float(raw_fundamentals.get("bps", 0)),
                # 财务比率
                "roe": float(raw_fundamentals.get("roe", 0)),
                "roa": float(raw_fundamentals.get("roa", 0)),
                "gross_margin": float(raw_fundamentals.get("gross_margin", 0)),
                "net_margin": float(raw_fundamentals.get("net_margin", 0)),
                # 估值指标
                "pe_ratio": float(raw_fundamentals.get("pe_ratio", 0)),
                "pb_ratio": float(raw_fundamentals.get("pb_ratio", 0)),
                "ps_ratio": float(raw_fundamentals.get("ps_ratio", 0)),
                "last_update": datetime.now().isoformat(),
            }

            return ptrade_fundamentals

        except Exception as e:
            logger.error(f"financial data converting failed {symbol}: {e}")
            return {}

    def _parse_market_from_symbol(self, symbol: str) -> str:
        """从股票代码解析市场"""
        if symbol.endswith(".SZ"):
            return "SZ"
        elif symbol.endswith(".SS"):
            return "SS"
        elif symbol.endswith(".SH"):
            return "SS"
        elif symbol.endswith(".HK"):
            return "HK"
        elif symbol.endswith(".US"):
            return "US"
        else:
            # 根据代码前缀推断
            if symbol.startswith(("00", "30")):
                return "SZ"
            elif symbol.startswith(("60", "68")):
                return "SS"
            else:
                return "SZ"

    def _get_exchange_name(self, market: str) -> str:
        """获取交易所名称"""
        exchange_names = {
            "SZ": "深圳证券交易所",
            "SS": "上海证券交易所",
            "HK": "香港证券交易所",
            "US": "美国证券交易所",
        }
        return exchange_names.get(market, "")

    def _get_trading_hours(self, market: str) -> str:
        """获取交易时间"""
        market_config = self.market_configs.get(market, {})
        return market_config.get("trading_hours", "09:30-11:30,13:00-15:00")

    def get_conversion_stats(self) -> Dict[str, Any]:
        """获取转换统计信息"""
        return {
            "default_currency": self.default_currency,
            "default_timezone": self.default_timezone,
            "enable_valuation": self.enable_valuation,
            "supported_markets": list(self.market_configs.keys()),
        }
