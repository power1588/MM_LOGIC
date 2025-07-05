from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

@dataclass
class StrategyConfig:
    """策略配置"""
    symbol: str
    min_spread: Decimal  # 0.002 (0.2%)
    max_spread: Decimal  # 0.004 (0.4%)
    min_order_value: Decimal  # 10000 USDT
    target_orders_per_side: int  # 1
    drift_threshold: Decimal  # 0.005 (0.5%)
    rebalance_interval: int  # 秒
    
@dataclass
class PriceConfig:
    """价格计算配置"""
    method: str  # 'TWAP', 'VWAP', 'EMA', 'Hybrid'
    window_size: int  # 数据窗口大小
    smoothing_factor: float  # 平滑因子
    change_threshold: Decimal  # 价格变化阈值
    anomaly_threshold: Decimal  # 异常价格阈值
    
@dataclass
class ExecutionConfig:
    """执行配置"""
    symbol: str
    worker_count: int
    batch_size: int
    rate_limit: int  # 每秒请求数
    max_retries: int
    retry_delay: float
    
@dataclass
class RiskConfig:
    """风险配置"""
    max_position: Decimal  # 最大持仓
    max_order_count: int  # 最大订单数
    max_daily_loss: Decimal  # 最大日损失
    max_price_change: Decimal  # 最大价格变化
    check_interval: int  # 检查间隔
    
@dataclass
class MasterConfig:
    """主配置"""
    strategy: StrategyConfig
    price: PriceConfig
    execution: ExecutionConfig
    risk: RiskConfig
    
    # API配置
    api_key: str
    api_secret: str
    testnet: bool
    
    # 系统配置
    log_level: str
    log_file: str
    metrics_enabled: bool
