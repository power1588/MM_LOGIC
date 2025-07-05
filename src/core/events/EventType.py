from enum import Enum, auto
from typing import Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal
import uuid

class EventType(Enum):
    # 市场数据事件
    MARKET_TRADE = auto()
    MARKET_DEPTH = auto()
    MARKET_TICKER = auto()
    
    # 价格事件
    PRICE_UPDATE = auto()
    PRICE_DEVIATION = auto()
    
    # 订单事件
    ORDER_STATUS = auto()
    ORDER_FILL = auto()
    ORDER_CANCEL = auto()
    ORDER_RESET = auto()  # 新增：订单重置事件
    ORDER_MODIFY = auto()  # 新增：改单事件
    ORDER_MODIFY_SUCCESS = auto()  # 新增：改单成功事件
    ORDER_MODIFY_FAILURE = auto()  # 新增：改单失败事件
    
    # 策略事件
    PLACE_ORDER = auto()
    CANCEL_ORDER = auto()
    CANCEL_ALL_ORDERS = auto()
    
    # 风险事件
    RISK_WARNING = auto()
    EMERGENCY_STOP = auto()
    
    # 系统事件
    SYSTEM_START = auto()
    SYSTEM_STOP = auto()
    HEARTBEAT = auto()

@dataclass
class BaseEvent:
    """基础事件类"""
    event_type: EventType
    timestamp: float
    data: Dict[str, Any]

@dataclass
class PriceUpdateEvent(BaseEvent):
    """价格更新事件"""
    reference_price: Decimal
    price_change: Decimal
    confidence: float
    correlation_id: Optional[str] = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())

@dataclass
class OrderStatusEvent(BaseEvent):
    """订单状态事件"""
    order_id: str
    status: str  # 使用字符串而不是OrderStatus枚举
    order_data: Dict[str, Any]  # 使用字典而不是OrderState对象
    old_status: Optional[str] = None
    correlation_id: Optional[str] = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())

@dataclass
class OrderResetEvent(BaseEvent):
    """订单重置事件"""
    correlation_id: Optional[str] = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())

@dataclass
class OrderModifyEvent(BaseEvent):
    """改单事件"""
    correlation_id: Optional[str] = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())

@dataclass
class OrderModifySuccessEvent(BaseEvent):
    """改单成功事件"""
    correlation_id: Optional[str] = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())

@dataclass
class OrderModifyFailureEvent(BaseEvent):
    """改单失败事件"""
    correlation_id: Optional[str] = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())

@dataclass
class PlaceOrderEvent(BaseEvent):
    """下单事件"""
    side: str
    price: Decimal
    quantity: Decimal
    priority: int = 5
    correlation_id: Optional[str] = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())

@dataclass
class CancelOrderEvent(BaseEvent):
    """撤单事件"""
    order_id: str
    priority: int = 1
    correlation_id: Optional[str] = None
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())
