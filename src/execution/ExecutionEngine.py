import asyncio
import time
import random
import logging
from decimal import Decimal
from ..core.orders.OrderState import OrderState, OrderStatus
from ..core.orders.OrderManager import OrderManager
from .api.ExchangeAPI import ExchangeAPI
from ..core.events.EventBus import EventBus
from ..utils.limiting.RateLimiter import RateLimiter
from .ExecutionTask import ExecutionTask
from ..core.events.EventType import (
    PlaceOrderEvent, CancelOrderEvent, EventType,
    OrderResetEvent, OrderModifyEvent, OrderModifySuccessEvent, OrderModifyFailureEvent
)
from ..config.Configs import ExecutionConfig

class ExecutionEngine:
    def __init__(self, config: ExecutionConfig, event_bus: EventBus,
                 order_manager: OrderManager):
        self.config = config
        self.event_bus = event_bus
        self.order_manager = order_manager
        self.exchange_api = ExchangeAPI(
            api_key="",  # 从配置中获取
            api_secret="",  # 从配置中获取
            testnet=True  # 从配置中获取
        )
        self.symbol = config.symbol
        self.logger = logging.getLogger(__name__)
        
        # 执行队列
        self.execution_queue = asyncio.Queue()
        self.batch_size = config.batch_size
        self.rate_limiter = RateLimiter(config.rate_limit)
        
        # 改单相关
        self.modify_queue = asyncio.Queue()
        self.modify_worker_task = None
        
    async def start(self) -> None:
        """启动执行引擎"""
        # 启动执行工作器
        for i in range(self.config.worker_count):
            asyncio.create_task(self._execution_worker(f"worker-{i}"))
            
        # 启动改单工作器
        self.modify_worker_task = asyncio.create_task(self._modify_worker())
            
        # 启动批处理器
        asyncio.create_task(self._batch_processor())
        
        # 注册事件处理器
        await self.event_bus.subscribe(EventType.PLACE_ORDER, self.handle_place_order)
        await self.event_bus.subscribe(EventType.CANCEL_ORDER, self.handle_cancel_order)
        await self.event_bus.subscribe(EventType.ORDER_RESET, self.handle_order_reset)
        await self.event_bus.subscribe(EventType.ORDER_MODIFY, self.handle_order_modify)
        
    async def stop(self) -> None:
        """停止执行引擎"""
        if self.modify_worker_task:
            self.modify_worker_task.cancel()
            try:
                await self.modify_worker_task
            except asyncio.CancelledError:
                pass
        self.logger.info("执行引擎已停止")
        
    async def handle_place_order(self, event: PlaceOrderEvent) -> None:
        """处理下单请求"""
        # 生成客户端订单ID
        client_order_id = self._generate_client_order_id()
        
        # 创建订单状态对象
        order_state = OrderState(
            order_id="",  # 待交易所返回
            client_order_id=client_order_id,
            symbol=self.symbol,
            side=event.side,
            price=event.price,
            original_quantity=event.quantity,
            executed_quantity=Decimal('0'),
            status=OrderStatus.PENDING_NEW,
            create_time=time.time(),
            update_time=time.time(),
            last_event_time=time.time()
        )
        
        # 添加到订单管理器
        await self.order_manager.add_order(order_state)
        
        # 创建执行任务
        task = ExecutionTask(
            task_type='PLACE_ORDER',
            order_data=order_state,
            retry_count=0,
            priority=event.priority or 5
        )
        
        await self.execution_queue.put(task)
        
    async def handle_cancel_order(self, event: CancelOrderEvent) -> None:
        """处理撤单请求"""
        order = await self.order_manager.get_order_by_id(event.order_id)
        if not order or not order.is_active:
            return
            
        # 更新状态为待撤销
        await self.order_manager.update_order_status(
            event.order_id, OrderStatus.PENDING_CANCEL
        )
        
        # 创建执行任务
        task = ExecutionTask(
            task_type='CANCEL_ORDER',
            order_data=order,
            retry_count=0,
            priority=event.priority or 1  # 撤单优先级较高
        )
        
        await self.execution_queue.put(task)
        
    async def handle_order_reset(self, event: OrderResetEvent) -> None:
        """处理订单重置事件"""
        self.logger.info("收到订单重置事件，开始批量撤单")
        
        # 获取所有活跃订单
        active_orders = await self.order_manager.get_active_orders()
        
        # 批量创建撤单任务
        for order in active_orders:
            task = ExecutionTask(
                task_type='CANCEL_ORDER',
                order_data=order,
                retry_count=0,
                priority=1  # 重置撤单优先级最高
            )
            await self.execution_queue.put(task)
            
        self.logger.info(f"已创建 {len(active_orders)} 个撤单任务")
        
    async def handle_order_modify(self, event: OrderModifyEvent) -> None:
        """处理改单事件"""
        order_id = event.data.get('order_id')
        new_price = event.data.get('new_price')
        new_quantity = event.data.get('new_quantity')
        
        if not order_id:
            self.logger.error("改单事件缺少订单ID")
            return
            
        # 获取订单
        order = await self.order_manager.get_order_by_id(order_id)
        if not order:
            self.logger.error(f"订单不存在: {order_id}")
            return
            
        # 创建改单任务
        task = ExecutionTask(
            task_type='MODIFY_ORDER',
            order_data=order,
            modify_data={
                'new_price': new_price,
                'new_quantity': new_quantity
            },
            retry_count=0,
            priority=3  # 改单优先级中等
        )
        
        await self.modify_queue.put(task)
        
    async def _modify_worker(self) -> None:
        """改单工作器"""
        while True:
            try:
                task = await self.modify_queue.get()
                
                # 速率限制
                await self.rate_limiter.acquire()
                
                # 执行改单
                await self._execute_modify_order(task)
                
                self.modify_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Modify worker error: {e}")
                await asyncio.sleep(1)
                
    async def _execution_worker(self, worker_name: str) -> None:
        """执行工作器"""
        while True:
            try:
                task = await self.execution_queue.get()
                
                # 速率限制
                await self.rate_limiter.acquire()
                
                # 执行任务
                await self._execute_task(task, worker_name)
                
                self.execution_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(1)
                
    async def _batch_processor(self) -> None:
        """批处理器"""
        while True:
            try:
                # 处理批量任务
                await asyncio.sleep(0.1)  # 避免过度占用CPU
            except Exception as e:
                self.logger.error(f"Batch processor error: {e}")
                await asyncio.sleep(1)
                
    async def _execute_task(self, task: ExecutionTask, worker_name: str) -> None:
        """执行单个任务"""
        try:
            if task.task_type == 'PLACE_ORDER':
                await self._execute_place_order(task)
            elif task.task_type == 'CANCEL_ORDER':
                await self._execute_cancel_order(task)
                
        except Exception as e:
            self.logger.error(f"Task execution failed: {e}")
            
            # 重试逻辑
            if task.retry_count < self.config.max_retries:
                task.retry_count += 1
                await asyncio.sleep(self.config.retry_delay * (2 ** task.retry_count))
                await self.execution_queue.put(task)
            else:
                # 重试次数已达上限，标记为失败
                if task.task_type == 'PLACE_ORDER':
                    await self.order_manager.update_order_status(
                        task.order_data.client_order_id, OrderStatus.REJECTED
                    )
                    
    async def _execute_modify_order(self, task: ExecutionTask) -> None:
        """执行改单"""
        order_data = task.order_data
        modify_data = task.modify_data
        
        try:
            # 调用交易所改单API
            response = await self.exchange_api.modify_order(
                symbol=order_data.symbol,
                orderId=order_data.order_id,
                new_price=modify_data.get('new_price'),
                new_quantity=modify_data.get('new_quantity')
            )
            
            # 改单成功
            await self.order_manager.apply_modification(order_data.order_id, True)
            
            self.logger.info(f"改单成功: {order_data.order_id}")
            
        except Exception as e:
            self.logger.error(f"改单失败: {order_data.order_id}, 错误: {e}")
            
            # 改单失败
            await self.order_manager.apply_modification(order_data.order_id, False)
            
            # 重试逻辑
            if task.retry_count < self.config.max_retries:
                task.retry_count += 1
                await asyncio.sleep(self.config.retry_delay * (2 ** task.retry_count))
                await self.modify_queue.put(task)
                    
    async def _execute_place_order(self, task: ExecutionTask) -> None:
        """执行下单"""
        order_data = task.order_data
        
        response = await self.exchange_api.place_order(
            symbol=order_data.symbol,
            side=order_data.side,
            type='LIMIT',
            quantity=str(order_data.original_quantity),
            price=str(order_data.price),
            timeInForce='GTC',
            newClientOrderId=order_data.client_order_id
        )
        
        # 更新订单状态
        order_data.order_id = response['orderId']
        await self.order_manager.update_order_status(
            order_data.order_id, OrderStatus.ACTIVE
        )
        
    async def _execute_cancel_order(self, task: ExecutionTask) -> None:
        """执行撤单"""
        order_data = task.order_data
        
        await self.exchange_api.cancel_order(
            symbol=order_data.symbol,
            orderId=order_data.order_id
        )
        
        # 状态更新由WebSocket回报处理
        
    def _generate_client_order_id(self) -> str:
        """生成客户端订单ID"""
        timestamp = int(time.time() * 1000)
        random_suffix = random.randint(1000, 9999)
        return f"mm_{timestamp}_{random_suffix}"
