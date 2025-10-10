# SimTradeData 示例代码

本目录包含 SimTradeData 各核心功能的演示示例。

## 📋 示例列表

| 文件 | 功能演示 | 说明 |
|------|---------|------|
| `api_router_demo.py` | API路由器 | 查询构建器、结果格式化、缓存、路由器 |
| `interfaces_demo.py` | 用户接口层 | PTrade适配器、REST API、API网关 |
| `multi_market_demo.py` | 多市场支持 | A股、港股、美股数据处理 |
| `performance_demo.py` | 性能优化 | 缓存、并发、查询优化 |

## 🚀 运行示例

### 前提条件

```bash
# 确保已安装依赖
poetry install

# 初始化数据库（如果还没有）
poetry run python scripts/init_database.py --db-path data/simtradedata.db
```

### 运行单个示例

```bash
# API路由器演示
poetry run python examples/api_router_demo.py

# 用户接口层演示
poetry run python examples/interfaces_demo.py

# 多市场支持演示
poetry run python examples/multi_market_demo.py

# 性能优化演示
poetry run python examples/performance_demo.py
```

## 📖 示例说明

### 1. API路由器演示 (api_router_demo.py)

演示 SimTradeData 核心 API 路由器的各项功能：

- **查询构建器**: 展示如何构建历史数据、快照数据、财务数据查询
- **结果格式化**: 演示 DataFrame、JSON、Dict 等多种输出格式
- **查询缓存**: 展示缓存机制的使用和统计
- **API路由器**: 统一的查询接口和性能监控

**适用场景**: 了解如何使用 API 查询各类金融数据

### 2. 用户接口层演示 (interfaces_demo.py)

演示多种用户接口实现：

- **PTrade API适配器**: 完全兼容 PTrade 原生 API
- **RESTful API服务器**: 标准 HTTP API 接口
- **API网关**: 统一入口、限流、认证、负载均衡

**适用场景**: 了解如何对外提供数据服务

### 3. 多市场支持演示 (multi_market_demo.py)

演示跨市场数据处理：

- **A股市场**: 深圳、上海市场数据
- **港股市场**: 香港市场数据
- **美股市场**: 美国市场数据
- **市场差异处理**: 不同市场的特殊处理逻辑

**适用场景**: 了解如何处理多市场数据

### 4. 性能优化演示 (performance_demo.py)

演示各种性能优化技术：

- **缓存机制**: 多级缓存策略
- **并发处理**: 并行查询和数据处理
- **查询优化**: SQL 优化和索引使用
- **性能监控**: 性能指标收集和分析

**适用场景**: 了解如何优化查询性能

## 💡 使用提示

### 示例代码特点

1. **演示性质**: 所有示例使用 Mock 对象，无需实际数据即可运行
2. **功能完整**: 展示各组件的核心功能和使用方法
3. **详细注释**: 代码包含详细的中文注释和说明
4. **独立运行**: 每个示例都可以独立运行

### 学习路径建议

1. **新手入门**: 从 `api_router_demo.py` 开始，了解基本查询
2. **进阶使用**: 学习 `interfaces_demo.py`，了解如何提供服务
3. **多市场场景**: 运行 `multi_market_demo.py`，处理跨市场数据
4. **性能优化**: 学习 `performance_demo.py`，提升系统性能

### 实际应用

示例代码提供了基本框架，实际使用时需要：

1. 替换 Mock 对象为真实的数据库连接
2. 配置实际的数据源（BaoStock、Mootdx、QStock）
3. 根据需求调整查询参数和配置
4. 添加错误处理和日志记录

## 📚 相关文档

- [API参考文档](../docs/API_REFERENCE.md) - 完整的API接口文档
- [开发者指南](../docs/DEVELOPER_GUIDE.md) - 开发者扩展开发指南
- [架构指南](../docs/Architecture_Guide.md) - 系统架构和设计文档
- [CLI使用指南](../docs/CLI_USAGE_GUIDE.md) - 命令行工具使用说明

## 🔧 自定义示例

可以基于现有示例创建自己的演示代码：

```python
#!/usr/bin/env python3
"""
自定义示例
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simtradedata.api import APIRouter
from simtradedata.database import DatabaseManager
from simtradedata.config import Config

def my_custom_demo():
    """我的自定义演示"""
    config = Config()
    db_manager = DatabaseManager("data/simtradedata.db")
    api_router = APIRouter(db_manager, config)

    # 你的代码...

if __name__ == "__main__":
    my_custom_demo()
```

## 🆘 获取帮助

如果在运行示例时遇到问题：

1. 检查是否已正确安装依赖: `poetry install`
2. 确认数据库已初始化: `poetry run python scripts/init_database.py`
3. 查看相关文档了解详细 API 用法
4. 在 GitHub 提交 Issue 寻求帮助

---

**最后更新**: 2025-10-10
**维护者**: SimTradeData 团队
