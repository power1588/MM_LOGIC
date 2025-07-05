import pytest
import pytest_asyncio
import asyncio
from src.core.orders.OrderState import OrderManager, OrderState, OrderStatus
from src.core.events.EventBus import EventBus
from decimal import Decimal
import time
from unittest.mock import Mock, AsyncMock

@pytest_asyncio.fixture
async def event_bus():
    bus = EventBus()
    await bus.start()
    yield bus
    await bus.stop()

@pytest_asyncio.fixture
async def order_manager(event_bus):
    return OrderManager(event_bus)

@pytest.mark.asyncio
async def test_add_and_get_order(order_manager):
    order = OrderState(
        order_id="1",
        client_order_id="c1",
        symbol="BTCUSDT",
        side="BUY",
        price=Decimal('100'),
        original_quantity=Decimal('1'),
        executed_quantity=Decimal('0'),
        status=OrderStatus.PENDING_NEW,
        create_time=time.time(),
        update_time=time.time(),
        last_event_time=time.time()
    )
    await order_manager.add_order(order)
    result = await order_manager.get_order_by_id("1")
    assert result.order_id == "1"
    assert result.status == OrderStatus.PENDING_NEW

@pytest.mark.asyncio
async def test_update_order_status(order_manager):
    order = OrderState(
        order_id="2",
        client_order_id="c2",
        symbol="BTCUSDT",
        side="SELL",
        price=Decimal('200'),
        original_quantity=Decimal('2'),
        executed_quantity=Decimal('0'),
        status=OrderStatus.PENDING_NEW,
        create_time=time.time(),
        update_time=time.time(),
        last_event_time=time.time()
    )
    await order_manager.add_order(order)
    await order_manager.update_order_status("2", OrderStatus.ACTIVE, executed_qty=Decimal('1'))
    result = await order_manager.get_order_by_id("2")
    assert result.status == OrderStatus.ACTIVE
    assert result.executed_quantity == Decimal('1')

@pytest.mark.asyncio
async def test_get_active_orders(order_manager):
    order1 = OrderState(
        order_id="3",
        client_order_id="c3",
        symbol="BTCUSDT",
        side="BUY",
        price=Decimal('300'),
        original_quantity=Decimal('3'),
        executed_quantity=Decimal('0'),
        status=OrderStatus.ACTIVE,
        create_time=time.time(),
        update_time=time.time(),
        last_event_time=time.time()
    )
    order2 = OrderState(
        order_id="4",
        client_order_id="c4",
        symbol="BTCUSDT",
        side="SELL",
        price=Decimal('400'),
        original_quantity=Decimal('4'),
        executed_quantity=Decimal('0'),
        status=OrderStatus.FILLED,
        create_time=time.time(),
        update_time=time.time(),
        last_event_time=time.time()
    )
    await order_manager.add_order(order1)
    await order_manager.add_order(order2)
    active_orders = await order_manager.get_active_orders()
    assert any(o.order_id == "3" for o in active_orders)
    assert all(o.status == OrderStatus.ACTIVE or o.status == OrderStatus.PARTIALLY_FILLED for o in active_orders)

@pytest.fixture
def sample_order():
    """创建示例订单"""
    return OrderState(
        order_id="test_order_123",
        client_order_id="client_123",
        symbol="BTCUSDT",
        side="BUY",
        price=Decimal("50000"),
        original_quantity=Decimal("0.1"),
        executed_quantity=Decimal("0"),
        status=OrderStatus.PENDING_NEW,
        create_time=1234567890.0,
        update_time=1234567890.0,
        last_event_time=1234567890.0
    )

@pytest.mark.asyncio
async def test_add_order(order_manager, sample_order):
    """测试添加订单"""
    order_manager.event_bus.publish = AsyncMock()
    await order_manager.add_order(sample_order)
    
    # 检查订单是否被添加
    retrieved_order = await order_manager.get_order_by_id("test_order_123")
    assert retrieved_order is not None
    assert retrieved_order.symbol == "BTCUSDT"
    assert retrieved_order.side == "BUY"
    
    # 检查客户端订单映射
    assert "client_123" in order_manager.client_order_mapping
    assert order_manager.client_order_mapping["client_123"] == "test_order_123"
    
    # 检查事件发布
    order_manager.event_bus.publish.assert_called_once()
    
@pytest.mark.asyncio
async def test_update_order_with_executed_quantity(order_manager, sample_order):
    """测试更新订单执行数量"""
    await order_manager.add_order(sample_order)
    
    # 更新执行数量
    await order_manager.update_order_status(
        "test_order_123",
        OrderStatus.PARTIALLY_FILLED,
        executed_qty=Decimal("0.05")
    )
    
    # 检查执行数量
    updated_order = await order_manager.get_order_by_id("test_order_123")
    assert updated_order.executed_quantity == Decimal("0.05")
    assert updated_order.remaining_quantity == Decimal("0.05")
    
@pytest.mark.asyncio
async def test_get_orders_by_price_range(order_manager):
    """测试按价格范围获取订单"""
    # 创建不同价格的订单
    order1 = OrderState(
        order_id="order1",
        client_order_id="client1",
        symbol="BTCUSDT",
        side="BUY",
        price=Decimal("50000"),
        original_quantity=Decimal("0.1"),
        executed_quantity=Decimal("0"),
        status=OrderStatus.ACTIVE,
        create_time=1234567890.0,
        update_time=1234567890.0,
        last_event_time=1234567890.0
    )
    
    order2 = OrderState(
        order_id="order2",
        client_order_id="client2",
        symbol="BTCUSDT",
        side="BUY",
        price=Decimal("51000"),
        original_quantity=Decimal("0.1"),
        executed_quantity=Decimal("0"),
        status=OrderStatus.ACTIVE,
        create_time=1234567890.0,
        update_time=1234567890.0,
        last_event_time=1234567890.0
    )
    
    await order_manager.add_order(order1)
    await order_manager.add_order(order2)
    
    # 获取价格范围内的订单
    orders = await order_manager.get_orders_by_price_range(
        Decimal("49000"), Decimal("50500")
    )
    assert len(orders) == 1
    assert orders[0].order_id == "order1"
    
@pytest.mark.asyncio
async def test_order_properties(sample_order):
    """测试订单属性"""
    # 测试剩余数量
    assert sample_order.remaining_quantity == Decimal("0.1")
    
    # 测试是否活跃
    assert sample_order.is_active == False  # PENDING_NEW不是活跃状态
    
    sample_order.status = OrderStatus.ACTIVE
    assert sample_order.is_active == True
    
    # 测试订单价值
    assert sample_order.order_value == Decimal("5000")  # 50000 * 0.1
    
@pytest.mark.asyncio
async def test_archive_completed_order(order_manager, sample_order):
    """测试归档已完成订单"""
    await order_manager.add_order(sample_order)
    
    # 完成订单
    await order_manager.update_order_status(
        "test_order_123",
        OrderStatus.FILLED
    )
    
    # 检查订单是否被归档
    # 注意：归档是异步的，需要等待
    await asyncio.sleep(0.1)
    
    # 订单应该还在（因为延迟清理）
    order = await order_manager.get_order_by_id("test_order_123")
    assert order is not None
    
@pytest.mark.asyncio
async def test_get_nonexistent_order(order_manager):
    """测试获取不存在的订单"""
    order = await order_manager.get_order_by_id("nonexistent")
    assert order is None 