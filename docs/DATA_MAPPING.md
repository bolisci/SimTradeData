# 数据映射方案文档

## 概述

本文档详细说明如何将 BaoStock、QStock、Yahoo Finance 等开源数据源的数据映射到 SimTradeLab 兼容的 HDF5 格式。

**目标**: 生成与 PTrade 数据格式完全兼容的 HDF5 文件,使 SimTradeLab 可以零修改使用免费数据源。

---

## 一、ptrade_data.h5 映射方案

### 文件结构

```
ptrade_data.h5
├── benchmark          # 基准指数数据
├── stock_data/        # 股票行情数据
│   ├── 000001.SZ     # 每只股票一个 group
│   ├── 000002.SZ
│   └── ...
├── exrights/          # 除权除息数据
│   ├── 000001.SZ
│   └── ...
├── metadata           # 元数据(暂时为空)
└── stock_metadata     # 股票元数据
```

### 1.1 benchmark (基准指数)

#### 目标格式

| 字段名 | 类型 | 说明 |
|--------|------|------|
| close | float | 收盘价 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| volume | float | 成交量 |
| money | float | 成交额 |

索引: datetime64[ns] 类型的日期

#### 数据源映射

**BaoStock** (推荐,数据最完整)

```python
import baostock as bs

# 获取上证指数数据
bs.login()
rs = bs.query_history_k_data_plus(
    "sh.000001",  # 上证综指
    "date,open,high,low,close,volume,amount",
    start_date='2020-01-01',
    end_date='2025-12-31',
    frequency="d",
    adjustflag="3"  # 不复权
)
bs.logout()

# 字段映射
ptrade_fields = {
    'open': 'open',
    'high': 'high',
    'low': 'low',
    'close': 'close',
    'volume': 'volume',
    'amount': 'money'  # 注意: BaoStock 的 amount 对应 PTrade 的 money
}
```

**QStock** (备选)

```python
from qstock import get_data

# 获取上证指数
df = get_data('000001', 'gzindex')  # 沪深指数

# 字段映射 (与 BaoStock 相同)
```

**Yahoo Finance** (用于港股/美股基准)

```python
import yfinance as yf

# 获取恒生指数
df = yf.download('^HSI', start='2020-01-01', end='2025-12-31')

# 字段映射
df.columns = df.columns.str.lower()
df.rename(columns={'adj close': 'close'}, inplace=True)
```

### 1.2 stock_data (股票行情)

#### 目标格式

每只股票一个 group,包含以下字段:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| close | float | 收盘价 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| volume | float | 成交量 |
| money | float | 成交额 |

索引: datetime64[ns] 类型的日期

#### 数据源映射

**BaoStock** (推荐)

```python
# 获取单只股票数据
rs = bs.query_history_k_data_plus(
    "sz.000001",  # 平安银行
    "date,open,high,low,close,volume,amount",
    start_date='2020-01-01',
    end_date='2025-12-31',
    frequency="d",
    adjustflag="3"  # 不复权(后续使用复权因子)
)

# 字段映射(同 benchmark)
```

**QStock** (备选)

```python
from qstock import get_data

# 获取股票数据
df = get_data('000001', 'stock-day')

# QStock 字段映射
qstock_to_ptrade = {
    'open': 'open',
    'high': 'high',
    'low': 'low',
    'close': 'close',
    'volume': 'volume',
    'amount': 'money'
}
```

**注意事项**:
- BaoStock 和 QStock 的股票代码格式不同
  - BaoStock: `sh.600000`, `sz.000001`
  - QStock: `600000`, `000001`
  - PTrade: `600000.SH`, `000001.SZ`
- 需要进行代码转换

### 1.3 exrights (除权除息)

#### 目标格式

每只股票一个 group,包含以下字段:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| allotted_ps | float | 配股比例 |
| rationed_ps | float | 配股价格比例 |
| rationed_px | float | 配股价格 |
| bonus_ps | float | 送股比例 |
| exer_forward_a | float | 前复权因子 a |
| exer_forward_b | float | 前复权因子 b |
| exer_backward_a | float | 后复权因子 a |
| exer_backward_b | float | 后复权因子 b |

