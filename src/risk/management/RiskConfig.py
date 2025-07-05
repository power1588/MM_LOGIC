from dataclasses import dataclass
from decimal import Decimal

@dataclass
class RiskConfig:
    """风险配置"""
    max_position: Decimal  # 最大持仓
    max_order_count: int  # 最大订单数
    max_daily_loss: Decimal  # 最大日损失
    max_price_change: Decimal  # 最大价格变化
    check_interval: int  # 检查间隔 