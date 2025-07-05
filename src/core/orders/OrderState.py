from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio
import time
from decimal import Decimal

class OrderStatus(Enum):
    PENDING_NEW = "PENDING_NEW"
    ACTIVE = "ACTIVE"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

@dataclass
class OrderState:
    """订单状态对象"""
    order_id: str
    client_order_id: str
    symbol: str
    side: str
    price: Decimal
    original_quantity: Decimal
    executed_quantity: Decimal
    status: OrderStatus
    create_time: float
    update_time: float
    last_event_time: float
    
    @property
    def remaining_quantity(self) -> Decimal:
        return self.original_quantity - self.executed_quantity
        
    @property
    def is_active(self) -> bool:
        return self.status in [OrderStatus.ACTIVE, OrderStatus.PARTIALLY_FILLED]
        
    @property
    def order_value(self) -> Decimal:
        return self.price * self.original_quantity

class OrderManager:
    def __init__(self, event_bus):
        self.orders: Dict[str, OrderState] = {}
        self.client_order_mapping: Dict[str, str] = {}
        self.event_bus = event_bus
        self._lock = asyncio.Lock()
        
    async def add_order(self, order: OrderState) -> None:
        """添加新订单"""
        async with self._lock:
            self.orders[order.order_id] = order
            self.client_order_mapping[order.client_order_id] = order.order_id
            
            # 发布订单状态事件
            from ..events.EventType import OrderStatusEvent, EventType
            await self.event_bus.publish(OrderStatusEvent(
                event_type=EventType.ORDER_STATUS,
                timestamp=time.time(),
                data={},
                order_id=order.order_id,
                status=str(order.status),
                order_data={
                    'order_id': order.order_id,
                    'client_order_id': order.client_order_id,
                    'symbol': order.symbol,
                    'side': order.side,
                    'price': str(order.price),
                    'original_quantity': str(order.original_quantity),
                    'executed_quantity': str(order.executed_quantity),
                    'status': str(order.status),
                    'create_time': order.create_time,
                    'update_time': order.update_time,
                    'last_event_time': order.last_event_time
                }
            ))
            
    async def update_order_status(self, order_id: str, new_status: OrderStatus,
                                executed_qty: Decimal = None) -> None:
        """更新订单状态"""
        async with self._lock:
            if order_id not in self.orders:
                return
                
            order = self.orders[order_id]
            old_status = order.status
            
            order.status = new_status
            order.update_time = time.time()
            
            if executed_qty is not None:
                order.executed_quantity += executed_qty
                
            # 发布状态变更事件
            from ..events.EventType import OrderStatusEvent, EventType
            await self.event_bus.publish(OrderStatusEvent(
                event_type=EventType.ORDER_STATUS,
                timestamp=time.time(),
                data={},
                order_id=order_id,
                status=str(new_status),
                old_status=str(old_status),
                order_data={
                    'order_id': order.order_id,
                    'client_order_id': order.client_order_id,
                    'symbol': order.symbol,
                    'side': order.side,
                    'price': str(order.price),
                    'original_quantity': str(order.original_quantity),
                    'executed_quantity': str(order.executed_quantity),
                    'status': str(order.status),
                    'create_time': order.create_time,
                    'update_time': order.update_time,
                    'last_event_time': order.last_event_time
                }
            ))
            
            # 清理已完成的订单
            if new_status in [OrderStatus.FILLED, OrderStatus.CANCELLED, 
                            OrderStatus.REJECTED, OrderStatus.EXPIRED]:
                await self._archive_order(order_id)
                
    async def get_active_orders(self, side: str = None) -> List[OrderState]:
        """获取活跃订单"""
        async with self._lock:
            active_orders = [
                order for order in self.orders.values()
                if order.is_active
            ]
            
            if side:
                active_orders = [o for o in active_orders if o.side == side]
                
            return active_orders
            
    async def get_orders_by_price_range(self, min_price: Decimal, 
                                      max_price: Decimal) -> List[OrderState]:
        """根据价格范围获取订单"""
        async with self._lock:
            return [
                order for order in self.orders.values()
                if order.is_active and min_price <= order.price <= max_price
            ]
            
    async def get_order_by_id(self, order_id: str) -> Optional[OrderState]:
        """根据订单ID获取订单"""
        async with self._lock:
            return self.orders.get(order_id)
            
    async def _archive_order(self, order_id: str) -> None:
        """归档已完成的订单"""
        if order_id in self.orders:
            order = self.orders[order_id]
            
            # 移除映射
            if order.client_order_id in self.client_order_mapping:
                del self.client_order_mapping[order.client_order_id]
                
            # 可以选择移除订单或保留一段时间
            # 这里选择保留2小时用于查询
            asyncio.create_task(self._cleanup_order_later(order_id, 7200))
            
    async def _cleanup_order_later(self, order_id: str, delay: int) -> None:
        """延迟清理订单"""
        await asyncio.sleep(delay)
        if order_id in self.orders:
            del self.orders[order_id]
