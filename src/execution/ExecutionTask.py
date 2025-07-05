from dataclasses import dataclass
from typing import Optional, Dict, Any
from ..core.orders.OrderManager import OrderState

@dataclass
class ExecutionTask:
    """执行任务"""
    task_type: str  # 'PLACE_ORDER', 'CANCEL_ORDER', 'MODIFY_ORDER'
    order_data: Optional[OrderState] = None
    modify_data: Optional[Dict[str, Any]] = None  # 改单数据
    retry_count: int = 0
    priority: int = 5  # 1-10，数字越小优先级越高
    created_time: float = None
    
    def __post_init__(self):
        if self.created_time is None:
            import time
            self.created_time = time.time() 