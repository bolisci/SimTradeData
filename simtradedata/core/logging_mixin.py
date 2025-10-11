"""
统一日志记录混入类

提供标准化的日志记录功能。
"""

import logging
import time
from functools import wraps
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    pass


class LoggingMixin:
    """统一日志记录混入类"""

    # 类型标注所需的属性声明
    enable_debug: bool
    enable_performance_log: bool
    logger: logging.Logger

    def _init_logger(self) -> logging.Logger:
        """初始化日志器"""
        return logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _log_method_start(self, method_name: str, **params):
        """记录方法开始执行"""
        if hasattr(self, "enable_debug") and self.enable_debug:
            self.logger.debug(f"[{method_name}] starting execution : {params}")
        else:
            self.logger.info(f"starting {method_name}")

    def _log_method_end(
        self, method_name: str, duration: Optional[float] = None, **result_info
    ):
        """记录方法执行完成"""
        if (
            duration is not None
            and hasattr(self, "enable_performance_log")
            and self.enable_performance_log
        ):
            self.logger.info(
                f"[{method_name}] executing completed : elapsed {duration:.3f}s, {result_info}"
            )
        else:
            self.logger.info(f"{method_name} executing completed : {result_info}")

    def _log_error(self, method_name: str, error: Exception, **context):
        """记录错误信息"""
        exc_info = hasattr(self, "enable_debug") and self.enable_debug
        self.logger.error(
            f"[{method_name}] executing failed : {type(error).__name__}: {error},"
            f"上下文: {context}",
            exc_info=exc_info,
        )

    def _log_warning(self, method_name: str, message: str, **context):
        """记录警告信息"""
        self.logger.warning(f"[{method_name}] {message}, context : {context}")

    def _log_performance(self, operation: str, duration: float, **metrics):
        """记录性能指标"""
        if hasattr(self, "enable_performance_log") and self.enable_performance_log:
            self.logger.info(
                f"[ performance ] {operation}: elapsed {duration:.3f}s, indicators : {metrics}"
            )


def log_method_execution(log_start: bool = True, log_end: bool = True):
    """方法执行日志装饰器"""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            method_name = func.__name__
            start_time = time.time()

            # 记录开始
            if log_start and hasattr(self, "_log_method_start"):
                self._log_method_start(method_name, args=args, kwargs=kwargs)

            try:
                result = func(self, *args, **kwargs)

                # 记录结束
                if log_end and hasattr(self, "_log_method_end"):
                    duration = time.time() - start_time
                    result_info = {"result_type": type(result).__name__}
                    if hasattr(result, "__len__"):
                        result_info["result_size"] = str(len(result))  # 转换为字符串
                    self._log_method_end(method_name, duration, **result_info)

                return result

            except Exception as e:
                if hasattr(self, "_log_error"):
                    self._log_error(method_name, e, args=args, kwargs=kwargs)
                raise

        return wrapper

    return decorator
