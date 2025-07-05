from ..events.EventType import BaseEvent, EventType
from decimal import Decimal
from typing import Optional
import uuid

class OrderDecision(BaseEvent):
    """订单决策基类"""
    def __init__(self, event_type: EventType, timestamp=None, data=None):
        super().__init__(event_type=event_type, timestamp=timestamp, data=data or {})
        self.correlation_id = str(uuid.uuid4())

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

class ModifyOrderDecision(OrderDecision):
    def __init__(self, order_id: str, new_price: Optional[Decimal] = None, 
                 new_quantity: Optional[Decimal] = None, priority: int = 3):
        super().__init__(
            event_type=EventType.ORDER_MODIFY,
            timestamp=None,
            data={
                'order_id': order_id,
                'new_price': str(new_price) if new_price else None,
                'new_quantity': str(new_quantity) if new_quantity else None
            },
        )
        self.order_id = order_id
        self.new_price = new_price
        self.new_quantity = new_quantity
        self.priority = priority 