索引: date (int64 格式,如 20250612)

#### 数据源映射

**BaoStock** (推荐)

```python
# 获取除权除息信息
rs = bs.query_dividend_data(
    code="sh.600000",
    year="2024",
    yearType="report"
)

# 字段映射
baostock_fields = {
    'dividOperateDate': 'date',        # 除权除息日
    'perCashDiv': 'cash_div',          # 每股现金分红
    'perShareDivRatio': 'bonus_ps',    # 每股送股比例
    'perShareTransRatio': 'transfer',  # 每股转增比例
    'allotmentRatio': 'allotted_ps',   # 配股比例
    'allotmentPrice': 'rationed_px'    # 配股价格
}

# 复权因子需要单独计算或从 query_adjust_factor 获取
rs_adj = bs.query_adjust_factor(
    code="sh.600000",
    start_date="2020-01-01",
    end_date="2025-12-31"
)
# 返回字段: date, foreAdjustFactor, backAdjustFactor
```

**QStock** (备选)

```python
from qstock import get_data

# 获取分红数据
df = get_data('600000', 'bonus')

# QStock 提供的分红信息较为简单,可能需要补充
```

**注意事项**:
- BaoStock 提供的是原始除权除息信息,复权因子需要单独获取
- 复权因子的 a、b 参数需要根据除权除息信息计算

### 1.4 stock_metadata (股票元数据)

#### 目标格式

| 字段名 | 类型 | 说明 |
|--------|------|------|
| blocks | string (JSON) | 板块信息 |
| de_listed_date | datetime | 退市日期 |
| has_info | bool | 是否有信息 |
| listed_date | datetime | 上市日期 |
| stock_name | string | 股票名称 |

索引: stock_code (股票代码)

#### 数据源映射

**BaoStock** (推荐)

```python
# 获取股票基本信息
rs = bs.query_stock_basic(code="sh.600000")

# 字段映射
baostock_fields = {
    'code': 'stock_code',
    'code_name': 'stock_name',
    'ipoDate': 'listed_date',
    'outDate': 'de_listed_date'
}

# 获取行业分类(板块信息)
rs_industry = bs.query_stock_industry(code="sh.600000")

# 返回字段: code, industry, industryClassification
# 需要转换为 JSON 格式存储到 blocks 字段
```

**QStock** (备选)

```python
from qstock import get_data

# 获取股票基本信息
df = get_data('000001', 'stock-info')

# QStock 提供的信息更全面,包括概念板块等
```

---

## 二、ptrade_fundamentals.h5 映射方案

### 文件结构

```
ptrade_fundamentals.h5
├── fundamentals/     # 基本面财务指标
│   ├── 000001.SZ
│   └── ...
└── valuation/        # 估值指标
    ├── 000001.SZ
    └── ...
```

### 2.1 fundamentals (基本面财务指标)

#### 目标格式

**⚠️ 重要**: 除了 23 个财务指标外，还必须保存 `pubDate`（公告日期）和 `statDate`（统计日期）字段。

25 个字段（23个财务指标 + 2个日期字段），季度数据:

| 字段名 | 说明 | 重要性 |
|--------|------|--------|
| **日期字段** (2个) | | |
| pubDate | 公告日期 | ⚠️ **最重要** - 避免未来函数 |
| statDate | 统计日期（季度结束日期） | 必需 |
| **财务指标** (23个) | | |
| accounts_receivables_turnover_rate | 应收账款周转率 | |
| basic_eps_yoy | 基本每股收益同比增长率 | |
| current_assets_turnover_rate | 流动资产周转率 | |
| current_ratio | 流动比率 | |
| debt_equity_ratio | 资产负债率 | |
| gross_income_ratio | 销售毛利率 | |
| gross_income_ratio_ttm | 销售毛利率(TTM) | |
| interest_cover | 利息保障倍数 | |
| inventory_turnover_rate | 存货周转率 | |
| net_profit_grow_rate | 净利润增长率 | |
| net_profit_ratio | 销售净利率 | |
| net_profit_ratio_ttm | 销售净利率(TTM) | |
| np_parent_company_yoy | 归母净利润同比 | |
| operating_revenue_grow_rate | 营业收入增长率 | |
| quick_ratio | 速动比率 | |
| roa | 总资产收益率 | |
| roa_ebit_ttm | EBIT/总资产(TTM) | |
| roa_ttm | 总资产收益率(TTM) | |
| roe | 净资产收益率 | |
| roe_ttm | 净资产收益率(TTM) | |
| roic | 投入资本回报率 | |
| total_asset_grow_rate | 总资产增长率 | |
| total_asset_turnover_rate | 总资产周转率 | |

