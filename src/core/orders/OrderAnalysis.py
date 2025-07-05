from dataclasses import dataclass
from typing import List, Dict, Optional
from decimal import Decimal

@dataclass
class OrderAnalysis:
    """订单分析结果"""
    orders_to_cancel: List[str] = None  # 需要撤销的订单ID列表
    orders_to_modify: List[Dict] = None  # 需要改单的订单信息列表
    need_bid_orders: int = 0  # 需要的买单数量
    need_ask_orders: int = 0  # 需要的卖单数量
    spread_compliance: bool = True  # 价差合规性
    liquidity_sufficient: bool = True  # 流动性充足性
    
    def __post_init__(self):
        if self.orders_to_cancel is None:
            self.orders_to_cancel = []
        if self.orders_to_modify is None:
            self.orders_to_modify = [] 