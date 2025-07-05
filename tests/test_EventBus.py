import pytest
import pytest_asyncio
import asyncio
from src.core.events.EventBus import EventBus, EventBusStats
from src.core.events.EventType import EventType, PriceUpdateEvent
from decimal import Decimal

class TestEventBus:
    @pytest_asyncio.fixture
    async def event_bus(self):
        """创建事件总线实例"""
        bus = EventBus()
        await bus.start()
        yield bus
        await bus.stop()
        
    @pytest.mark.asyncio
    async def test_event_bus_creation(self, event_bus):
        """测试事件总线创建"""
        assert event_bus is not None
        assert isinstance(event_bus.stats, EventBusStats)
        
    @pytest.mark.asyncio
    async def test_event_publishing(self, event_bus):
        """测试事件发布"""
        events_received = []
        
        async def test_handler(event):
            events_received.append(event)
            
        # 订阅事件
        await event_bus.subscribe(EventType.PRICE_UPDATE, test_handler)
        
        # 发布事件
        test_event = PriceUpdateEvent(
            event_type=EventType.PRICE_UPDATE,
            timestamp=1234567890,
            data={'test': 'data'},
            reference_price=Decimal('100'),
            price_change=Decimal('0.01'),
            confidence=0.99
        )
        
        await event_bus.publish(test_event)
        
        # 等待事件处理
        await asyncio.sleep(0.1)
        
        assert len(events_received) == 1
        assert events_received[0].data['test'] == 'data'
        
    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, event_bus):
        """测试多个订阅者"""
        handler1_events = []
        handler2_events = []
        
        async def handler1(event):
            handler1_events.append(event)
            
        async def handler2(event):
            handler2_events.append(event)
            
        # 订阅事件
        await event_bus.subscribe(EventType.PRICE_UPDATE, handler1)
        await event_bus.subscribe(EventType.PRICE_UPDATE, handler2)
        
        # 发布事件
        test_event = PriceUpdateEvent(
            event_type=EventType.PRICE_UPDATE,
            timestamp=1234567890,
            data={'test': 'data'},
            reference_price=Decimal('100'),
            price_change=Decimal('0.01'),
            confidence=0.99
        )
        
        await event_bus.publish(test_event)
        
        # 等待事件处理
        await asyncio.sleep(0.1)
        
        assert len(handler1_events) == 1
        assert len(handler2_events) == 1
        
    @pytest.mark.asyncio
    async def test_event_stats(self, event_bus):
        """测试事件统计"""
        async def test_handler(event):
            pass
            
        await event_bus.subscribe(EventType.PRICE_UPDATE, test_handler)
        
        # 发布多个事件
        for i in range(5):
            test_event = PriceUpdateEvent(
                event_type=EventType.PRICE_UPDATE,
                timestamp=1234567890 + i,
                data={'index': i},
                reference_price=Decimal('100'),
                price_change=Decimal('0.01'),
                confidence=0.99
            )
            await event_bus.publish(test_event)
            
        # 等待事件处理
        await asyncio.sleep(0.1)
        
        assert event_bus.stats.events_published == 5
        assert event_bus.stats.events_processed == 5
        assert event_bus.stats.avg_processing_time >= 0 