索引: end_date (datetime64[ns],通常等于 statDate)

**字段说明**:
- `pubDate`: 财报公告日期，决定数据何时可用，用于回测时避免使用未来数据
- `statDate`: 财报统计日期，即季度结束日期（如 2024-09-30）
- `end_date`: 索引字段，通常等于 `statDate`

#### 数据源映射

**BaoStock** (推荐,提供完整的季频财务指标)

BaoStock 提供多个季频财务 API,需要组合使用:

```python
import baostock as bs

bs.login()

# 1. 盈利能力
rs_profit = bs.query_profit_data(
    code="sh.600000",
    year=2024,
    quarter=3
)
# 字段: roeAvg, npMargin, gpMargin, netProfit, epsTTM, MBRevenue, totalProfitMargin, ...

# 2. 营运能力
rs_operation = bs.query_operation_data(
    code="sh.600000",
    year=2024,
    quarter=3
)
# 字段: NRTurnRatio, NRTurnDays, INVTurnRatio, INVTurnDays, CATurnRatio, ...

# 3. 成长能力
rs_growth = bs.query_growth_data(
    code="sh.600000",
    year=2024,
    quarter=3
)
# 字段: YOYEquity, YOYAsset, YOYNI, YOYEPSBasic, YOYPNI, ...

# 4. 偿债能力
rs_balance = bs.query_balance_data(
    code="sh.600000",
    year=2024,
    quarter=3
)
# 字段: currentRatio, quickRatio, cashRatio, YOYLiability, liabilityToAsset, ...

# 5. 现金流量
rs_cash = bs.query_cash_flow_data(
    code="sh.600000",
    year=2024,
    quarter=3
)
# 字段: CAToAsset, NCAToAsset, tangibleAssetToAsset, ebitToInterest, ...

# 6. 杜邦指数
rs_dupont = bs.query_dupont_data(
    code="sh.600000",
    year=2024,
    quarter=3
)
# 字段: dupontROE, dupontAssetStoEquity, dupontAssetTurn, dupontPnitoni, ...

bs.logout()
```

**完整字段映射表** (23个字段):

