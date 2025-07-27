"""
RESTful API服务器

提供标准的RESTful API接口，支持HTTP/HTTPS访问。
"""

import logging
from datetime import datetime
from typing import Any, Dict

try:
    from flask import Flask, Response, jsonify, request
    from flask_cors import CORS

    FLASK_AVAILABLE = True
except ImportError:
    # 如果没有安装Flask，使用模拟版本
    Flask = None
    request = None
    jsonify = None
    Response = None
    CORS = None
    FLASK_AVAILABLE = False
import threading

from ..api import APIRouter
from ..config import Config
from ..database import DatabaseManager

logger = logging.getLogger(__name__)


class RESTAPIServer:
    """RESTful API服务器"""

    def __init__(
        self, db_manager: DatabaseManager, api_router: APIRouter, config: Config = None
    ):
        """
        初始化RESTful API服务器

        Args:
            db_manager: 数据库管理器
            api_router: API路由器
            config: 配置对象
        """
        self.db_manager = db_manager
        self.api_router = api_router
        self.config = config or Config()

        # 服务器配置
        self.host = self.config.get("rest_api.host", "0.0.0.0")
        self.port = self.config.get("rest_api.port", 8080)
        self.debug = self.config.get("rest_api.debug", False)
        self.enable_cors = self.config.get("rest_api.enable_cors", True)

        # 检查Flask是否可用
        if not FLASK_AVAILABLE:
            logger.warning("Flask不可用，REST API服务器将无法启动")
            self.app = None
        else:
            # 创建Flask应用
            self.app = Flask(__name__)

            # 启用CORS
            if self.enable_cors:
                CORS(self.app)

            # 注册路由
            self._register_routes()

        # 服务器状态
        self.is_running = False
        self.server_thread = None

        logger.info("RESTful API服务器初始化完成")

    def _register_routes(self):
        """注册API路由"""
        if not FLASK_AVAILABLE or not self.app:
            return

        @self.app.route("/api/v1/health", methods=["GET"])
        def health_check():
            """健康检查"""
            return jsonify(
                {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0.0",
                }
            )

        @self.app.route("/api/v1/stocks", methods=["GET"])
        def get_stocks():
            """获取股票列表"""
            try:
                market = request.args.get("market")
                status = request.args.get("status", "active")
                limit = int(request.args.get("limit", 1000))

                query_params = {"data_type": "stock_list", "format": "json"}

                if market:
                    query_params["market"] = market
                if status:
                    query_params["status"] = status

                result = self.api_router.query(query_params)

                # 限制返回数量
                if isinstance(result, list) and len(result) > limit:
                    result = result[:limit]

                return jsonify(
                    {
                        "success": True,
                        "data": result,
                        "count": len(result) if isinstance(result, list) else 0,
                    }
                )

            except Exception as e:
                logger.error(f"获取股票列表失败: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/v1/stocks/<symbol>/price", methods=["GET"])
        def get_stock_price(symbol):
            """获取股票价格"""
            try:
                start_date = request.args.get("start_date")
                end_date = request.args.get("end_date")
                frequency = request.args.get("frequency", "1d")

                query_params = {
                    "data_type": "price_data",
                    "symbols": [symbol],
                    "frequency": frequency,
                    "format": "json",
                }

                if start_date:
                    query_params["start_date"] = start_date
                if end_date:
                    query_params["end_date"] = end_date

                result = self.api_router.query(query_params)

                return jsonify({"success": True, "symbol": symbol, "data": result})

            except Exception as e:
                logger.error(f"获取股票价格失败: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/v1/stocks/<symbol>/fundamentals", methods=["GET"])
        def get_stock_fundamentals(symbol):
            """获取股票基本面"""
            try:
                fields = request.args.get("fields")
                if fields:
                    fields = fields.split(",")

                query_params = {
                    "data_type": "fundamentals",
                    "symbols": [symbol],
                    "format": "json",
                }

                if fields:
                    query_params["fields"] = fields

                result = self.api_router.query(query_params)

                return jsonify({"success": True, "symbol": symbol, "data": result})

            except Exception as e:
                logger.error(f"获取基本面数据失败: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/v1/stocks/<symbol>/industry", methods=["GET"])
        def get_stock_industry(symbol):
            """获取股票行业分类"""
            try:
                standard = request.args.get("standard", "sw")

                query_params = {
                    "data_type": "industry_classification",
                    "symbols": [symbol],
                    "standard": standard,
                    "format": "json",
                }

                result = self.api_router.query(query_params)

                return jsonify({"success": True, "symbol": symbol, "data": result})

            except Exception as e:
                logger.error(f"获取行业分类失败: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/v1/stocks/<symbol>/indicators", methods=["GET"])
        def get_stock_indicators(symbol):
            """获取股票技术指标"""
            try:
                indicators = request.args.get("indicators", "ma,rsi")
                start_date = request.args.get("start_date")
                end_date = request.args.get("end_date")

                if indicators:
                    indicators = indicators.split(",")

                query_params = {
                    "data_type": "technical_indicators",
                    "symbol": symbol,
                    "indicators": indicators,
                    "format": "json",
                }

                if start_date:
                    query_params["start_date"] = start_date
                if end_date:
                    query_params["end_date"] = end_date

                result = self.api_router.query(query_params)

                return jsonify({"success": True, "symbol": symbol, "data": result})

            except Exception as e:
                logger.error(f"获取技术指标失败: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/v1/etf/<symbol>/holdings", methods=["GET"])
        def get_etf_holdings(symbol):
            """获取ETF成分股"""
            try:
                date = request.args.get("date")

                query_params = {
                    "data_type": "etf_holdings",
                    "etf_symbol": symbol,
                    "format": "json",
                }

                if date:
                    query_params["date"] = date

                result = self.api_router.query(query_params)

                return jsonify({"success": True, "etf_symbol": symbol, "data": result})

            except Exception as e:
                logger.error(f"获取ETF成分股失败: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/v1/sectors", methods=["GET"])
        def get_sectors():
            """获取板块列表"""
            try:
                sector_type = request.args.get("type", "industry")

                query_params = {
                    "data_type": "sector_list",
                    "sector_type": sector_type,
                    "format": "json",
                }

                result = self.api_router.query(query_params)

                return jsonify({"success": True, "data": result})

            except Exception as e:
                logger.error(f"获取板块列表失败: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/v1/sectors/<sector_code>/constituents", methods=["GET"])
        def get_sector_constituents(sector_code):
            """获取板块成分股"""
            try:
                date = request.args.get("date")

                query_params = {
                    "data_type": "sector_constituents",
                    "sector_code": sector_code,
                    "format": "json",
                }

                if date:
                    query_params["date"] = date

                result = self.api_router.query(query_params)

                return jsonify(
                    {"success": True, "sector_code": sector_code, "data": result}
                )

            except Exception as e:
                logger.error(f"获取板块成分股失败: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/v1/market/stats", methods=["GET"])
        def get_market_stats():
            """获取市场统计"""
            try:
                market = request.args.get("market")
                days = int(request.args.get("days", 30))

                query_params = {
                    "data_type": "market_statistics",
                    "days": days,
                    "format": "json",
                }

                if market:
                    query_params["market"] = market

                result = self.api_router.query(query_params)

                return jsonify({"success": True, "data": result})

            except Exception as e:
                logger.error(f"获取市场统计失败: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.errorhandler(404)
        def not_found(error):
            """404错误处理"""
            return jsonify({"success": False, "error": "API endpoint not found"}), 404

        @self.app.errorhandler(500)
        def internal_error(error):
            """500错误处理"""
            return jsonify({"success": False, "error": "Internal server error"}), 500

    def start(self, threaded: bool = True):
        """启动服务器"""
        try:
            if not FLASK_AVAILABLE or not self.app:
                logger.error("Flask不可用，无法启动REST API服务器")
                return

            if self.is_running:
                logger.warning("服务器已在运行")
                return

            if threaded:
                # 在新线程中启动服务器
                self.server_thread = threading.Thread(
                    target=self._run_server, daemon=True
                )
                self.server_thread.start()
            else:
                # 在当前线程中启动服务器
                self._run_server()

            self.is_running = True
            logger.info(f"RESTful API服务器启动成功: http://{self.host}:{self.port}")

        except Exception as e:
            logger.error(f"启动RESTful API服务器失败: {e}")
            raise

    def stop(self):
        """停止服务器"""
        try:
            if not self.is_running:
                logger.warning("服务器未在运行")
                return

            self.is_running = False

            if self.server_thread and self.server_thread.is_alive():
                # 等待服务器线程结束
                self.server_thread.join(timeout=5)

            logger.info("RESTful API服务器已停止")

        except Exception as e:
            logger.error(f"停止RESTful API服务器失败: {e}")

    def _run_server(self):
        """运行服务器"""
        try:
            if not FLASK_AVAILABLE or not self.app:
                logger.error("Flask不可用，无法运行服务器")
                self.is_running = False
                return

            self.app.run(
                host=self.host,
                port=self.port,
                debug=self.debug,
                threaded=True,
                use_reloader=False,
            )
        except Exception as e:
            logger.error(f"服务器运行失败: {e}")
            self.is_running = False

    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        return {
            "server_name": "SimTradeData REST API",
            "version": "1.0.0",
            "host": self.host,
            "port": self.port,
            "is_running": self.is_running,
            "debug": self.debug,
            "enable_cors": self.enable_cors,
            "endpoints": [
                "GET /api/v1/health",
                "GET /api/v1/stocks",
                "GET /api/v1/stocks/{symbol}/price",
                "GET /api/v1/stocks/{symbol}/fundamentals",
                "GET /api/v1/stocks/{symbol}/industry",
                "GET /api/v1/stocks/{symbol}/indicators",
                "GET /api/v1/etf/{symbol}/holdings",
                "GET /api/v1/sectors",
                "GET /api/v1/sectors/{sector_code}/constituents",
                "GET /api/v1/market/stats",
            ],
        }
