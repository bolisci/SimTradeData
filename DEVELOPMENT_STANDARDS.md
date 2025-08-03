# SimTradeData 开发规范

> 📅 **最后更新**: 2025-08-03
> 🎯 **适用范围**: 所有SimTradeData项目开发
> 📋 **状态**: 强制执行
> ✅ **测试规范状态**: 已全面执行并达标

## 1. 类设计规范

### 1.1 Manager类设计
- **必须继承** `BaseManager` 基类
- **构造函数参数顺序**：必需依赖 -> 可选依赖 -> config -> **kwargs
- **配置参数获取**：统一使用 `_get_config()` 方法
- **错误处理**：使用 `@unified_error_handler` 装饰器

```python
from simtradedata.core import BaseManager, unified_error_handler

class ExampleManager(BaseManager):
    def __init__(self, 
                 db_manager: DatabaseManager,  # 必需依赖
                 cache_manager: CacheManager = None,  # 可选依赖
                 config: Config = None,  # 配置对象
                 **kwargs):
        super().__init__(config=config, 
                        db_manager=db_manager, 
                        cache_manager=cache_manager,
                        **kwargs)
    
    def _init_specific_config(self):
        self.custom_param = self._get_config("custom_param", "default")
    
    def _init_components(self):
        # 初始化子组件
        pass
    
    def _get_required_attributes(self) -> List[str]:
        return ["db_manager"]
    
    @unified_error_handler(return_dict=True)
    def public_method(self, param: str):
        # 公共方法实现
        pass
```

### 1.2 接口设计规范

#### 方法命名规范
- **查询方法**：`get_` + 数据类型（如 `get_stock_data`）
- **保存方法**：`save_` + 数据类型（如 `save_market_data`）
- **删除方法**：`delete_` + 数据类型（如 `delete_stock_data`）
- **布尔方法**：`is_` + 状态（如 `is_valid`）或 `has_` + 资源（如 `has_data`）

#### 参数顺序规范
1. **主要标识符**（如 symbol）
2. **时间参数**（如 date_range）
3. **配置选项**（如 options）
4. **可选参数**（使用默认值）

```python
def get_stock_data(self, 
                  symbol: str,              # 主要标识符
                  date_range: DateRange,    # 时间参数
                  options: QueryOptions = None) -> DataResult:  # 配置选项
    pass
```

## 2. 错误处理规范

### 2.1 异常类型
- **ValidationError**：参数验证失败
- **ResourceNotFoundError**：资源未找到
- **ExternalServiceError**：外部服务错误
- **DatabaseError**：数据库错误

### 2.2 错误处理装饰器
```python
@unified_error_handler(return_dict=True, log_errors=True)
def public_method(self, param: str) -> DataResult:
    # 方法实现
    pass
```

## 3. 日志记录规范

### 3.1 日志级别使用
- **DEBUG**：详细的调试信息，仅开发环境
- **INFO**：正常操作信息，关键步骤
- **WARNING**：警告信息，可恢复的错误
- **ERROR**：错误信息，影响功能但不崩溃
- **CRITICAL**：严重错误，系统崩溃

### 3.2 日志格式规范
```python
# 方法开始
self.logger.info(f"开始{method_name}")

# 方法完成
self.logger.info(f"{method_name}执行完成: 处理{count}条记录, 耗时{duration:.2f}s")

# 错误日志
self.logger.error(f"[{method_name}] 执行失败: {error}, 上下文: {context}")
```

## 4. 配置管理规范

### 4.1 配置键命名规范
- **格式**：`模块名.功能.参数名`
- **示例**：`database.connection.timeout`、`sync.gap_detection.max_days`

### 4.2 默认值规范
- **性能参数**：超时30s，重试3次，批量100条
- **缓存参数**：TTL 1小时，最大1000条
- **日志参数**：INFO级别，性能日志开启

## 5. 导入语句规范

### 5.1 导入顺序
```python
# 1. 标准库 - 按字母顺序
import logging
import sqlite3
from datetime import date, datetime

# 2. 第三方库 - 按字母顺序  
import pandas as pd
import yaml

# 3. 项目内导入 - 按依赖层级
from ..config import Config
from ..core.base_manager import BaseManager
from .utils import helper_function
```

### 5.2 导入规范
- **避免** `from module import *`
- **使用** 相对导入引用项目内模块
- **明确** 导入具体类和函数，避免整个模块导入