| PTrade 字段 | 说明 | BaoStock API | BaoStock 字段 | 映射状态 |
|-------------|------|-------------|--------------|---------|
| **盈利能力指标** (4个) |
| roe | 净资产收益率 | query_profit_data | roeAvg | ✅ 直接映射 |
| roe_ttm | 净资产收益率TTM | - | - | ⚠️ 需计算 (滚动4季度) |
| roa | 总资产净利率 | query_profit_data | roa | ✅ 直接映射 |
| roa_ttm | 总资产净利率TTM | - | - | ⚠️ 需计算 (滚动4季度) |
| roa_ebit_ttm | 总资产报酬率TTM | - | - | ⚠️ 需计算 |
| roic | 投入资本回报率 | - | - | ⚠️ 需计算公式 |
| net_profit_ratio | 销售净利率 | query_profit_data | npMargin | ✅ 直接映射 |
| net_profit_ratio_ttm | 销售净利率TTM | - | - | ⚠️ 需计算 (滚动4季度) |
| gross_income_ratio | 销售毛利率 | query_profit_data | gpMargin | ✅ 直接映射 |
| gross_income_ratio_ttm | 销售毛利率TTM | - | - | ⚠️ 需计算 (滚动4季度) |
| **成长能力指标** (5个) |
| operating_revenue_grow_rate | 营业收入增长率 | query_growth_data | YOYORev | ✅ 直接映射 |
| net_profit_grow_rate | 净利润增长率 | query_growth_data | YOYNI | ✅ 直接映射 |
| total_asset_grow_rate | 总资产增长率 | query_growth_data | YOYAsset | ✅ 直接映射 |
| basic_eps_yoy | 基本每股收益同比 | query_growth_data | YOYEPSBasic | ✅ 直接映射 |
| np_parent_company_yoy | 归母净利润同比 | query_growth_data | YOYPNI | ✅ 直接映射 |
| **偿债能力指标** (3个) |
| current_ratio | 流动比率 | query_balance_data | currentRatio | ✅ 直接映射 |
| quick_ratio | 速动比率 | query_balance_data | quickRatio | ✅ 直接映射 |
| debt_equity_ratio | 资产负债率 | query_balance_data | liabilityToAsset | ✅ 直接映射 |
| **营运能力指标** (4个) |
| accounts_receivables_turnover_rate | 应收账款周转率 | query_operation_data | NRTurnRatio | ✅ 直接映射 |
| inventory_turnover_rate | 存货周转率 | query_operation_data | INVTurnRatio | ✅ 直接映射 |
| current_assets_turnover_rate | 流动资产周转率 | query_operation_data | CATurnRatio | ✅ 直接映射 |
| total_asset_turnover_rate | 总资产周转率 | query_operation_data | AssetTurnRatio | ✅ 直接映射 |
| **现金流量指标** (1个) |
| interest_cover | 利息保障倍数 | query_cash_flow_data | ebitToInterest | ✅ 直接映射 |

**数据覆盖率**:
- ✅ 可直接获取: **16/23 字段 (70%)**
- ⚠️ 需要计算: **7/23 字段 (30%)**
  - 5个 TTM 指标 (滚动4季度求和)
  - 1个 ROIC (需公式计算)
  - 1个 roa_ebit_ttm (需公式计算)

**QStock** (备选)

```python
from qstock import get_data

# QStock 提供的财务数据接口
df = get_data('000001', 'financial_data')

# QStock 字段较少,可能需要补充或计算
```

**注意事项**:
- BaoStock 需要调用多个 API 来获取全部 23 个指标
- 某些指标可能需要根据其他字段计算得出
- TTM (Trailing Twelve Months) 指标需要特殊处理

### 2.2 valuation (估值指标)

#### 目标格式

8 个估值指标,日频数据:

| 字段名 | 说明 |
|--------|------|
| float_value | 流通市值 |
| pb | 市净率 |
| pcf | 市现率 |
| pe_ttm | 市盈率(TTM) |
| ps_ttm | 市销率(TTM) |
| total_shares | 总股本 |
| total_value | 总市值 |
| turnover_rate | 换手率 |

索引: date (datetime64[ns])

#### 数据源映射

**BaoStock** (推荐)

```python
# 获取日线数据 (含估值指标)
rs = bs.query_history_k_data_plus(
    "sh.600000",
    "date,close,peTTM,pbMRQ,psTTM,pcfNcfTTM,turn",
    start_date='2020-01-01',
    end_date='2025-12-31',
    frequency="d",
    adjustflag="3"
)

# 获取股本信息 (用于计算市值)
rs_basic = bs.query_stock_basic(code="sh.600000")
```

**完整字段映射表** (8个字段):

| PTrade 字段 | 说明 | BaoStock API | BaoStock 字段 | 映射状态 |
|------------|------|-------------|--------------|---------|
| pe_ttm | 市盈率TTM | query_history_k_data_plus | peTTM | ✅ 直接映射 |
| pb | 市净率 | query_history_k_data_plus | pbMRQ | ✅ 直接映射 |
| ps_ttm | 市销率TTM | query_history_k_data_plus | psTTM | ✅ 直接映射 |
| pcf | 市现率 | query_history_k_data_plus | pcfNcfTTM | ✅ 直接映射 |
| turnover_rate | 换手率 | query_history_k_data_plus | turn | ✅ 直接映射 |
| total_value | 总市值 | - | - | ⚠️ 需计算: close × total_shares |
| float_value | 流通市值 | - | - | ⚠️ 需计算: close × float_shares |
| total_shares | 总股本 | query_stock_basic | - | ⚠️ 从股票基本信息获取 |

