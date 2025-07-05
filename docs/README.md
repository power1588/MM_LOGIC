# 被动做市策略系统 (Market Making Strategy System)

## 项目概述

这是一个专业的被动做市策略系统，专为加密货币交易设计。系统采用事件驱动架构，提供高可用性、低延迟的做市服务。

## 系统架构

```
MM_Logic/
├── src/                          # 源代码目录
│   ├── core/                     # 核心模块
│   │   ├── events/              # 事件系统
│   │   │   ├── EventBus.py      # 事件总线
│   │   │   └── EventType.py     # 事件类型定义
│   │   └── orders/              # 订单管理
│   │       ├── OrderState.py    # 订单状态管理
│   │       ├── OrderAnalysis.py # 订单分析
│   │       └── OrderDecision.py # 订单决策
│   ├── strategy/                 # 策略模块
│   │   └── engines/             # 策略引擎
│   │       ├── StrategyEngine.py        # 主策略引擎
│   │       └── ReferencePriceEngine.py  # 参考价格引擎
│   ├── execution/                # 执行模块
│   │   ├── ExecutionEngine.py   # 执行引擎
│   │   ├── ExecutionTask.py     # 执行任务
│   │   └── api/                 # 交易所API
│   │       └── ExchangeAPI.py   # 交易所接口
│   ├── risk/                     # 风险管理
│   │   └── management/          # 风险管理器
│   │       ├── RiskManager.py   # 风险管理器
│   │       ├── RiskConfig.py    # 风险配置
│   │       └── RiskLevel.py     # 风险等级
│   ├── market/                   # 市场数据
│   │   └── data/                # 市场数据
│   │       └── MarketDataGateway.py # 市场数据网关
│   ├── config/                   # 配置管理
│   │   ├── Configs.py           # 配置类定义
│   │   └── loaders/             # 配置加载器
│   │       └── ConfigLoader.py  # 配置加载器
│   ├── utils/                    # 工具模块
│   │   └── limiting/            # 速率限制
│   │       └── RateLimiter.py   # 速率限制器
│   └── strategy_main.py         # 策略主程序
├── tests/                        # 测试目录
│   ├── test_EventBus.py         # 事件总线测试
│   ├── test_OrderManager.py     # 订单管理测试
│   ├── test_StrategyEngine.py   # 策略引擎测试
│   ├── test_RiskManager.py      # 风险管理测试
│   ├── test_ReferencePriceEngine.py # 价格引擎测试
│   └── test_RateLimiter.py      # 速率限制测试
├── docs/                         # 文档目录
│   ├── README.md                # 项目说明
│   └── 项目架构设计.md           # 架构设计文档
├── config.yaml                   # 配置文件
├── requirements.txt              # 依赖包列表
└── main.py                      # 主程序入口
```

## 核心特性

### 🎯 策略特性
- **被动做市**: 维持0.2%-0.4%的买卖价差
- **连续流动性**: 确保市场始终有买卖订单
- **实时价格跟踪**: 基于TWAP的参考价格计算
- **最小化被动成交**: 智能订单位置优化
- **高可用性**: 99.9%+的系统可用性

### 🏗️ 技术架构
- **事件驱动**: 基于事件总线的松耦合架构
- **模块化设计**: 清晰的模块边界和职责分离
- **异步处理**: 全异步I/O，高并发处理
- **风险管理**: 多层次风险控制机制
- **实时监控**: 完整的系统监控和指标

### 📊 关键指标 (KPIs)
- **价差控制**: 0.2%-0.4%目标价差
- **订单填充率**: <5%被动成交率
- **系统延迟**: <10ms事件处理延迟
- **风险控制**: 0风险事件
- **可用性**: 99.9%+系统可用性

## 安装和运行

### 环境要求
- Python 3.8+
- 64位操作系统
- 至少4GB内存

### 安装依赖
```bash
pip install -r requirements.txt
```

### 配置系统
1. 复制并修改配置文件：
```bash
cp config.yaml config_local.yaml
# 编辑 config_local.yaml 文件
```

2. 配置参数说明：
```yaml
strategy:
  symbol: "BTCUSDT"           # 交易对
  min_spread: 0.002          # 最小价差 (0.2%)
  max_spread: 0.004          # 最大价差 (0.4%)
  min_order_value: 10000     # 最小订单价值 (USDT)
  drift_threshold: 0.005     # 价格漂移阈值
  target_orders_per_side: 1  # 每边目标订单数

execution:
  worker_count: 4            # 执行工作器数量
  rate_limit: 1200           # 速率限制 (每分钟)
  max_retries: 3            # 最大重试次数

risk:
  max_position: 100000       # 最大持仓 (USDT)
  max_daily_loss: 5000      # 最大日亏损 (USDT)
  max_price_change: 0.1     # 最大价格变化 (10%)
```

### 运行系统
```bash
# 使用默认配置
python main.py

# 使用自定义配置
python main.py config_local.yaml
```

### 运行测试
```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_EventBus.py

# 生成测试覆盖率报告
pytest --cov=src tests/
```

## 系统监控

### 实时指标
- 当前价差
- 订单状态统计
- 风险指标
- 系统性能指标

### 日志监控
- 事件处理日志
- 错误和异常日志
- 性能指标日志

## 风险控制

### 多层次风险控制
1. **订单级别**: 价格和数量限制
2. **策略级别**: 价差和持仓控制
3. **系统级别**: 紧急停止机制
4. **市场级别**: 价格异常检测

### 风险指标
- 持仓限制: 最大持仓量控制
- 亏损限制: 日亏损上限
- 价格异常: 价格变化监控
- 订单异常: 订单数量控制

## 开发指南

### 代码规范
- 遵循PEP 8编码规范
- 使用类型注解
- 编写完整的文档字符串
- 保持模块职责单一

### 测试要求
- 单元测试覆盖率 > 90%
- 集成测试覆盖核心流程
- 性能测试验证延迟要求

### 部署建议
- 使用Docker容器化部署
- 配置负载均衡
- 设置监控告警
- 准备回滚机制

## 技术栈

### 核心依赖
- **asyncio**: 异步编程框架
- **websockets**: WebSocket客户端
- **PyYAML**: 配置文件解析
- **pytest**: 测试框架
- **decimal**: 精确数值计算

### 可选依赖
- **prometheus_client**: 指标监控
- **structlog**: 结构化日志
- **redis**: 缓存和状态存储

## 许可证

本项目采用 MIT 许可证。

## 联系方式

- 项目维护者: MM_Logic Team
- 邮箱: support@mm-logic.com
- 项目地址: https://github.com/mm-logic/mm-strategy

## 更新日志

### v1.0.0 (2024-01-01)
- 初始版本发布
- 完整的被动做市策略实现
- 事件驱动架构
- 完整的测试覆盖
- 详细的文档说明 