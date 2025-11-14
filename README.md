# SimTradeData - 量化交易数据支持库

> 🎯 **为 SimTradeLab 提供兼容的 H5 格式数据** | 📊 **多数据源融合** | 🚀 **开源免费**

**SimTradeData** 是 [SimTradeLab](https://github.com/kay_ou/SimTradeLab) 的配套数据库,通过整合 BaoStock、QStock、Yahoo Finance 等开源数据源,生成与 SimTradeLab 兼容的 HDF5 格式数据文件,为量化策略回测提供完整的历史数据支持。

## 🎯 项目目标

SimTradeLab 原本使用 PTrade(掘金量化)的数据格式,但 PTrade 为商业数据源。本项目旨在:

1. **数据格式兼容**: 生成与 PTrade 数据完全兼容的 HDF5 文件格式
2. **开源数据整合**: 整合 BaoStock、QStock、Yahoo Finance 等免费开源数据源
3. **零成本使用**: 让用户无需付费即可使用 SimTradeLab 进行量化回测
4. **数据完整性**: 尽可能提供完整的行情、财务、估值等多维度数据

## 📦 数据文件说明

本项目生成以下 HDF5 格式数据文件,完全兼容 SimTradeLab:

| 文件名 | 大小 | 说明 | 数据内容 |
|--------|------|------|----------|
| `ptrade_data.h5` | ~157 MB | 主数据文件 | 股票行情(OHLCV)、基准指数、除权除息、股票元数据 |
| `ptrade_fundamentals.h5` | ~192 MB | 基本面数据 | 季度财务指标(23项)、每日估值指标(PE/PB/PS等) |
| `ptrade_adj_pre.h5` | ~85 MB | 复权因子 | 每只股票的历史复权因子序列 |
| `ptrade_dividend_cache.h5` | ~0.5 MB | 分红缓存 | 股票分红派息记录 |

### 数据结构详情

详细的数据结构分析请参考: [H5_DATA_STRUCTURE.md](docs/H5_DATA_STRUCTURE.md)

## 🚀 快速开始

### 1. 安装依赖

```bash
# 克隆项目
git clone https://github.com/kay-ou/SimTradeData.git
cd SimTradeData

# 安装依赖(使用 Poetry)
poetry install

# 激活虚拟环境
poetry shell
```

### 2. 生成 HDF5 数据文件

```bash
# 【推荐】下载全部数据(K线使用Mootdx加速,其他用BaoStock)
poetry run python -m simtradedata.cli fetch-all \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --market-source mootdx

# 跳过基本面数据,下载更快(约6小时完成5600股)
poetry run python -m simtradedata.cli fetch-all \
  --start-date 2024-01-01 \
  --skip-fundamentals \
  --market-source mootdx

# 【第二步】单独补充基本面数据(约15小时)
poetry run python -m simtradedata.cli fetch-all \
  --start-date 2024-01-01 \
  --only-fundamentals

# 下载指定股票
poetry run python -m simtradedata.cli fetch \
  "600000.SH,000001.SZ,000002.SZ" \
  --start-date 2024-01-01 \
  --market-source mootdx

# 增量更新已有数据(最近30天)
poetry run python -m simtradedata.cli update --days 30

# 下载基准指数数据
poetry run python -m simtradedata.cli fetch-benchmark \
  --index-code 000001.SH \
  --start-date 2024-01-01

# 验证数据完整性
poetry run python -m simtradedata.cli validate --output-dir data

# 查看数据统计
poetry run python -m simtradedata.cli stats --output-dir data
```

### 3. 在 SimTradeLab 中使用

生成的 HDF5 文件可直接放入 SimTradeLab 的数据目录使用:

```bash
# 复制生成的文件到 SimTradeLab 数据目录
cp data/*.h5 /path/to/SimTradeLab/data/
```

SimTradeLab 会自动识别并加载这些数据文件。

## 📊 数据源说明

### 支持的数据源

| 数据源 | 类型 | 覆盖范围 | 优势 | 限制 |
|--------|------|----------|------|------|
| **Mootdx** | 免费 | A股全市场 | **K线下载快**(3.3倍于BaoStock) | 仅提供K线,无估值/基本面 |
| **BaoStock** | 免费 | A股全市场 | 数据完整,接口稳定 | 单线程下载,速度较慢 |
| **QStock** | 免费 | A股全市场 | 开源,更新及时 | 依赖问题(计划中) |
| **Yahoo Finance** | 免费 | 全球市场 | 覆盖港股/美股 | A股数据较少(计划中) |

### 混合数据源策略 🚀

**默认使用混合数据源以获得最佳性能:**

- **K线数据(OHLCV)**: Mootdx (快,~1-2秒/股,**推荐**)
- **估值数据(PE/PB/PS)**: BaoStock (~2-3秒/股)
- **复权因子**: BaoStock (~1秒/股)
- **分红数据**: BaoStock (~1秒/股)
- **基本面数据**: BaoStock (~10-15秒/股)

**性能对比:**

| 数据源组合 | 每股耗时 | 5600股总耗时 | 说明 |
|----------|---------|-------------|------|
| 纯BaoStock | ~20秒 | ~31小时 | 全部数据 |
| **Mootdx+BaoStock** | **~15秒** | **~23小时** | 全部数据(推荐) |
| Mootdx+BaoStock(跳过基本面) | ~4秒 | ~6小时 | 快速下载K线+估值 |

### 数据映射方案

本项目建立了完整的数据源字段到 PTrade 格式的映射关系:

- **行情数据**: Mootdx `bars()` / BaoStock `query_history_k_data_plus()` → `ptrade_data.h5/stock_data`
- **财务数据**: BaoStock 季频财务指标 → `ptrade_fundamentals.h5/fundamentals`
- **估值数据**: BaoStock `query_history_k_data_plus()` → `ptrade_fundamentals.h5/valuation`
- **复权因子**: BaoStock `query_adjust_factor()` → `ptrade_adj_pre.h5`
- **除权除息**: BaoStock `query_dividend_data()` → `ptrade_data.h5/exrights`

详细映射关系请参考: [DATA_MAPPING.md](docs/DATA_MAPPING.md)

## 📚 文档

| 文档 | 说明 | 状态 |
|------|------|------|
| [H5_DATA_STRUCTURE.md](docs/H5_DATA_STRUCTURE.md) | HDF5 文件详细数据结构 | ✅ 已完成 |
| [DATA_MAPPING.md](docs/DATA_MAPPING.md) | 数据源到 H5 格式的映射方案 | 🚧 编写中 |
| [BaoStock API Reference](docs/reference/baostock_api/BaoStock_API_Reference.md) | BaoStock 完整 API 文档 | ✅ 已完成 |
| [QStock API Reference](docs/reference/qstock_api/QStock_API_Reference.md) | QStock 完整 API 文档 | ✅ 已完成 |
| [Mootdx API Reference](docs/reference/mootdx_api/MOOTDX_API_Reference.md) | Mootdx 完整 API 文档 | ✅ 已完成 |

## 🎯 核心功能

### 数据获取
- ✅ **混合数据源**: K线用Mootdx加速,估值/基本面用BaoStock(性能提升25%)
- ✅ **智能过滤**: 自动区分股票/指数,只下载真实股票数据
- ✅ **增量更新**: 智能识别已有数据,仅下载增量部分
- ✅ **断点续传**: 支持中断后继续下载,跳过已完成的股票
- ✅ **进度显示**: 流畅的进度条,实时显示成功/失败数量

### 数据处理
- ✅ **格式转换**: 自动转换为 SimTradeLab 兼容的 HDF5 格式
- ✅ **数据清洗**: 去除异常值,补全缺失数据
- ✅ **数据验证**: 完整性检查,质量评分
- ✅ **复权处理**: 自动计算前复权/后复权因子

### 数据质量
- ✅ **缺失检测**: 自动检测数据缺口
- ✅ **异常监控**: 识别价格异常、成交量异常
- ✅ **多源校验**: 多数据源交叉验证数据准确性

## 🏗️ 项目结构

```
SimTradeData/
├── simtradedata/           # 源代码
│   ├── fetchers/          # 数据获取模块
│   │   ├── baostock_fetcher.py    # BaoStock数据源
│   │   └── mootdx_fetcher.py      # Mootdx数据源(K线加速)
│   ├── converters/        # 格式转换模块
│   ├── writers/           # HDF5 写入模块
│   ├── utils/             # 工具函数
│   ├── cli.py             # 命令行接口
│   └── pipeline.py        # 数据处理流程
├── data/                  # 生成的 H5 文件
├── docs/                  # 文档
│   ├── reference/         # API 参考文档
│   └── *.md              # 各类说明文档
├── tests/                 # 测试文件
└── examples/              # 使用示例
```

## 💡 使用示例

### Python API 使用

```python
from simtradedata.pipeline import DataPipeline

# 创建数据管道(默认使用Mootdx加速K线)
pipeline = DataPipeline(
    output_dir='data',
    market_source='mootdx'  # 或 'baostock'
)

# 下载单只股票的全部数据
with pipeline:
    success = pipeline.fetch_and_write_stock(
        symbol='600000.SH',
        start_date='2024-01-01',
        end_date='2024-12-31',
        include_fundamentals=True
    )

# 批量下载股票列表
stock_list = ['600000.SH', '000001.SZ', '000002.SZ']
results = pipeline.fetch_and_write_all_stocks(
    stock_list=stock_list,
    start_date='2024-01-01',
    end_date='2024-12-31',
    include_fundamentals=False,
    skip_existing=True
)

print(f"成功: {results['success']}, 失败: {results['failure']}")
```

### 命令行使用

```bash
# 下载全市场数据(使用Mootdx加速)
poetry run python -m simtradedata.cli fetch-all \
  --start-date 2024-01-01 \
  --market-source mootdx

# 下载指定股票
poetry run python -m simtradedata.cli fetch \
  "000001.SZ,600000.SH" \
  --start-date 2024-01-01 \
  --market-source mootdx

# 增量更新最近30天
poetry run python -m simtradedata.cli update --days 30

# 验证数据完整性
poetry run python -m simtradedata.cli validate

# 查看数据统计
poetry run python -m simtradedata.cli stats
```

## ⚙️ 配置说明

创建配置文件 `config.yaml`:

```yaml
# 数据源配置
data_sources:
  priority: ['baostock', 'qstock', 'yahoo']  # 数据源优先级

  baostock:
    enabled: true
    max_retries: 3

  qstock:
    enabled: true

  yahoo:
    enabled: true
    proxy: null  # 可选代理配置

# 数据存储配置
storage:
  output_dir: 'data'
  compression: 'gzip'  # HDF5 压缩算法

# 下载配置
download:
  max_workers: 4  # 并发线程数
  chunk_size: 100  # 每批次下载股票数
  retry_delay: 5   # 失败重试延迟(秒)
```

## 🔧 开发

### 运行测试

```bash
# 运行所有测试
poetry run pytest

# 运行特定测试
poetry run pytest tests/test_fetchers.py

# 生成覆盖率报告
poetry run pytest --cov=simtradedata --cov-report=html
```

### 代码风格

项目使用 Black + isort 进行代码格式化:

```bash
# 格式化代码
poetry run black simtradedata/
poetry run isort simtradedata/

# 检查代码风格
poetry run black --check simtradedata/
```

## ⚠️ 数据说明

### 数据完整性

由于免费数据源的限制,某些数据可能不完整:

| 数据类型 | 可用性 | 备注 |
|----------|--------|------|
| 日线行情 | ✅ 完整 | 覆盖全市场 |
| 分钟线行情 | ⚠️ 部分 | 需要 Mootdx |
| 财务数据 | ✅ 完整 | 季度更新 |
| 估值指标 | ✅ 完整 | 每日更新 |
| 股票列表 | ✅ 完整 | 包含退市股 |
| 行业分类 | ✅ 完整 | 申万行业 |

### 数据免责声明

本项目提供的数据来源于公开的免费数据源,仅供学习研究使用。请勿用于实盘交易。使用者需自行承担使用数据的风险。

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议!

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🔗 相关链接

- **SimTradeLab**: https://github.com/kay_ou/SimTradeLab - 量化策略回测框架
- **BaoStock**: http://baostock.com/ - 免费证券数据平台
- **QStock**: https://github.com/tkfy920/qstock - 开源 A 股数据接口
- **Yahoo Finance**: https://finance.yahoo.com/ - 全球金融数据

## 📮 联系方式

- **Issues**: https://github.com/kay_ou/SimTradeData/issues
- **Email**: kayou@duck.com

---

**项目状态**: 🚧 开发中 | **当前版本**: v0.1.0 | **最后更新**: 2025-11-14