**数据覆盖率**:
- ✅ 可直接获取: **5/8 字段 (63%)**
- ⚠️ 需要计算: **3/8 字段 (37%)**
  - 2个市值字段 (价格 × 股本)
  - 1个股本字段 (从 query_stock_basic 获取)

**QStock** (备选)

```python
from qstock import get_data

# 获取估值数据
df = get_data('000001', 'valuation')

# QStock 提供的估值指标较全
```

**注意事项**:
- BaoStock 不直接提供市值数据,需要根据价格 × 股本计算
- 股本数据可从 `query_stock_basic` 获取

---

## 三、ptrade_adj_pre.h5 映射方案

### 文件结构

```
ptrade_adj_pre.h5
├── 000001.SZ    # 每只股票一个 Series
├── 000002.SZ
└── ...
```

### 目标格式

每只股票存储为一个 pandas Series:
- **索引**: datetime64[ns] 类型的日期
- **数值**: float32 类型的复权因子
- **Series 名称**: `backward_a` (后复权因子)

### 数据源映射

**BaoStock** (推荐)

```python
# 获取复权因子
rs = bs.query_adjust_factor(
    code="sh.600000",
    start_date="2020-01-01",
    end_date="2025-12-31"
)

# 返回字段:
# - date: 日期
# - foreAdjustFactor: 前复权因子
# - backAdjustFactor: 后复权因子

# PTrade 使用的是 backward_a (后复权因子)
# 直接使用 backAdjustFactor
```

**QStock** (备选)

```python
from qstock import get_data

# QStock 暂不直接提供复权因子
# 需要根据除权除息信息自行计算
```

**复权因子计算方法** (如果数据源不提供):

```python
def calculate_adjust_factor(df_exrights):
    """
    根据除权除息信息计算复权因子

    Args:
        df_exrights: DataFrame, 包含除权除息信息
            - date: 除权除息日
            - bonus_ps: 送股比例
            - transfer_ps: 转增比例
            - cash_div: 现金分红
            - allotted_ps: 配股比例
            - rationed_px: 配股价格
            - close_price: 收盘价(除权前一日)

    Returns:
        Series: 后复权因子序列
    """
    adjust_factor = 1.0
    factors = []

    for idx, row in df_exrights.iterrows():
        # 计算除权除息当日的调整因子
        # 公式: factor = (close + cash_div) / (close + cash_div - (bonus + transfer) - allotted * px)
        close = row['close_price']
        cash = row['cash_div']
        bonus = row['bonus_ps']
        transfer = row['transfer_ps']
        allotted = row['allotted_ps']
        px = row['rationed_px']

        numerator = close + cash
        denominator = close + cash - (bonus + transfer) - allotted * px

        if denominator != 0:
            daily_factor = numerator / denominator
            adjust_factor *= daily_factor

        factors.append((row['date'], adjust_factor))

    return pd.Series([f[1] for f in factors], index=[f[0] for f in factors])
```

---

## 四、ptrade_dividend_cache.h5 映射方案

### 文件结构

```
ptrade_dividend_cache.h5
└── dividends/       # PyTables 表格格式
    └── table        # 分红数据表
```

### 目标格式

PyTables 格式的表格,字段待确定 (当前文件为空)。

### 数据源映射

**BaoStock**

```python
# 获取分红数据
rs = bs.query_dividend_data(
    code="sh.600000",
    year="2024",
    yearType="report"
)

# 返回字段:
# - code: 股票代码
# - dividOperateDate: 除权除息日
# - perCashDiv: 每股现金分红
# - perShareDivRatio: 每股送股比例
# - perShareTransRatio: 每股转增比例
# - allotmentRatio: 配股比例
# - allotmentPrice: 配股价格
# - recordDate: 股权登记日
# - exDividendDate: 除息日
```

