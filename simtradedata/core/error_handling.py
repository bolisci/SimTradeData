"""
统一错误处理模块

提供标准化的错误处理装饰器和异常类。
"""

# 标准库导入
import logging
from enum import Enum
from functools import wraps
from typing import Callable, Dict, Union


class ErrorCode(Enum):
    """标准错误码"""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    PERMISSION_ERROR = "PERMISSION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ValidationError(Exception):
    """参数验证错误"""


class ResourceNotFoundError(Exception):
    """资源未找到错误"""


class ExternalServiceError(Exception):
    """外部服务错误"""


def unified_error_handler(
    return_dict: bool = True, log_errors: bool = True, reraise_on_critical: bool = False
):
    """统一错误处理装饰器

    Args:
        return_dict: 是否返回字典格式结果
        log_errors: 是否记录错误日志
        reraise_on_critical: 关键错误是否重新抛出
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(f"{func.__module__}.{func.__qualname__}")
            method_name = f"{func.__name__}"

            try:
                # 记录方法开始
                if hasattr(args[0], "enable_debug") and args[0].enable_debug:
                    logger.debug(
                        f"[{method_name}] starting execution : args={args[1:]}, kwargs={kwargs}"
                    )

                # 执行方法
                result = func(*args, **kwargs)

                # 返回结果
                if return_dict:
                    return {
                        "success": True,
                        "data": result,
                        "error_code": None,
                        "message": "执行成功",
                    }
                return result

            except ValidationError as e:
                if log_errors:
                    logger.warning(f"[{method_name}] parameter validation failed : {e}")
                error_result = _create_error_result(
                    ErrorCode.VALIDATION_ERROR, str(e), return_dict
                )
                if reraise_on_critical:
                    raise
                return error_result

            except ResourceNotFoundError as e:
                if log_errors:
                    logger.info(f"[{method_name}] resource not found : {e}")
                error_result = _create_error_result(
                    ErrorCode.RESOURCE_NOT_FOUND, str(e), return_dict
                )
                if reraise_on_critical:
                    raise
                return error_result

            except ExternalServiceError as e:
                if log_errors:
                    logger.error(f"[{method_name}] external service error : {e}")
                error_result = _create_error_result(
                    ErrorCode.EXTERNAL_SERVICE_ERROR, str(e), return_dict
                )
                if reraise_on_critical:
                    raise
                return error_result

            except Exception as e:
                if log_errors:
                    logger.error(
                        f"[{method_name}] unexpected error : {e}", exc_info=True
                    )
                error_result = _create_error_result(
                    ErrorCode.INTERNAL_ERROR, "内部处理错误", return_dict
                )
                if reraise_on_critical:
                    raise
                return error_result

        return wrapper

    return decorator


def _create_error_result(
    error_code: ErrorCode, message: str, return_dict: bool
) -> Union[Dict, None]:
    """创建错误结果"""
    if return_dict:
        return {
            "success": False,
            "data": None,
            "error_code": error_code.value,
            "message": message,
        }
    return None
