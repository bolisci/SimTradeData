"""
数据缺口检测器

负责检测数据缺口，分析缺口原因，提供自动修复建议。
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from ..config import Config
from ..database import DatabaseManager

logger = logging.getLogger(__name__)


class GapDetector:
    """数据缺口检测器"""

    def __init__(self, db_manager: DatabaseManager, config: Config = None):
        """
        初始化缺口检测器

        Args:
            db_manager: 数据库管理器
            config: 配置对象
        """
        self.db_manager = db_manager
        self.config = config or Config()

        # 检测配置
        self.max_gap_days = self.config.get("gap_detection.max_gap_days", 5)
        self.min_data_quality = self.config.get("gap_detection.min_data_quality", 60)
        self.check_frequencies = self.config.get("gap_detection.frequencies", ["1d"])
        self.exclude_weekends = self.config.get("gap_detection.exclude_weekends", True)

        logger.info("数据缺口检测器初始化完成")

    def detect_all_gaps(
        self,
        start_date: date = None,
        end_date: date = None,
        symbols: List[str] = None,
        frequencies: List[str] = None,
    ) -> Dict[str, Any]:
        """
        检测所有数据缺口

        Args:
            start_date: 开始日期，默认为30天前
            end_date: 结束日期，默认为今天
            symbols: 股票代码列表，默认为所有活跃股票
            frequencies: 频率列表，默认为配置中的频率

        Returns:
            Dict[str, Any]: 缺口检测结果
        """
        if start_date is None:
            start_date = datetime.now().date() - timedelta(days=30)

        if end_date is None:
            end_date = datetime.now().date()

        if frequencies is None:
            frequencies = self.check_frequencies

        try:
            logger.info(
                f"开始缺口检测: {start_date} 到 {end_date}, 频率: {frequencies}"
            )

            # 获取需要检测的股票列表
            if symbols is None:
                symbols = self._get_active_symbols()

            detection_result = {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "total_symbols": len(symbols),
                "frequencies": frequencies,
                "gaps_by_frequency": {},
                "summary": {
                    "total_gaps": 0,
                    "symbols_with_gaps": 0,
                    "gap_types": defaultdict(int),
                },
            }

            # 按频率检测缺口
            for frequency in frequencies:
                freq_gaps = self._detect_frequency_gaps(
                    symbols, start_date, end_date, frequency
                )
                detection_result["gaps_by_frequency"][frequency] = freq_gaps

                # 更新汇总统计
                detection_result["summary"]["total_gaps"] += len(freq_gaps["gaps"])
                detection_result["summary"]["symbols_with_gaps"] += len(
                    freq_gaps["symbols_with_gaps"]
                )

                for gap in freq_gaps["gaps"]:
                    detection_result["summary"]["gap_types"][gap["gap_type"]] += 1

            logger.info(
                f"缺口检测完成: 总缺口={detection_result['summary']['total_gaps']}, "
                f"涉及股票={detection_result['summary']['symbols_with_gaps']}"
            )

            return detection_result

        except Exception as e:
            logger.error(f"缺口检测失败: {e}")
            raise

    def detect_symbol_gaps(
        self, symbol: str, start_date: date, end_date: date, frequency: str = "1d"
    ) -> List[Dict[str, Any]]:
        """
        检测单个股票的数据缺口

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            frequency: 频率

        Returns:
            List[Dict[str, Any]]: 缺口列表
        """
        logger.debug(f"检测股票缺口: {symbol} {start_date} 到 {end_date} {frequency}")

        # 获取交易日历
        trading_days = self._get_trading_days(start_date, end_date)

        # 获取已有数据日期
        existing_dates = self._get_existing_dates(
            symbol, start_date, end_date, frequency
        )

        # 只检测日期缺口，删除过度的质量和异常检测
        gaps = self._detect_date_gaps(symbol, trading_days, existing_dates, frequency)

        logger.debug(f"股票缺口检测完成: {symbol}, 发现 {len(gaps)} 个缺口")
        return gaps

    def _detect_frequency_gaps(
        self, symbols: List[str], start_date: date, end_date: date, frequency: str
    ) -> Dict[str, Any]:
        """检测特定频率的缺口"""
        logger.info(f"检测频率缺口: {frequency}, 股票数量: {len(symbols)}")

        result = {
            "frequency": frequency,
            "total_symbols": len(symbols),
            "symbols_with_gaps": set(),
            "gaps": [],
        }

        for symbol in symbols:
            try:
                symbol_gaps = self.detect_symbol_gaps(
                    symbol, start_date, end_date, frequency
                )

                if symbol_gaps:
                    result["symbols_with_gaps"].add(symbol)
                    result["gaps"].extend(symbol_gaps)

            except Exception as e:
                logger.error(f"检测股票缺口失败 {symbol}: {e}")

        # 转换set为list以便JSON序列化
        result["symbols_with_gaps"] = list(result["symbols_with_gaps"])

        return result

    def _detect_date_gaps(
        self,
        symbol: str,
        trading_days: List[date],
        existing_dates: List[date],
        frequency: str,
    ) -> List[Dict[str, Any]]:
        """检测日期缺口"""
        gaps = []

        # 转换为集合以便快速查找
        existing_set = set(existing_dates)

        # 查找缺失的交易日
        missing_dates = []
        for trading_day in trading_days:
            if trading_day not in existing_set:
                missing_dates.append(trading_day)

        if not missing_dates:
            return gaps

        # 将连续的缺失日期合并为缺口
        current_gap_start = None
        current_gap_end = None

        for missing_date in sorted(missing_dates):
            if current_gap_start is None:
                current_gap_start = missing_date
                current_gap_end = missing_date
            elif missing_date == current_gap_end + timedelta(days=1):
                # 连续日期，扩展当前缺口
                current_gap_end = missing_date
            else:
                # 非连续日期，结束当前缺口并开始新缺口
                gaps.append(
                    {
                        "symbol": symbol,
                        "frequency": frequency,
                        "gap_type": "date_missing",
                        "start_date": str(current_gap_start),
                        "end_date": str(current_gap_end),
                        "gap_days": (current_gap_end - current_gap_start).days + 1,
                        "severity": self._calculate_gap_severity(
                            current_gap_start, current_gap_end
                        ),
                        "description": f"缺失交易日数据: {current_gap_start} 到 {current_gap_end}",
                    }
                )

                current_gap_start = missing_date
                current_gap_end = missing_date

        # 添加最后一个缺口
        if current_gap_start is not None:
            gaps.append(
                {
                    "symbol": symbol,
                    "frequency": frequency,
                    "gap_type": "date_missing",
                    "start_date": str(current_gap_start),
                    "end_date": str(current_gap_end),
                    "gap_days": (current_gap_end - current_gap_start).days + 1,
                    "severity": self._calculate_gap_severity(
                        current_gap_start, current_gap_end
                    ),
                    "description": f"缺失交易日数据: {current_gap_start} 到 {current_gap_end}",
                }
            )

        return gaps

    def _get_trading_days(self, start_date: date, end_date: date) -> List[date]:
        """获取交易日列表"""
        # 直接从数据库查询交易日历
        sql = """
        SELECT date FROM trading_calendar
        WHERE date >= ? AND date <= ?
        AND market = 'CN' AND is_trading = 1
        ORDER BY date
        """

        results = self.db_manager.fetchall(sql, (str(start_date), str(end_date)))

        if results:
            trading_days = [
                datetime.strptime(row["date"], "%Y-%m-%d").date() for row in results
            ]
            logger.debug(f"从数据库获取到 {len(trading_days)} 个交易日")
            return trading_days
        else:
            logger.warning(f"数据库中无交易日历数据: {start_date} 到 {end_date}")
            return []

    def _get_existing_dates(
        self, symbol: str, start_date: date, end_date: date, frequency: str
    ) -> List[date]:
        """获取已有数据日期"""
        try:
            sql = """
            SELECT DISTINCT date FROM market_data
            WHERE symbol = ? AND frequency = ?
            AND date >= ? AND date <= ?
            ORDER BY date
            """

            results = self.db_manager.fetchall(
                sql, (symbol, frequency, str(start_date), str(end_date))
            )

            return [
                datetime.strptime(row["date"], "%Y-%m-%d").date() for row in results
            ]

        except Exception as e:
            logger.error(f"获取已有数据日期失败 {symbol}: {e}")
            return []

    def _get_active_symbols(self) -> List[str]:
        """获取活跃股票列表"""
        try:
            sql = """
            SELECT symbol FROM ptrade_stock_info 
            WHERE status = 'active' 
            ORDER BY symbol
            """
            results = self.db_manager.fetchall(sql)

            if results:
                return [row["symbol"] for row in results]
            else:
                logger.warning("数据库中无活跃股票")
                return []

        except Exception as e:
            logger.error(f"获取活跃股票列表失败: {e}")
            return []

    def _calculate_gap_severity(self, start_date: date, end_date: date) -> str:
        """计算缺口严重程度"""
        gap_days = (end_date - start_date).days + 1

        if gap_days <= 1:
            return "low"
        elif gap_days <= 3:
            return "medium"
        elif gap_days <= 7:
            return "high"
        else:
            return "critical"

    def generate_gap_report(self, detection_result: Dict[str, Any]) -> str:
        """生成缺口检测报告"""
        try:
            report_lines = []

            # 报告头部
            report_lines.append("=" * 60)
            report_lines.append("数据缺口检测报告")
            report_lines.append("=" * 60)
            report_lines.append(
                f"检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            report_lines.append(
                f"检测范围: {detection_result['start_date']} 到 {detection_result['end_date']}"
            )
            report_lines.append(f"检测股票: {detection_result['total_symbols']} 只")
            report_lines.append(
                f"检测频率: {', '.join(detection_result['frequencies'])}"
            )
            report_lines.append("")

            # 汇总统计
            summary = detection_result["summary"]
            report_lines.append("汇总统计:")
            report_lines.append(f"  总缺口数: {summary['total_gaps']}")
            report_lines.append(f"  涉及股票: {summary['symbols_with_gaps']}")
            report_lines.append("")

            # 缺口类型统计
            if summary["gap_types"]:
                report_lines.append("缺口类型分布:")
                for gap_type, count in summary["gap_types"].items():
                    report_lines.append(f"  {gap_type}: {count}")
                report_lines.append("")

            # 按频率详细统计
            for frequency, freq_data in detection_result["gaps_by_frequency"].items():
                report_lines.append(f"频率 {frequency} 详细信息:")
                report_lines.append(
                    f"  涉及股票: {len(freq_data['symbols_with_gaps'])}"
                )
                report_lines.append(f"  缺口数量: {len(freq_data['gaps'])}")

                # 按严重程度统计
                severity_count = defaultdict(int)
                for gap in freq_data["gaps"]:
                    severity_count[gap["severity"]] += 1

                if severity_count:
                    report_lines.append("  严重程度分布:")
                    for severity, count in severity_count.items():
                        report_lines.append(f"    {severity}: {count}")

                report_lines.append("")

            # 建议修复的缺口
            critical_gaps = []
            for freq_data in detection_result["gaps_by_frequency"].values():
                for gap in freq_data["gaps"]:
                    if gap["severity"] in ["high", "critical"]:
                        critical_gaps.append(gap)

            if critical_gaps:
                report_lines.append("建议优先修复的缺口:")
                for gap in critical_gaps[:10]:  # 只显示前10个
                    report_lines.append(
                        f"  {gap['symbol']} {gap['start_date']} "
                        f"({gap['gap_type']}, {gap['severity']})"
                    )

                if len(critical_gaps) > 10:
                    report_lines.append(f"  ... 还有 {len(critical_gaps) - 10} 个缺口")

            return "\n".join(report_lines)

        except Exception as e:
            logger.error(f"生成缺口报告失败: {e}")
            return f"报告生成失败: {e}"
