"""
ETF数据管理器

负责ETF基础信息、成分股数据和净值数据的管理。
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from ..config import Config
from ..database import DatabaseManager

logger = logging.getLogger(__name__)


class ETFDataManager:
    """ETF数据管理器"""

    def __init__(self, db_manager: DatabaseManager, config: Config = None):
        """
        初始化ETF数据管理器

        Args:
            db_manager: 数据库管理器
            config: 配置对象
        """
        self.db_manager = db_manager
        self.config = config or Config()

        # ETF类型映射
        self.etf_types = {
            "stock": "股票型ETF",
            "bond": "债券型ETF",
            "commodity": "商品型ETF",
            "currency": "货币型ETF",
            "sector": "行业ETF",
            "index": "指数ETF",
            "inverse": "反向ETF",
            "leveraged": "杠杆ETF",
        }

        # ETF状态
        self.etf_status = {
            "active": "正常交易",
            "suspended": "暂停交易",
            "delisted": "已退市",
            "pending": "待上市",
        }

        logger.info("ETF数据管理器初始化完成")

    def save_etf_info(self, etf_data: Dict[str, Any]) -> bool:
        """
        保存ETF基础信息

        Args:
            etf_data: ETF基础信息数据

        Returns:
            bool: 是否保存成功
        """
        try:
            # 标准化ETF数据
            standardized_data = self._standardize_etf_info(etf_data)

            sql = """
            INSERT OR REPLACE INTO ptrade_etf_info 
            (symbol, name, name_en, market, exchange, currency, etf_type, 
             underlying_index, management_company, custodian_bank, 
             inception_date, expense_ratio, tracking_error, aum, 
             nav_frequency, dividend_frequency, status, last_update)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            self.db_manager.execute(
                sql,
                (
                    standardized_data["symbol"],
                    standardized_data["name"],
                    standardized_data.get("name_en"),
                    standardized_data["market"],
                    standardized_data.get("exchange"),
                    standardized_data.get("currency", "CNY"),
                    standardized_data.get("etf_type", "stock"),
                    standardized_data.get("underlying_index"),
                    standardized_data.get("management_company"),
                    standardized_data.get("custodian_bank"),
                    standardized_data.get("inception_date"),
                    standardized_data.get("expense_ratio"),
                    standardized_data.get("tracking_error"),
                    standardized_data.get("aum"),
                    standardized_data.get("nav_frequency", "daily"),
                    standardized_data.get("dividend_frequency", "quarterly"),
                    standardized_data.get("status", "active"),
                    datetime.now().isoformat(),
                ),
            )

            logger.info(f"ETF基础信息保存成功: {standardized_data['symbol']}")
            return True

        except Exception as e:
            logger.error(f"保存ETF基础信息失败: {e}")
            return False

    def save_etf_holdings(
        self,
        etf_symbol: str,
        holdings_data: List[Dict[str, Any]],
        holding_date: date = None,
    ) -> bool:
        """
        保存ETF成分股数据

        Args:
            etf_symbol: ETF代码
            holdings_data: 成分股数据列表
            holding_date: 持仓日期

        Returns:
            bool: 是否保存成功
        """
        try:
            if holding_date is None:
                holding_date = datetime.now().date()

            # 删除旧的成分股数据
            delete_sql = """
            DELETE FROM ptrade_etf_holdings 
            WHERE etf_symbol = ? AND holding_date = ?
            """
            self.db_manager.execute(delete_sql, (etf_symbol, str(holding_date)))

            # 插入新的成分股数据
            insert_sql = """
            INSERT INTO ptrade_etf_holdings 
            (etf_symbol, holding_date, stock_symbol, stock_name, weight, 
             shares, market_value, sector, last_update)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            saved_count = 0
            for holding in holdings_data:
                try:
                    standardized_holding = self._standardize_holding_data(holding)

                    self.db_manager.execute(
                        insert_sql,
                        (
                            etf_symbol,
                            str(holding_date),
                            standardized_holding["stock_symbol"],
                            standardized_holding.get("stock_name"),
                            standardized_holding.get("weight"),
                            standardized_holding.get("shares"),
                            standardized_holding.get("market_value"),
                            standardized_holding.get("sector"),
                            datetime.now().isoformat(),
                        ),
                    )

                    saved_count += 1

                except Exception as e:
                    logger.error(f"保存单个成分股失败 {holding}: {e}")

            logger.info(
                f"ETF成分股保存完成: {etf_symbol}, 成功保存 {saved_count} 只成分股"
            )
            return saved_count > 0

        except Exception as e:
            logger.error(f"保存ETF成分股失败: {e}")
            return False

    def save_etf_nav(self, nav_data: Dict[str, Any]) -> bool:
        """
        保存ETF净值数据

        Args:
            nav_data: ETF净值数据

        Returns:
            bool: 是否保存成功
        """
        try:
            standardized_data = self._standardize_nav_data(nav_data)

            sql = """
            INSERT OR REPLACE INTO ptrade_etf_nav 
            (symbol, nav_date, unit_nav, accumulated_nav, estimated_nav, 
             premium_discount, creation_redemption, dividend_per_unit, 
             last_update)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            self.db_manager.execute(
                sql,
                (
                    standardized_data["symbol"],
                    standardized_data["nav_date"],
                    standardized_data.get("unit_nav"),
                    standardized_data.get("accumulated_nav"),
                    standardized_data.get("estimated_nav"),
                    standardized_data.get("premium_discount"),
                    standardized_data.get("creation_redemption"),
                    standardized_data.get("dividend_per_unit"),
                    datetime.now().isoformat(),
                ),
            )

            logger.debug(
                f"ETF净值保存成功: {standardized_data['symbol']} {standardized_data['nav_date']}"
            )
            return True

        except Exception as e:
            logger.error(f"保存ETF净值失败: {e}")
            return False

    def get_etf_info(self, etf_symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取ETF基础信息

        Args:
            etf_symbol: ETF代码

        Returns:
            Optional[Dict[str, Any]]: ETF基础信息
        """
        try:
            sql = """
            SELECT * FROM ptrade_etf_info 
            WHERE symbol = ?
            """

            result = self.db_manager.fetchone(sql, (etf_symbol,))

            if result:
                return dict(result)
            else:
                return None

        except Exception as e:
            logger.error(f"获取ETF基础信息失败: {e}")
            return None

    def get_etf_holdings(
        self, etf_symbol: str, holding_date: date = None
    ) -> List[Dict[str, Any]]:
        """
        获取ETF成分股

        Args:
            etf_symbol: ETF代码
            holding_date: 持仓日期，默认为最新

        Returns:
            List[Dict[str, Any]]: 成分股列表
        """
        try:
            if holding_date is None:
                # 获取最新持仓日期
                date_sql = """
                SELECT MAX(holding_date) as latest_date 
                FROM ptrade_etf_holdings 
                WHERE etf_symbol = ?
                """
                date_result = self.db_manager.fetchone(date_sql, (etf_symbol,))

                if not date_result or not date_result["latest_date"]:
                    return []

                holding_date = datetime.strptime(
                    date_result["latest_date"], "%Y-%m-%d"
                ).date()

            sql = """
            SELECT * FROM ptrade_etf_holdings 
            WHERE etf_symbol = ? AND holding_date = ?
            ORDER BY weight DESC
            """

            results = self.db_manager.fetchall(sql, (etf_symbol, str(holding_date)))

            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"获取ETF成分股失败: {e}")
            return []

    def get_etf_nav_history(
        self, etf_symbol: str, start_date: date = None, end_date: date = None
    ) -> List[Dict[str, Any]]:
        """
        获取ETF净值历史

        Args:
            etf_symbol: ETF代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            List[Dict[str, Any]]: 净值历史数据
        """
        try:
            if end_date is None:
                end_date = datetime.now().date()

            if start_date is None:
                start_date = end_date - timedelta(days=30)

            sql = """
            SELECT * FROM ptrade_etf_nav 
            WHERE symbol = ? AND nav_date >= ? AND nav_date <= ?
            ORDER BY nav_date DESC
            """

            results = self.db_manager.fetchall(
                sql, (etf_symbol, str(start_date), str(end_date))
            )

            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"获取ETF净值历史失败: {e}")
            return []

    def get_etf_list(
        self, etf_type: str = None, market: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取ETF列表

        Args:
            etf_type: ETF类型筛选
            market: 市场筛选

        Returns:
            List[Dict[str, Any]]: ETF列表
        """
        try:
            conditions = []
            params = []

            if etf_type:
                conditions.append("etf_type = ?")
                params.append(etf_type)

            if market:
                conditions.append("market = ?")
                params.append(market)

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            sql = f"""
            SELECT symbol, name, etf_type, market, aum, expense_ratio, status
            FROM ptrade_etf_info 
            {where_clause}
            ORDER BY aum DESC
            """

            results = self.db_manager.fetchall(sql, params)

            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"获取ETF列表失败: {e}")
            return []

    def calculate_etf_performance(
        self, etf_symbol: str, days: int = 30
    ) -> Dict[str, Any]:
        """
        计算ETF业绩表现

        Args:
            etf_symbol: ETF代码
            days: 计算天数

        Returns:
            Dict[str, Any]: 业绩数据
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            # 获取净值数据
            nav_history = self.get_etf_nav_history(etf_symbol, start_date, end_date)

            if len(nav_history) < 2:
                return {}

            # 按日期排序
            nav_history.sort(key=lambda x: x["nav_date"])

            latest_nav = nav_history[-1]
            earliest_nav = nav_history[0]

            # 计算收益率
            if earliest_nav["unit_nav"] and latest_nav["unit_nav"]:
                return_rate = (
                    (latest_nav["unit_nav"] - earliest_nav["unit_nav"])
                    / earliest_nav["unit_nav"]
                ) * 100
            else:
                return_rate = 0.0

            # 计算波动率
            nav_values = [nav["unit_nav"] for nav in nav_history if nav["unit_nav"]]
            if len(nav_values) > 1:
                returns = []
                for i in range(1, len(nav_values)):
                    daily_return = (nav_values[i] - nav_values[i - 1]) / nav_values[
                        i - 1
                    ]
                    returns.append(daily_return)

                if returns:
                    import statistics

                    volatility = (
                        statistics.stdev(returns) * (252**0.5) * 100
                    )  # 年化波动率
                else:
                    volatility = 0.0
            else:
                volatility = 0.0

            performance = {
                "etf_symbol": etf_symbol,
                "period_days": days,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "start_nav": earliest_nav["unit_nav"],
                "end_nav": latest_nav["unit_nav"],
                "return_rate": round(return_rate, 4),
                "volatility": round(volatility, 4),
                "data_points": len(nav_history),
            }

            logger.debug(f"ETF业绩计算完成: {etf_symbol}, 收益率: {return_rate:.2f}%")
            return performance

        except Exception as e:
            logger.error(f"计算ETF业绩失败: {e}")
            return {}

    def _standardize_etf_info(self, etf_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化ETF基础信息"""
        standardized = {
            "symbol": etf_data.get("symbol", "").upper(),
            "name": etf_data.get("name", ""),
            "market": etf_data.get("market", "SZ"),
        }

        # 复制其他字段
        for key, value in etf_data.items():
            if key not in standardized:
                standardized[key] = value

        return standardized

    def _standardize_holding_data(self, holding_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化成分股数据"""
        standardized = {
            "stock_symbol": holding_data.get("stock_symbol", "").upper(),
            "weight": self._parse_float(holding_data.get("weight")),
            "shares": self._parse_float(holding_data.get("shares")),
            "market_value": self._parse_float(holding_data.get("market_value")),
        }

        # 复制其他字段
        for key, value in holding_data.items():
            if key not in standardized:
                standardized[key] = value

        return standardized

    def _standardize_nav_data(self, nav_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化净值数据"""
        standardized = {
            "symbol": nav_data.get("symbol", "").upper(),
            "nav_date": nav_data.get("nav_date", ""),
            "unit_nav": self._parse_float(nav_data.get("unit_nav")),
            "accumulated_nav": self._parse_float(nav_data.get("accumulated_nav")),
            "estimated_nav": self._parse_float(nav_data.get("estimated_nav")),
            "premium_discount": self._parse_float(nav_data.get("premium_discount")),
        }

        # 复制其他字段
        for key, value in nav_data.items():
            if key not in standardized:
                standardized[key] = value

        return standardized

    def _parse_float(self, value: Any) -> Optional[float]:
        """解析浮点数"""
        if value is None or value == "":
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def get_manager_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        try:
            # ETF数量统计
            etf_count_sql = "SELECT COUNT(*) as total FROM ptrade_etf_info"
            etf_count = self.db_manager.fetchone(etf_count_sql)

            # 按类型统计
            type_stats_sql = """
            SELECT etf_type, COUNT(*) as count 
            FROM ptrade_etf_info 
            GROUP BY etf_type
            """
            type_stats = self.db_manager.fetchall(type_stats_sql)

            # 按市场统计
            market_stats_sql = """
            SELECT market, COUNT(*) as count 
            FROM ptrade_etf_info 
            GROUP BY market
            """
            market_stats = self.db_manager.fetchall(market_stats_sql)

            return {
                "total_etfs": etf_count["total"] if etf_count else 0,
                "etf_types": self.etf_types,
                "type_distribution": {
                    row["etf_type"]: row["count"] for row in type_stats
                },
                "market_distribution": {
                    row["market"]: row["count"] for row in market_stats
                },
                "supported_features": [
                    "ETF基础信息管理",
                    "ETF成分股跟踪",
                    "ETF净值历史",
                    "ETF业绩分析",
                ],
            }

        except Exception as e:
            logger.error(f"获取管理器统计失败: {e}")
            return {}
