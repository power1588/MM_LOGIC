import asyncio
import time
import logging
from decimal import Decimal
from ...core.orders.OrderState import OrderStatus
from ...core.events.EventBus import EventBus
from .RiskConfig import RiskConfig
from .RiskLevel import RiskLevel
from ...core.events.EventType import OrderStatusEvent, PriceUpdateEvent, BaseEvent, EventType
import uuid

class RiskEvent(BaseEvent):
    """风险事件"""
    correlation_id: str = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())
    def __init__(self, risk_type: str, risk_level: RiskLevel, details: dict, **kwargs):
        super().__init__(
            event_type=EventType.RISK_WARNING,
            timestamp=time.time(),
            data={'risk_type': risk_type, 'risk_level': risk_level.value, 'details': details},
            **kwargs
        )
        self.__post_init__()

class EmergencyStopEvent(BaseEvent):
    """紧急停止事件"""
    correlation_id: str = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())
    def __init__(self, reason: str, timestamp: float, **kwargs):
        super().__init__(
            event_type=EventType.EMERGENCY_STOP,
            timestamp=timestamp,
            data={'reason': reason},
            **kwargs
        )
        self.__post_init__()

class CancelAllOrdersEvent(BaseEvent):
    """撤销所有订单事件"""
    correlation_id: str = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())
    def __init__(self, **kwargs):
        super().__init__(
            event_type=EventType.CANCEL_ALL_ORDERS,
            timestamp=time.time(),
            data={},
            **kwargs
        )
        self.__post_init__()

class TradeEvent(BaseEvent):
    """交易事件"""
    correlation_id: str = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())
    def __init__(self, symbol: str, price: Decimal, quantity: Decimal, side: str, **kwargs):
        super().__init__(
            event_type=EventType.ORDER_FILL,
            timestamp=time.time(),
            data={'symbol': symbol, 'price': float(price), 'quantity': float(quantity), 'side': side},
            **kwargs
        )
        self.__post_init__()

class RiskManager:
    def __init__(self, config: RiskConfig, event_bus: EventBus):
        self.config = config
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
        
        # 风险指标
        self.current_position = Decimal('0')
        self.unrealized_pnl = Decimal('0')
        self.daily_pnl = Decimal('0')
        self.order_count = 0
        self.last_price = None
        
        # 风险状态
        self.risk_level = RiskLevel.NORMAL
        self.emergency_mode = False
        
    async def start(self) -> None:
        """启动风险管理器"""
        # 订阅相关事件
        await self.event_bus.subscribe(EventType.ORDER_STATUS, self.on_order_status)
        await self.event_bus.subscribe(EventType.PRICE_UPDATE, self.on_price_update)
        await self.event_bus.subscribe(EventType.ORDER_FILL, self.on_trade)
        
        # 启动定期检查
        asyncio.create_task(self._periodic_risk_check())
        
    async def on_order_status(self, event: OrderStatusEvent) -> None:
        """处理订单状态事件"""
        if event.status == OrderStatus.FILLED:
            # 更新持仓
            if event.order_data.side == 'BUY':
                self.current_position += event.order_data.executed_quantity
            else:
                self.current_position -= event.order_data.executed_quantity
                
            # 检查持仓风险
            await self._check_position_risk()
            
    async def on_price_update(self, event: PriceUpdateEvent) -> None:
        """处理价格更新事件"""
        self.last_price = event.reference_price
        
        # 更新未实现盈亏
        if self.current_position != 0:
            self.unrealized_pnl = self.current_position * self.last_price
            
        # 检查价格风险
        await self._check_price_risk()
        
    async def on_trade(self, event: TradeEvent) -> None:
        """处理交易事件"""
        # 更新订单计数
        self.order_count += 1
        
    async def _check_position_risk(self) -> None:
        """检查持仓风险"""
        max_position = self.config.max_position
        
        if abs(self.current_position) > max_position:
            self.risk_level = RiskLevel.HIGH
            
            # 发布风险事件
            await self.event_bus.publish(RiskEvent(
                risk_type='POSITION_LIMIT_EXCEEDED',
                risk_level=RiskLevel.HIGH,
                details={
                    'current_position': float(self.current_position),
                    'max_position': float(max_position)
                }
            ))
            
            # 触发紧急措施
            await self._trigger_emergency_measures()
            
    async def _check_price_risk(self) -> None:
        """检查价格风险"""
        if self.last_price is None:
            return
            
        # 检查价格异常波动
        if hasattr(self, 'previous_price') and self.previous_price:
            price_change = abs(self.last_price - self.previous_price) / self.previous_price
            
            if price_change > self.config.max_price_change:
                self.risk_level = RiskLevel.HIGH
                
                await self.event_bus.publish(RiskEvent(
                    risk_type='PRICE_VOLATILITY_HIGH',
                    risk_level=RiskLevel.HIGH,
                    details={
                        'price_change': float(price_change),
                        'threshold': float(self.config.max_price_change)
                    }
                ))
                
        self.previous_price = self.last_price
        
    async def _trigger_emergency_measures(self) -> None:
        """触发紧急措施"""
        if self.emergency_mode:
            return
            
        self.emergency_mode = True
        
        # 发布紧急停止事件
        await self.event_bus.publish(EmergencyStopEvent(
            reason='RISK_LIMIT_EXCEEDED',
            timestamp=time.time()
        ))
        
        # 撤销所有订单
        await self.event_bus.publish(CancelAllOrdersEvent())
        
    async def _periodic_risk_check(self) -> None:
        """定期风险检查"""
        while True:
            try:
                await self._comprehensive_risk_check()
                await asyncio.sleep(self.config.check_interval)
            except Exception as e:
                self.logger.error(f"Risk check error: {e}")
                await asyncio.sleep(10)
                
    async def _comprehensive_risk_check(self) -> None:
        """综合风险检查"""
        # 检查订单数量
        if self.order_count > self.config.max_order_count:
            await self.event_bus.publish(RiskEvent(
                risk_type='ORDER_COUNT_EXCEEDED',
                risk_level=RiskLevel.MEDIUM,
                details={'order_count': self.order_count}
            ))
            
        # 检查日内盈亏
        if self.daily_pnl < -self.config.max_daily_loss:
            await self.event_bus.publish(RiskEvent(
                risk_type='DAILY_LOSS_EXCEEDED',
                risk_level=RiskLevel.HIGH,
                details={'daily_pnl': float(self.daily_pnl)}
            ))
