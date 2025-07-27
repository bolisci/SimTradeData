"""
结果格式化器

负责将查询结果转换为不同的输出格式，如DataFrame、JSON等。
"""

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List

import pandas as pd

from ..config import Config

logger = logging.getLogger(__name__)


class ResultFormatter:
    """结果格式化器"""

    def __init__(self, config: Config = None):
        """
        初始化结果格式化器

        Args:
            config: 配置对象
        """
        self.config = config or Config()

        # 格式化配置
        self.default_format = self.config.get("api.default_format", "dataframe")
        self.float_precision = self.config.get("api.float_precision", 4)
        self.date_format = self.config.get("api.date_format", "%Y-%m-%d")
        self.include_metadata = self.config.get("api.include_metadata", True)

        logger.debug("结果格式化器初始化完成")

    def format_result(
        self,
        data: List[Dict[str, Any]],
        format_type: str = None,
        metadata: Dict[str, Any] = None,
    ) -> Any:
        """
        格式化查询结果

        Args:
            data: 原始查询结果
            format_type: 输出格式 (dataframe/json/dict/records)
            metadata: 元数据信息

        Returns:
            Any: 格式化后的结果
        """
        if format_type is None:
            format_type = self.default_format

        try:
            # 数据预处理
            processed_data = self._preprocess_data(data)

            # 根据格式类型进行转换
            if format_type == "dataframe":
                result = self._to_dataframe(processed_data)
            elif format_type == "json":
                result = self._to_json(processed_data, metadata)
            elif format_type == "dict":
                result = self._to_dict(processed_data, metadata)
            elif format_type == "records":
                result = self._to_records(processed_data)
            else:
                raise ValueError(f"不支持的格式类型: {format_type}")

            logger.debug(f"结果格式化完成: {format_type}, 数据量: {len(data)}")
            return result

        except Exception as e:
            logger.error(f"结果格式化失败: {e}")
            raise

    def _preprocess_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """预处理数据"""
        if not data:
            return []

        processed = []

        for row in data:
            processed_row = {}

            for key, value in row.items():
                # 处理数值类型
                if isinstance(value, float):
                    processed_row[key] = round(value, self.float_precision)
                elif isinstance(value, (int, str, bool)) or value is None:
                    processed_row[key] = value
                else:
                    # 其他类型转换为字符串
                    processed_row[key] = str(value)

            processed.append(processed_row)

        return processed

    def _to_dataframe(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        """转换为DataFrame格式"""
        if not data:
            return pd.DataFrame()

        try:
            df = pd.DataFrame(data)

            # 数据类型优化
            df = self._optimize_dataframe_dtypes(df)

            # 设置索引
            if "symbol" in df.columns and "trade_date" in df.columns:
                df = df.set_index(["symbol", "trade_date"])
            elif "symbol" in df.columns:
                df = df.set_index("symbol")

            return df

        except Exception as e:
            logger.error(f"DataFrame转换失败: {e}")
            return pd.DataFrame(data)

    def _optimize_dataframe_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """优化DataFrame数据类型"""
        try:
            # 日期列转换
            date_columns = ["trade_date", "list_date", "delist_date", "report_date"]
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")

            # 数值列转换
            numeric_columns = [
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
                "ma5",
                "ma10",
                "ma20",
                "ma60",
                "revenue",
                "net_profit",
                "total_assets",
                "total_equity",
                "eps",
                "bps",
                "roe",
                "roa",
                "total_share",
                "float_share",
            ]

            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # 分类列转换
            category_columns = [
                "market",
                "frequency",
                "industry",
                "status",
                "report_type",
            ]
            for col in category_columns:
                if col in df.columns:
                    df[col] = df[col].astype("category")

            return df

        except Exception as e:
            logger.warning(f"数据类型优化失败: {e}")
            return df

    def _to_json(
        self, data: List[Dict[str, Any]], metadata: Dict[str, Any] = None
    ) -> str:
        """转换为JSON格式"""
        try:
            result = {
                "data": data,
                "count": len(data),
            }

            if self.include_metadata and metadata:
                result["metadata"] = metadata

            result["timestamp"] = datetime.now().isoformat()

            return json.dumps(
                result, ensure_ascii=False, indent=2, default=self._json_serializer
            )

        except Exception as e:
            logger.error(f"JSON转换失败: {e}")
            return json.dumps({"error": str(e), "data": []})

    def _to_dict(
        self, data: List[Dict[str, Any]], metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """转换为字典格式"""
        try:
            result = {
                "data": data,
                "count": len(data),
            }

            if self.include_metadata and metadata:
                result["metadata"] = metadata

            result["timestamp"] = datetime.now().isoformat()

            return result

        except Exception as e:
            logger.error(f"字典转换失败: {e}")
            return {"error": str(e), "data": []}

    def _to_records(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """转换为记录列表格式"""
        return data

    def _json_serializer(self, obj):
        """JSON序列化器"""
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        elif pd.isna(obj):
            return None
        else:
            return str(obj)

    def format_history_result(
        self,
        data: List[Dict[str, Any]],
        symbols: List[str],
        start_date: str,
        end_date: str,
        frequency: str,
        format_type: str = None,
    ) -> Any:
        """
        格式化历史数据结果

        Args:
            data: 查询结果
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            frequency: 频率
            format_type: 输出格式

        Returns:
            Any: 格式化后的结果
        """
        metadata = {
            "query_type": "history",
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "frequency": frequency,
            "symbol_count": len(symbols),
            "record_count": len(data),
        }

        return self.format_result(data, format_type, metadata)

    def format_snapshot_result(
        self,
        data: List[Dict[str, Any]],
        trade_date: str = None,
        market: str = None,
        format_type: str = None,
    ) -> Any:
        """
        格式化快照数据结果

        Args:
            data: 查询结果
            trade_date: 交易日期
            market: 市场
            format_type: 输出格式

        Returns:
            Any: 格式化后的结果
        """
        metadata = {
            "query_type": "snapshot",
            "trade_date": trade_date,
            "market": market,
            "record_count": len(data),
        }

        return self.format_result(data, format_type, metadata)

    def format_fundamentals_result(
        self,
        data: List[Dict[str, Any]],
        symbols: List[str],
        report_date: str = None,
        report_type: str = None,
        format_type: str = None,
    ) -> Any:
        """
        格式化财务数据结果

        Args:
            data: 查询结果
            symbols: 股票代码列表
            report_date: 报告期
            report_type: 报告类型
            format_type: 输出格式

        Returns:
            Any: 格式化后的结果
        """
        metadata = {
            "query_type": "fundamentals",
            "symbols": symbols,
            "report_date": report_date,
            "report_type": report_type,
            "symbol_count": len(symbols),
            "record_count": len(data),
        }

        return self.format_result(data, format_type, metadata)

    def format_stock_info_result(
        self,
        data: List[Dict[str, Any]],
        market: str = None,
        industry: str = None,
        format_type: str = None,
    ) -> Any:
        """
        格式化股票信息结果

        Args:
            data: 查询结果
            market: 市场
            industry: 行业
            format_type: 输出格式

        Returns:
            Any: 格式化后的结果
        """
        metadata = {
            "query_type": "stock_info",
            "market": market,
            "industry": industry,
            "record_count": len(data),
        }

        return self.format_result(data, format_type, metadata)

    def format_error_result(
        self, error_message: str, error_code: str = None, format_type: str = None
    ) -> Any:
        """
        格式化错误结果

        Args:
            error_message: 错误消息
            error_code: 错误代码
            format_type: 输出格式

        Returns:
            Any: 格式化后的错误结果
        """
        if format_type is None:
            format_type = self.default_format

        error_data = {
            "error": True,
            "error_message": error_message,
            "error_code": error_code,
            "timestamp": datetime.now().isoformat(),
        }

        if format_type == "dataframe":
            return pd.DataFrame()
        elif format_type == "json":
            return json.dumps(error_data, ensure_ascii=False, indent=2)
        else:
            return error_data

    def get_format_info(self) -> Dict[str, Any]:
        """获取格式化器信息"""
        return {
            "default_format": self.default_format,
            "supported_formats": ["dataframe", "json", "dict", "records"],
            "float_precision": self.float_precision,
            "date_format": self.date_format,
            "include_metadata": self.include_metadata,
        }