**注意事项**:
- 这个文件在示例数据中几乎为空,可能是 SimTradeLab 的缓存文件
- 如果 SimTradeLab 不使用此文件,可以暂时不生成

---

## 五、数据质量保证

### 5.1 数据完整性检查

实现以下检查机制:

1. **日期连续性检查**: 检查交易日是否连续(排除节假日)
2. **字段完整性检查**: 确保所有必需字段都存在
3. **数值范围检查**: 检查数值是否在合理范围内
4. **缺失值检查**: 统计并报告缺失值情况

### 5.2 数据源优先级

当多个数据源可用时,按以下优先级选择:

1. **BaoStock** - 数据最完整,接口最稳定
2. **QStock** - 更新及时,数据较新
3. **Yahoo Finance** - 用于港股/美股补充

### 5.3 异常数据处理

- **价格异常**: 涨跌幅超过 ±20% 需要标记并验证
- **成交量异常**: 成交量为 0 或异常高需要标记
- **缺失数据**: 尝试从备用数据源获取,否则标记为 NaN

---

## 六、实现步骤

### 步骤 1: 数据获取

```python
class DataFetcher:
    def __init__(self, source='baostock'):
        self.source = source

    def fetch_market_data(self, symbol, start_date, end_date):
        """获取行情数据"""
        pass

    def fetch_fundamentals(self, symbol, year, quarter):
        """获取财务数据"""
        pass

    def fetch_valuation(self, symbol, start_date, end_date):
        """获取估值数据"""
        pass

    def fetch_adjust_factor(self, symbol, start_date, end_date):
        """获取复权因子"""
        pass
```

### 步骤 2: 数据转换

```python
class DataConverter:
    def convert_to_ptrade_format(self, data, data_type):
        """转换为 PTrade 格式"""
        pass

    def normalize_stock_code(self, code, source):
        """统一股票代码格式"""
        # baostock: sh.600000 -> 600000.SH
        # qstock: 600000 -> 600000.SH
        pass
```

### 步骤 3: HDF5 写入

```python
class HDF5Writer:
    def __init__(self, filepath):
        self.filepath = filepath

    def write_market_data(self, data):
        """写入行情数据到 ptrade_data.h5"""
        pass

    def write_fundamentals(self, data):
        """写入财务数据到 ptrade_fundamentals.h5"""
        pass

    def write_adjust_factor(self, data):
        """写入复权因子到 ptrade_adj_pre.h5"""
        pass
```

### 步骤 4: 数据验证

```python
class DataValidator:
    def validate_completeness(self, filepath):
        """验证数据完整性"""
        pass

    def validate_format(self, filepath):
        """验证格式兼容性"""
        pass
```

---

## 七、未映射字段说明

### 当前无法映射的字段

| 文件 | 字段 | 原因 | 解决方案 |
|------|------|------|----------|
| ptrade_fundamentals.h5 | roe_ttm | BaoStock 仅提供季度 ROE | 可根据季度数据计算 TTM |
| ptrade_fundamentals.h5 | gross_income_ratio_ttm | 同上 | 需要计算 |
| ptrade_fundamentals.h5 | roic | BaoStock 不直接提供 ROIC | 可根据公式计算 |
| ptrade_data.h5 | exrights 的复权因子字段 | 需要特殊计算 | 使用 query_adjust_factor 获取或自行计算 |
| ptrade_dividend_cache.h5 | 全部字段 | 文件用途不明确 | 暂时可不生成 |

### 字段计算公式

**TTM 指标计算**:
```python
def calculate_ttm(quarterly_data, num_quarters=4):
    """
    计算 TTM (最近12个月) 指标

    Args:
        quarterly_data: 季度数据
        num_quarters: 使用的季度数 (默认4)

    Returns:
        TTM 值
    """
    return quarterly_data.rolling(window=num_quarters).sum()
```

**ROIC (投入资本回报率) 计算**:
```
ROIC = NOPAT / (总资产 - 流动负债 - 现金)
其中 NOPAT = 营业利润 × (1 - 税率)
```