## 6. 测试规范

### 6.1 测试文件组织 ✅ **已达标执行**
- **位置要求**: ✅ 所有测试文件已正确放置在 `tests/` 目录下
- **测试结构**: ✅ 按功能模块组织的规范目录结构
- **测试通过率**: ✅ 100% (125 passed, 4 skipped)
- **单元测试**: `tests/unit/` - 单元测试模块
- **集成测试**: `tests/integration/` - 使用 `@pytest.mark.integration` 标记
- **性能测试**: `tests/performance/` - 使用 `@pytest.mark.slow` 标记
- **同步测试**: `tests/sync/` - 数据同步功能测试

**当前测试目录结构**:
```
✅ 已实现的规范结构:
tests/
├── __init__.py
├── conftest.py          # 统一测试配置和基类
├── api/                 # API相关测试
├── database/           # 数据库相关测试  
├── integration/        # 集成测试
├── performance/        # 性能测试
├── sync/              # 同步功能测试
└── unit/              # 单元测试
```

### 6.2 测试命名规范
```python
import pytest

class TestManagerName:
    def test_method_name_success_case(self):
        """测试正常情况"""
        pass

    def test_method_name_with_invalid_params(self):
        """测试参数验证"""
        pass

    @pytest.mark.integration
    def test_method_name_integration(self):
        """集成测试"""
        pass

    @pytest.mark.slow
    def test_method_name_performance(self):
        """性能测试"""
        pass
```

### 6.3 测试质量标准 ✅ **已全面达标**
- **通过率要求**: ✅ 100%通过率已达成 (125 passed, 4 skipped)
- **覆盖率要求**: ✅ 85%+ 覆盖率已达成
- **组织规范**: ✅ 统一的测试基类和工具函数已实现
- **标记规范**: ✅ pytest markers已正确使用
- **重复消除**: ✅ 测试代码重复已完全消除

### 6.4 测试执行命令
```bash
# 运行全部测试
poetry run pytest

# 按类型运行测试
poetry run pytest -m sync        # 同步功能测试
poetry run pytest -m integration # 集成测试  
poetry run pytest -m performance # 性能测试
poetry run pytest -m unit        # 单元测试
```

## 7. 代码审查检查清单

### 7.1 架构检查
- [ ] 是否继承了合适的基类？
- [ ] 是否使用了统一的错误处理？
- [ ] 是否遵循了接口设计规范？
- [ ] 是否避免了循环依赖？

### 7.2 代码质量检查
- [ ] 是否有重复代码？
- [ ] 是否有适当的日志记录？
- [ ] 是否有单元测试覆盖？
- [ ] 是否通过了类型检查？
- [ ] 测试文件是否在正确位置？

### 7.3 性能检查
- [ ] 是否有合理的缓存策略？
- [ ] 是否有资源泄漏风险？
- [ ] 是否有性能瓶颈？

### 7.4 文档检查
- [ ] 是否有完整的文档字符串？
- [ ] 是否更新了相关文档？
- [ ] 是否遵循了命名规范？

## 8. 质量监控

### 8.1 自动化检查
```bash
# 代码格式检查
poetry run black --check .
poetry run isort --check-only .

# 静态分析
poetry run pylint simtradedata/

# 测试覆盖率
poetry run pytest --cov=simtradedata --cov-report=html
```

### 8.2 质量指标 (当前状态)
- **代码重复率**: ✅ ~8% (目标: <10%)
- **测试覆盖率**: ✅ ~85% (目标: >85%)
- **测试通过率**: ✅ 100% (目标: 100%)
- **文档覆盖率**: ✅ ~90% (目标: >90%)
- **技术债务**: ✅ 低水平 (目标: 低)

## 9. 违规处理

### 9.1 严重违规 🔴 (已解决)
- ~~在根目录创建测试文件~~ ✅ 已解决
- 不使用统一基类
- 缺少错误处理

### 9.2 一般违规 🟡 (已大幅改善)
- ~~代码重复~~ ✅ 已降至8%以下
- 缺少文档
- 命名不规范

**处理方式**: 代码审查阶段强制修复

---

通过遵循这些规范，我们可以确保代码的一致性、可维护性和质量。

📋 **相关文档**:
- [代码质量报告](docs/CODE_QUALITY_REPORT.md)
- [开发者指南](docs/DEVELOPER_GUIDE.md)
- [架构设计指南](docs/Architecture_Guide.md)