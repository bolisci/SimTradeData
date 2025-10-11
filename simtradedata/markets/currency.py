"""
货币转换器

提供多货币之间的汇率转换功能。
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from ..config import Config
from ..database import DatabaseManager

logger = logging.getLogger(__name__)


class CurrencyConverter:
    """货币转换器"""

    def __init__(self, db_manager: DatabaseManager, config: Config = None):
        """
        初始化货币转换器

        Args:
            db_manager: 数据库管理器
            config: 配置对象
        """
        self.db_manager = db_manager
        self.config = config or Config()

        # 支持的货币
        self.supported_currencies = ["CNY", "HKD", "USD", "EUR", "JPY", "GBP"]

        # 基准货币
        self.base_currency = self.config.get("currency.base_currency", "CNY")

        # 汇率缓存
        self.exchange_rates_cache = {}
        self.cache_expiry = {}
        self.cache_duration = self.config.get("currency.cache_duration", 3600)  # 1小时

        # 默认汇率 (作为备用)
        self.default_rates = {
            "CNY": 1.0,
            "HKD": 0.9,
            "USD": 7.2,
            "EUR": 7.8,
            "JPY": 0.05,
            "GBP": 9.1,
        }

        logger.info("currency converter initialized completed")

    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        date: Optional[date] = None,
    ) -> Optional[float]:
        """
        货币转换

        Args:
            amount: 金额
            from_currency: 源货币
            to_currency: 目标货币
            date: 汇率日期，默认为今天

        Returns:
            Optional[float]: 转换后的金额
        """
        try:
            if amount is None or amount == 0:
                return 0.0

            # 相同货币直接返回
            if from_currency == to_currency:
                return amount

            # 获取汇率
            rate = self.get_exchange_rate(from_currency, to_currency, date)

            if rate is None:
                logger.warning(
                    f"unable to retrieve exchange rate : {from_currency} -> {to_currency}"
                )
                return None

            converted_amount = amount * rate

            logger.debug(
                f"currency converting : {amount} {from_currency} = {converted_amount:.4f} {to_currency} ( exchange rate : {rate})"
            )
            return round(converted_amount, 4)

        except Exception as e:
            logger.error(f"currency converting failed : {e}")
            return None

    def get_exchange_rate(
        self, from_currency: str, to_currency: str, date: Optional[date] = None
    ) -> Optional[float]:
        """
        获取汇率

        Args:
            from_currency: 源货币
            to_currency: 目标货币
            date: 汇率日期，默认为今天

        Returns:
            Optional[float]: 汇率
        """
        try:
            if from_currency == to_currency:
                return 1.0

            if date is None:
                date = datetime.now().date()

            # 检查缓存
            cache_key = f"{from_currency}_{to_currency}_{date}"
            if self._is_cache_valid(cache_key):
                return self.exchange_rates_cache[cache_key]

            # 从数据库获取汇率
            rate = self._get_rate_from_db(from_currency, to_currency, date)

            if rate is None:
                # 使用默认汇率计算
                rate = self._calculate_default_rate(from_currency, to_currency)

            # 缓存汇率
            if rate is not None:
                self._cache_rate(cache_key, rate)

            return rate

        except Exception as e:
            logger.error(f"failed to retrieve exchange rate : {e}")
            return None

    def update_exchange_rates(
        self, rates_data: Dict[str, Dict[str, float]], rate_date: date = None
    ) -> bool:
        """
        更新汇率数据

        Args:
            rates_data: 汇率数据 {from_currency: {to_currency: rate}}
            rate_date: 汇率日期

        Returns:
            bool: 是否更新成功
        """
        try:
            if rate_date is None:
                rate_date = datetime.now().date()

            updated_count = 0

            for from_currency, to_rates in rates_data.items():
                for to_currency, rate in to_rates.items():
                    success = self._save_rate_to_db(
                        from_currency, to_currency, rate, rate_date
                    )
                    if success:
                        updated_count += 1

                        # 更新缓存
                        cache_key = f"{from_currency}_{to_currency}_{rate_date}"
                        self._cache_rate(cache_key, rate)

            logger.info(
                f"exchange rate updating completed : updating {updated_count} records exchange rate data"
            )
            return updated_count > 0

        except Exception as e:
            logger.error(f"updating exchange rate failed : {e}")
            return False

    def get_supported_currencies(self) -> List[str]:
        """获取支持的货币列表"""
        return self.supported_currencies.copy()

    def is_currency_supported(self, currency: str) -> bool:
        """检查货币是否支持"""
        return currency.upper() in self.supported_currencies

    def convert_price_data(
        self, price_data: Dict[str, Any], target_currency: str
    ) -> Dict[str, Any]:
        """
        转换价格数据中的货币

        Args:
            price_data: 价格数据
            target_currency: 目标货币

        Returns:
            Dict[str, Any]: 转换后的价格数据
        """
        try:
            converted_data = price_data.copy()

            source_currency = price_data.get("currency", "CNY")
            trade_date_str = price_data.get("trade_date")

            if source_currency == target_currency:
                return converted_data

            # 解析交易日期
            trade_date = None
            if trade_date_str:
                try:
                    trade_date = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
                except ValueError:
                    trade_date = datetime.now().date()

            # 需要转换的价格字段
            price_fields = [
                "open",
                "high",
                "low",
                "close",
                "preclose",
                "money",
                "high_limit",
                "low_limit",
                "adj_close",
            ]

            for field in price_fields:
                if field in converted_data and converted_data[field] is not None:
                    converted_value = self.convert(
                        converted_data[field],
                        source_currency,
                        target_currency,
                        trade_date,
                    )
                    if converted_value is not None:
                        converted_data[field] = converted_value

            # 更新货币字段
            converted_data["currency"] = target_currency
            converted_data["original_currency"] = source_currency

            logger.debug(
                f"price data currency converting completed : {source_currency} -> {target_currency}"
            )
            return converted_data

        except Exception as e:
            logger.error(f"price data currency converting failed : {e}")
            return price_data

    def get_currency_info(self, currency: str) -> Dict[str, Any]:
        """
        获取货币信息

        Args:
            currency: 货币代码

        Returns:
            Dict[str, Any]: 货币信息
        """
        currency_info = {
            "CNY": {
                "code": "CNY",
                "name": "人民币",
                "name_en": "Chinese Yuan",
                "symbol": "¥",
                "precision": 2,
                "country": "CN",
            },
            "HKD": {
                "code": "HKD",
                "name": "港币",
                "name_en": "Hong Kong Dollar",
                "symbol": "HK$",
                "precision": 2,
                "country": "HK",
            },
            "USD": {
                "code": "USD",
                "name": "美元",
                "name_en": "US Dollar",
                "symbol": "$",
                "precision": 2,
                "country": "US",
            },
            "EUR": {
                "code": "EUR",
                "name": "欧元",
                "name_en": "Euro",
                "symbol": "€",
                "precision": 2,
                "country": "EU",
            },
            "JPY": {
                "code": "JPY",
                "name": "日元",
                "name_en": "Japanese Yen",
                "symbol": "¥",
                "precision": 0,
                "country": "JP",
            },
            "GBP": {
                "code": "GBP",
                "name": "英镑",
                "name_en": "British Pound",
                "symbol": "£",
                "precision": 2,
                "country": "GB",
            },
        }

        return currency_info.get(currency.upper(), {})

    def _get_rate_from_db(
        self, from_currency: str, to_currency: str, date: date
    ) -> Optional[float]:
        """从数据库获取汇率"""
        try:
            sql = """
            SELECT exchange_rate FROM ptrade_exchange_rates 
            WHERE from_currency = ? AND to_currency = ? AND rate_date = ?
            ORDER BY update_time DESC LIMIT 1
            """

            result = self.db_manager.fetchone(
                sql, (from_currency, to_currency, str(date))
            )

            if result:
                return float(result["exchange_rate"])

            # 尝试获取最近的汇率
            sql = """
            SELECT exchange_rate FROM ptrade_exchange_rates 
            WHERE from_currency = ? AND to_currency = ? AND rate_date <= ?
            ORDER BY rate_date DESC, update_time DESC LIMIT 1
            """

            result = self.db_manager.fetchone(
                sql, (from_currency, to_currency, str(date))
            )

            if result:
                return float(result["exchange_rate"])

            return None

        except Exception as e:
            logger.error(f"failed to retrieve exchange rate from database : {e}")
            return None

    def _save_rate_to_db(
        self, from_currency: str, to_currency: str, rate: float, date: date
    ) -> bool:
        """保存汇率到数据库"""
        try:
            sql = """
            INSERT OR REPLACE INTO ptrade_exchange_rates 
            (from_currency, to_currency, exchange_rate, rate_date, update_time)
            VALUES (?, ?, ?, ?, ?)
            """

            self.db_manager.execute(
                sql,
                (
                    from_currency,
                    to_currency,
                    rate,
                    str(date),
                    datetime.now().isoformat(),
                ),
            )

            return True

        except Exception as e:
            logger.error(f"failed to save exchange rate to database : {e}")
            return False

    def _calculate_default_rate(
        self, from_currency: str, to_currency: str
    ) -> Optional[float]:
        """使用默认汇率计算"""
        try:
            from_rate = self.default_rates.get(from_currency)
            to_rate = self.default_rates.get(to_currency)

            if from_rate is None or to_rate is None:
                return None

            # 通过基准货币转换
            if from_currency == self.base_currency:
                return 1.0 / to_rate
            elif to_currency == self.base_currency:
                return from_rate
            else:
                return from_rate / to_rate

        except Exception as e:
            logger.error(f"failed to calculate default exchange rate : {e}")
            return None

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.exchange_rates_cache:
            return False

        if cache_key not in self.cache_expiry:
            return False

        return datetime.now() < self.cache_expiry[cache_key]

    def _cache_rate(self, cache_key: str, rate: float):
        """缓存汇率"""
        self.exchange_rates_cache[cache_key] = rate
        self.cache_expiry[cache_key] = datetime.now() + timedelta(
            seconds=self.cache_duration
        )

    def clear_cache(self):
        """清空缓存"""
        self.exchange_rates_cache.clear()
        self.cache_expiry.clear()
        logger.info("exchange rate cache cleared")

    def get_converter_stats(self) -> Dict[str, Any]:
        """获取转换器统计信息"""
        return {
            "supported_currencies": self.supported_currencies,
            "base_currency": self.base_currency,
            "cache_size": len(self.exchange_rates_cache),
            "cache_duration": self.cache_duration,
            "default_rates": self.default_rates.copy(),
        }
