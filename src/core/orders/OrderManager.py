from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio
import time
from decimal import Decimal
import logging

class OrderStatus(Enum):
    PENDING_NEW = "PENDING_NEW"
    ACTIVE = "ACTIVE"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    PENDING_MODIFY = "PENDING_MODIFY"

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

@dataclass
class ModifyOrderRequest:
    """改单请求"""
    order_id: str
    new_price: Optional[Decimal] = None
    new_quantity: Optional[Decimal] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class OrderManager:
    def __init__(self, event_bus, reset_interval: int = 300):  # 默认5分钟重置
        self.orders: Dict[str, OrderState] = {}
        self.client_order_mapping: Dict[str, str] = {}
        self.event_bus = event_bus
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)
        
        # 定时重置相关
        self.reset_interval = reset_interval  # 重置间隔（秒）
        self.last_reset_time = time.time()
        self.reset_task = None
        
        # 改单相关
        self.pending_modifications: Dict[str, ModifyOrderRequest] = {}
        self.modification_lock = asyncio.Lock()
        
        # 启动定时重置任务
        self.reset_task = asyncio.create_task(self._periodic_reset())
        
    async def start(self):
        """启动订单管理器"""
        self.logger.info(f"订单管理器启动，重置间隔: {self.reset_interval}秒")
        
    async def stop(self):
        """停止订单管理器"""
        if self.reset_task:
            self.reset_task.cancel()
            try:
                await self.reset_task
            except asyncio.CancelledError:
                pass
        self.logger.info("订单管理器已停止")
        
    async def _periodic_reset(self):
        """定时重置任务"""
        while True:
            try:
                await asyncio.sleep(self.reset_interval)
                await self._perform_reset()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"定时重置任务异常: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再重试
                
    async def _perform_reset(self):
        """执行重置操作"""
        async with self._lock:
            current_time = time.time()
            active_orders = [o for o in self.orders.values() if o.is_active]
            
            if not active_orders:
                self.logger.info("没有活跃订单，跳过重置")
                return
                
            self.logger.info(f"开始定时重置，当前活跃订单数: {len(active_orders)}")
            
            # 发布重置事件
            from ..events.EventType import OrderResetEvent, EventType
            await self.event_bus.publish(OrderResetEvent(
                event_type=EventType.ORDER_RESET,
                timestamp=current_time,
                data={
                    'reset_reason': 'PERIODIC_RESET',
                    'active_orders_count': len(active_orders),
                    'reset_interval': self.reset_interval
                }
            ))
            
            # 标记所有活跃订单为待撤销状态
            for order in active_orders:
                order.status = OrderStatus.PENDING_CANCEL
                order.update_time = current_time
                
            self.last_reset_time = current_time
            self.logger.info(f"定时重置完成，标记了 {len(active_orders)} 个订单为待撤销状态")
            
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
                
    async def modify_order(self, order_id: str, new_price: Optional[Decimal] = None,
                          new_quantity: Optional[Decimal] = None) -> bool:
        """改单功能"""
        async with self._lock:
            if order_id not in self.orders:
                self.logger.warning(f"订单不存在: {order_id}")
                return False
                
            order = self.orders[order_id]
            
            # 检查订单是否可以改单
            if not order.is_active:
                self.logger.warning(f"订单状态不允许改单: {order_id}, 状态: {order.status}")
                return False
                
            # 检查是否有实际变化
            has_changes = False
            if new_price is not None and new_price != order.price:
                has_changes = True
            if new_quantity is not None and new_quantity != order.original_quantity:
                has_changes = True
                
            if not has_changes:
                self.logger.info(f"订单无需修改: {order_id}")
                return True
                
            # 创建改单请求
            modify_request = ModifyOrderRequest(
                order_id=order_id,
                new_price=new_price,
                new_quantity=new_quantity
            )
            
            # 添加到待处理队列
            async with self.modification_lock:
                self.pending_modifications[order_id] = modify_request
                
            # 更新订单状态为待修改
            order.status = OrderStatus.PENDING_MODIFY
            order.update_time = time.time()
            
            # 发布改单事件
            from ..events.EventType import OrderModifyEvent, EventType
            await self.event_bus.publish(OrderModifyEvent(
                event_type=EventType.ORDER_MODIFY,
                timestamp=time.time(),
                data={
                    'order_id': order_id,
                    'old_price': str(order.price),
                    'new_price': str(new_price) if new_price else None,
                    'old_quantity': str(order.original_quantity),
                    'new_quantity': str(new_quantity) if new_quantity else None,
                    'side': order.side,
                    'symbol': order.symbol
                }
            ))
            
            self.logger.info(f"改单请求已提交: {order_id}, 新价格: {new_price}, 新数量: {new_quantity}")
            return True
            
    async def apply_modification(self, order_id: str, success: bool) -> None:
        """应用改单结果"""
        async with self._lock:
            if order_id not in self.orders:
                return
                
            order = self.orders[order_id]
            
            if success:
                # 改单成功，更新订单信息
                modify_request = self.pending_modifications.get(order_id)
                if modify_request:
                    if modify_request.new_price is not None:
                        order.price = modify_request.new_price
                    if modify_request.new_quantity is not None:
                        order.original_quantity = modify_request.new_quantity
                        
                    order.status = OrderStatus.ACTIVE
                    order.update_time = time.time()
                    
                    self.logger.info(f"改单成功: {order_id}")
                    
                    # 发布改单成功事件
                    from ..events.EventType import OrderModifySuccessEvent, EventType
                    await self.event_bus.publish(OrderModifySuccessEvent(
                        event_type=EventType.ORDER_MODIFY_SUCCESS,
                        timestamp=time.time(),
                        data={
                            'order_id': order_id,
                            'new_price': str(order.price),
                            'new_quantity': str(order.original_quantity)
                        }
                    ))
            else:
                # 改单失败，恢复原状态
                order.status = OrderStatus.ACTIVE
                order.update_time = time.time()
                
                self.logger.warning(f"改单失败: {order_id}")
                
                # 发布改单失败事件
                from ..events.EventType import OrderModifyFailureEvent, EventType
                await self.event_bus.publish(OrderModifyFailureEvent(
                    event_type=EventType.ORDER_MODIFY_FAILURE,
                    timestamp=time.time(),
                    data={
                        'order_id': order_id,
                        'reason': 'EXCHANGE_REJECTED'
                    }
                ))
                
            # 清理待处理队列
            async with self.modification_lock:
                if order_id in self.pending_modifications:
                    del self.pending_modifications[order_id]
                    
    async def get_pending_modifications(self) -> List[ModifyOrderRequest]:
        """获取待处理的改单请求"""
        async with self.modification_lock:
            return list(self.pending_modifications.values())
            
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
            
    async def cancel_all_orders(self) -> List[str]:
        """撤销所有活跃订单"""
        async with self._lock:
            active_orders = [o for o in self.orders.values() if o.is_active]
            cancelled_ids = []
            
            for order in active_orders:
                order.status = OrderStatus.PENDING_CANCEL
                order.update_time = time.time()
                cancelled_ids.append(order.order_id)
                
            self.logger.info(f"撤销所有订单，共 {len(cancelled_ids)} 个")
            return cancelled_ids
            
    async def get_reset_stats(self) -> Dict:
        """获取重置统计信息"""
        current_time = time.time()
        active_orders = [o for o in self.orders.values() if o.is_active]
        
        return {
            'last_reset_time': self.last_reset_time,
            'next_reset_time': self.last_reset_time + self.reset_interval,
            'reset_interval': self.reset_interval,
            'active_orders_count': len(active_orders),
            'pending_modifications_count': len(self.pending_modifications),
            'time_since_last_reset': current_time - self.last_reset_time,
            'time_until_next_reset': max(0, (self.last_reset_time + self.reset_interval) - current_time)
        }
            
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