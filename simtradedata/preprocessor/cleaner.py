"""
简化的数据清洗器

删除过度的健壮性代码，只保留基本的数据清洗功能。
"""

import logging
from typing import Any, Dict

from ..config import Config

logger = logging.getLogger(__name__)


class DataCleaner:
    """简化的数据清洗器"""

    def __init__(self, config: Config = None):
        """
        初始化数据清洗器（简化版）

        Args:
            config: 配置对象
        """
        self.config = config or Config()
        logger.info("data cleaner initialized completed (simplified version )")

    def clean_data(
        self, raw_data: Dict[str, Any], symbol: str, frequency: str
    ) -> Dict[str, Any]:
        """
        清洗原始数据（简化版）

        Args:
            raw_data: 原始数据
            symbol: 股票代码
            frequency: 频率

        Returns:
            Dict[str, Any]: 清洗后的数据
        """
        if not raw_data:
            logger.warning(f"raw data is empty : {symbol}")
            return {}

        try:
            logger.debug(f"starting clean data : {symbol} {frequency}")

            # 1. 基础验证
            if not self._validate_basic_structure(raw_data, symbol, frequency):
                logger.warning(f"data structure validation failed : {symbol}")
                return {}

            # 2. 数据类型转换
            cleaned_data = self._convert_data_types(raw_data)

            # 3. 基本数据一致性检查
            cleaned_data = self._check_data_consistency(cleaned_data, symbol, frequency)

            # 4. 设置基本质量评分
            cleaned_data["quality_score"] = 100  # 简化质量评分

            logger.debug(
                f"data cleaning completed : {symbol}, quality 评分: {cleaned_data.get('quality_score', 0)}"
            )

            return cleaned_data

        except Exception as e:
            logger.error(f"data clean failed {symbol}: {e}")
            return {}

    def _validate_basic_structure(
        self, data: Dict[str, Any], symbol: str, frequency: str
    ) -> bool:
        """验证基础数据结构"""
        try:
            if not isinstance(data, dict):
                return False

            # 检查关键字段
            if frequency == "1d":
                required_fields = ["open", "high", "low", "close", "volume"]
                return all(field in data for field in required_fields)
            else:
                # 分钟线数据
                return "data" in data and isinstance(data["data"], list)

        except Exception as e:
            logger.error(f"data structure validation failed {symbol}: {e}")
            return False

    def _convert_data_types(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """转换数据类型"""
        cleaned_data = data.copy()

        try:
            # 数值字段转换
            numeric_fields = [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "money",
                "prev_close",
                "change_amount",
                "change_percent",
                "amplitude",
                "high_limit",
                "low_limit",
                "turnover_rate",
            ]

            for field in numeric_fields:
                if field in cleaned_data:
                    try:
                        cleaned_data[field] = float(cleaned_data[field])
                    except (ValueError, TypeError):
                        cleaned_data[field] = 0.0

            # 布尔字段转换
            bool_fields = ["is_limit_up", "is_limit_down"]
            for field in bool_fields:
                if field in cleaned_data:
                    cleaned_data[field] = bool(cleaned_data[field])

            return cleaned_data

        except Exception as e:
            logger.error(f"data type converting failed : {e}")
            return data

    def _check_data_consistency(
        self, data: Dict[str, Any], symbol: str, frequency: str
    ) -> Dict[str, Any]:
        """检查数据一致性（简化版）"""
        try:
            cleaned_data = data.copy()

            # 基本的OHLC逻辑检查
            if frequency == "1d":
                open_price = data.get("open", 0)
                high_price = data.get("high", 0)
                low_price = data.get("low", 0)
                close_price = data.get("close", 0)

                # 检查价格是否为正数
                if any(
                    price <= 0
                    for price in [open_price, high_price, low_price, close_price]
                ):
                    logger.warning(f"price data exception : {symbol}")
                    return {}

                # 检查高低价关系
                if high_price < low_price:
                    logger.warning(f"high-low price relationship exception : {symbol}")
                    return {}

                # 检查开盘价和收盘价是否在合理范围内
                if not (low_price <= open_price <= high_price):
                    logger.warning(f"open price exception : {symbol}")
                    return {}

                if not (low_price <= close_price <= high_price):
                    logger.warning(f"close price exception : {symbol}")
                    return {}

            return cleaned_data

        except Exception as e:
            logger.error(f"data consistency check failed {symbol}: {e}")
            return data

    def get_cleaning_stats(self) -> Dict[str, Any]:
        """获取清洗统计信息（简化版）"""
        return {
            "version": "simplified",
            "features": ["basic_validation", "type_conversion", "consistency_check"],
        }