---

## 八、测试计划

### 单元测试

```python
def test_data_fetcher():
    """测试数据获取"""
    fetcher = DataFetcher(source='baostock')
    data = fetcher.fetch_market_data('000001.SZ', '2024-01-01', '2024-12-31')
    assert data is not None
    assert '000001.SZ' in data
    assert len(data) > 0

def test_data_converter():
    """测试数据转换"""
    converter = DataConverter()
    code = converter.normalize_stock_code('sh.600000', 'baostock')
    assert code == '600000.SH'

def test_hdf5_writer():
    """测试 HDF5 写入"""
    writer = HDF5Writer('test_ptrade_data.h5')
    writer.write_market_data(sample_data)
    # 验证文件格式与 PTrade 一致
```

### 集成测试

```python
def test_full_pipeline():
    """测试完整流程"""
    # 1. 获取数据
    fetcher = DataFetcher()
    data = fetcher.fetch_all('000001.SZ', '2024-01-01', '2024-12-31')

    # 2. 转换格式
    converter = DataConverter()
    ptrade_data = converter.convert(data)

    # 3. 写入文件
    writer = HDF5Writer('test.h5')
    writer.write(ptrade_data)

    # 4. 验证
    validator = DataValidator()
    assert validator.validate('test.h5') == True
```

### 兼容性测试

```python
def test_simtradelab_compatibility():
    """测试与 SimTradeLab 的兼容性"""
    # 使用生成的 H5 文件在 SimTradeLab 中运行测试策略
    # 确保可以正常加载和使用
    pass
```

---

## 九、性能优化

### 增量更新

```python
def incremental_update(h5_file, start_date=None):
    """增量更新已有 H5 文件"""
    # 读取文件中最新日期
    with pd.HDFStore(h5_file) as store:
        last_date = get_latest_date(store)

    # 从最新日期的下一天开始下载
    if start_date is None:
        start_date = last_date + timedelta(days=1)

    # 下载增量数据
    new_data = fetch_data(start_date, datetime.now())

    # 追加到文件
    append_to_h5(h5_file, new_data)
```

### 压缩优化

```python
# 使用 HDF5 压缩减小文件大小
with pd.HDFStore('ptrade_data.h5', complevel=9, complib='blosc') as store:
    store.put('stock_data/000001.SZ', df, format='table')
```

---

## 十、常见问题

### Q1: BaoStock 股票代码格式如何转换?

```python
def convert_baostock_code(code):
    """
    BaoStock: sh.600000, sz.000001
    PTrade: 600000.SH, 000001.SZ
    """
    market, symbol = code.split('.')
    market_map = {'sh': 'SH', 'sz': 'SZ'}
    return f"{symbol}.{market_map[market]}"
```

### Q2: 如何处理停牌股票?

停牌期间数据缺失,可以:
1. 保留停牌前最后一天的数据
2. 标记为 NaN
3. 在元数据中记录停牌信息

### Q3: 历史数据追溯到多久?

- BaoStock: 支持从 1990 年开始
- QStock: 支持从 2000 年左右
- Yahoo Finance: 取决于具体股票

建议至少下载最近 5 年的数据,以满足回测需求。

### Q4: 如何处理数据源API限流?

```python
import time

def fetch_with_retry(func, *args, max_retries=3, delay=5, **kwargs):
    """带重试的数据获取"""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise e
```

---

## 十一、总结

本映射方案详细说明了如何将开源数据源转换为 SimTradeLab 兼容的 HDF5 格式。主要工作包括:

1. ✅ **ptrade_data.h5**: 行情、除权除息、元数据映射完成
2. ✅ **ptrade_fundamentals.h5**: 财务和估值指标映射完成
3. ✅ **ptrade_adj_pre.h5**: 复权因子映射完成

通过本方案,可以完全使用免费数据源替代 PTrade 商业数据,实现 SimTradeLab 的零成本使用。

---

**最后更新**: 2025-11-14
**维护者**: kayou@duck.com
