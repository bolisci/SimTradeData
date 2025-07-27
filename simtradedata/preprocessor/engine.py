"""
数据处理引擎 - 极简版本，没有健壮代码和try-catch
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from ..config import Config
from ..data_sources.manager import DataSourceManager
from ..database.manager import DatabaseManager

logger = logging.getLogger(__name__)


class DataProcessingEngine:
    """数据处理引擎 - 极简版本"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        data_source_manager: DataSourceManager,
        config: Optional[Config] = None,
    ):
        self.db_manager = db_manager
        self.data_source_manager = data_source_manager
        self.config = config or Config()

        # 配置参数
        self.batch_size = self.config.get("processing.batch_size", 50)
        self.enable_technical_indicators = self.config.get(
            "processing.enable_technical_indicators", True
        )
        self.enable_valuations = self.config.get("processing.enable_valuations", True)

    def process_symbol_data(
        self,
        symbol: str,
        start_date: date,
        end_date: Optional[date] = None,
        frequency: str = "1d",
        force_update: bool = False,
    ) -> Dict[str, Any]:
        """处理股票数据 - 极简版本"""
        if end_date is None:
            end_date = start_date

        result = {
            "symbol": symbol,
            "processed_dates": [],
            "skipped_dates": [],
            "failed_dates": [],
            "total_records": 0,
        }

        # 获取原始数据
        raw_data = self.data_source_manager.get_daily_data(symbol, start_date, end_date)

        # 直接处理DataFrame
        if hasattr(raw_data, "iterrows"):
            for _, row in raw_data.iterrows():
                daily_data = row.to_dict()

                # 简单验证
                validated_data = self._validate_data(daily_data)

                # 存储数据
                self._store_market_data(
                    validated_data, symbol, daily_data.get("date", start_date)
                )

                result["processed_dates"].append(
                    str(daily_data.get("date", start_date))
                )

        result["total_records"] = len(result["processed_dates"])
        return result

    def process_stock_data(
        self,
        symbol: str,
        start_date: date,
        end_date: Optional[date] = None,
        frequency: str = "1d",
        force_update: bool = False,
    ) -> Dict[str, Any]:
        """处理股票数据 - 别名方法"""
        return self.process_symbol_data(
            symbol, start_date, end_date, frequency, force_update
        )

    def _validate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """极简数据验证（修复空字符串转换问题）"""
        # 字段映射
        field_mapping = {
            "open": ["open", "开盘"],
            "high": ["high", "最高"],
            "low": ["low", "最低"],
            "close": ["close", "收盘"],
            "volume": ["volume", "成交量"],
        }

        def safe_float(value, default=0.0):
            """安全的浮点数转换"""
            if value is None or value == "" or str(value).strip() == "":
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        validated_data = {}
        for std_field, possible_fields in field_mapping.items():
            for field in possible_fields:
                if field in data:
                    validated_data[std_field] = safe_float(data[field])
                    break
            else:
                validated_data[std_field] = 0.0

        return validated_data

    def _store_market_data(self, data: Dict[str, Any], symbol: str, trade_date):
        """存储市场数据"""
        sql = """
        INSERT OR REPLACE INTO market_data (
            symbol, date, frequency, open, high, low, close, volume, amount, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            symbol,
            str(trade_date),
            "1d",
            data.get("open", 0),
            data.get("high", 0),
            data.get("low", 0),
            data.get("close", 0),
            data.get("volume", 0),
            data.get("amount", 0),
            "baostock",
        )

        self.db_manager.execute(sql, params)

    def process_symbols_batch_pipeline(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        batch_size: int = 10,
        max_workers: int = 4,
        progress_bar=None,
    ) -> Dict[str, Any]:
        """批量处理股票数据 - 极简版本"""
        result = {
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "processed_symbols": [],
            "failed_symbols": [],
        }

        # 简单的串行处理
        for symbol in symbols:
            symbol_result = self.process_symbol_data(symbol, start_date, end_date)

            if symbol_result["total_records"] > 0:
                result["success_count"] += 1
                result["processed_symbols"].append(symbol)
                result["total_records"] += symbol_result["total_records"]
            else:
                result["error_count"] += 1
                result["failed_symbols"].append(symbol)

            if progress_bar:
                progress_bar.update(1)

        return result

    def _get_market_from_symbol(self, symbol: str) -> str:
        """从股票代码获取市场"""
        if symbol.endswith(".SZ"):
            return "SZ"
        elif symbol.endswith(".SS"):
            return "SS"
        elif symbol.endswith(".HK"):
            return "HK"
        elif symbol.endswith(".US"):
            return "US"
        else:
            return "CN"

    def _calculate_quality_score(self, result: Dict[str, Any]) -> float:
        """计算质量分数"""
        total = len(result["processed_dates"]) + len(result["failed_dates"])
        if total == 0:
            return 0.0
        return len(result["processed_dates"]) / total * 100
