from ..events.EventType import BaseEvent, EventType
from decimal import Decimal
from typing import Optional

class OrderDecision(BaseEvent):
    """订单决策基类"""
    pass

class PlaceOrderDecision(OrderDecision):
    def __init__(self, side: str, price: Decimal, quantity: Decimal, priority: int = 5):
        super().__init__(
            event_type=EventType.PLACE_ORDER,
            timestamp=None,
            data={},
        )
        self.side = side
        self.price = price
        self.quantity = quantity
        self.priority = priority

class CancelOrderDecision(OrderDecision):
    def __init__(self, order_id: str, priority: int = 1):
        super().__init__(
            event_type=EventType.CANCEL_ORDER,
            timestamp=None,
            data={},
        )
        self.order_id = order_id
        self.priority = priority 