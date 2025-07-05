import asyncio
import logging
from typing import Dict, List, Callable, Any
from collections import defaultdict
import uuid
from .EventType import EventType, BaseEvent
import time

class EventBusStats:
    """事件总线统计"""
    def __init__(self):
        self.events_published = 0
        self.events_processed = 0
        self.events_failed = 0
        self.total_processing_time = 0.0
        self.avg_processing_time = 0.0
        self.max_processing_time = 0.0
        
    def add_processing_time(self, processing_time: float):
        """添加处理时间"""
        self.total_processing_time += processing_time
        self.avg_processing_time = self.total_processing_time / self.events_processed
        self.max_processing_time = max(self.max_processing_time, processing_time)

class EventBus:
    def __init__(self):
        self.subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self.event_queue = asyncio.Queue()
        self.processing_tasks = []
        self.stats = EventBusStats()
        self.logger = logging.getLogger(__name__)
        
    async def start(self, worker_count: int = 4) -> None:
        """启动事件总线"""
        for i in range(worker_count):
            task = asyncio.create_task(self._event_processor(f"processor-{i}"))
            self.processing_tasks.append(task)
            
    async def stop(self) -> None:
        """停止事件总线"""
        for task in self.processing_tasks:
            task.cancel()
            
        await asyncio.gather(*self.processing_tasks, return_exceptions=True)
        
    async def subscribe(self, event_type: EventType, callback: Callable) -> str:
        """订阅事件"""
        subscription_id = str(uuid.uuid4())
        self.subscribers[event_type].append({
            'id': subscription_id,
            'callback': callback
        })
        return subscription_id
        
    async def unsubscribe(self, event_type: EventType, subscription_id: str) -> None:
        """取消订阅"""
        self.subscribers[event_type] = [
            sub for sub in self.subscribers[event_type] 
            if sub['id'] != subscription_id
        ]
        
    async def publish(self, event: BaseEvent) -> None:
        """发布事件"""
        event.correlation_id = event.correlation_id or str(uuid.uuid4())
        await self.event_queue.put(event)
        self.stats.events_published += 1
        
    async def _event_processor(self, processor_name: str) -> None:
        """事件处理器"""
        while True:
            try:
                event = await self.event_queue.get()
                
                # 获取订阅者
                subscribers = self.subscribers.get(event.event_type, [])
                
                # 并行处理所有订阅者
                if subscribers:
                    tasks = []
                    for subscriber in subscribers:
                        task = asyncio.create_task(
                            self._handle_event(subscriber['callback'], event)
                        )
                        tasks.append(task)
                        
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                self.event_queue.task_done()
                self.stats.events_processed += 1
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Event processor {processor_name} error: {e}")
                await asyncio.sleep(0.1)
                
    async def _handle_event(self, callback: Callable, event: BaseEvent) -> None:
        """处理单个事件"""
        try:
            start_time = time.time()
            
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
                
            processing_time = time.time() - start_time
            self.stats.add_processing_time(processing_time)
            
        except Exception as e:
            self.logger.error(f"Event handler error: {e}")
            self.stats.events_failed += 1
