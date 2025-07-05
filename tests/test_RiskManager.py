import pytest
import pytest_asyncio
import asyncio
from src.risk.management.RiskManager import RiskManager, RiskEvent, EmergencyStopEvent, CancelAllOrdersEvent, TradeEvent
from src.risk.management.RiskConfig import RiskConfig
from src.risk.management.RiskLevel import RiskLevel
from src.core.events.EventBus import EventBus
from src.core.orders.OrderState import OrderState, OrderStatus
from src.core.events.EventType import OrderStatusEvent, PriceUpdateEvent, EventType
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
def risk_config():
    return RiskConfig(
        max_position=10,
        max_order_count=5,
        max_daily_loss=1000,
        max_price_change=0.1,
        check_interval=1
    )

@pytest.mark.asyncio
async def test_position_risk(risk_config):
    from unittest.mock import AsyncMock
    event_bus = AsyncMock()
    manager = RiskManager(risk_config, event_bus)
    await manager.start()
    # 模拟订单成交
    order = OrderState(
        order_id="1",
        client_order_id="client_1",
        symbol="BTCUSDT",
        side="BUY",
        price=Decimal('50000'),
        original_quantity=Decimal('20'),
        executed_quantity=Decimal('20'),
        status=OrderStatus.FILLED,
        create_time=time.time(),
        update_time=time.time(),
        last_event_time=time.time()
    )
    event = OrderStatusEvent(
        event_type=EventType.ORDER_STATUS,
        timestamp=time.time(),
        data={},
        order_id="1",
        status=OrderStatus.FILLED,
        order_data=order
    )
    await manager.on_order_status(event)
    await asyncio.sleep(0.1)
    
    # 检查是否有任何事件被发布
    assert event_bus.publish.called, "No events were published"
    
    # 获取所有发布的事件
    calls = event_bus.publish.call_args_list
    print(f"Published events: {len(calls)}")
    for i, call in enumerate(calls):
        event_obj = call.args[0]
        print(f"Event {i}: type={type(event_obj)}, event_type={getattr(event_obj, 'event_type', 'N/A')}, data={getattr(event_obj, 'data', {})}")
    
    # 检查是否有RiskEvent被发布
    risk_events = [call.args[0] for call in calls if hasattr(call.args[0], 'data') and call.args[0].data.get('risk_type') == 'POSITION_LIMIT_EXCEEDED']
    assert len(risk_events) > 0, "No POSITION_LIMIT_EXCEEDED risk event was published"

@pytest.mark.asyncio
async def test_price_risk(event_bus, risk_config):
    manager = RiskManager(risk_config, event_bus)
    await manager.start()
    # 模拟价格波动
    event1 = PriceUpdateEvent(
        event_type=EventType.PRICE_UPDATE,
        timestamp=time.time(),
        data={},
        reference_price=Decimal('100'),
        price_change=Decimal('0.01'),
        confidence=0.99
    )
    event2 = PriceUpdateEvent(
        event_type=EventType.PRICE_UPDATE,
        timestamp=time.time(),
        data={},
        reference_price=Decimal('120'),
        price_change=Decimal('0.2'),
        confidence=0.99
    )
    await manager.on_price_update(event1)
    await manager.on_price_update(event2)
    assert manager.risk_level == RiskLevel.HIGH

class TestRiskManager:
    """测试风险管理器"""
    
    @pytest.fixture
    def risk_config(self):
        """创建风险配置"""
        return RiskConfig(
            max_position=Decimal("1.0"),
            max_order_count=100,
            max_daily_loss=Decimal("1000"),
            max_price_change=Decimal("0.1"),  # 10%
            check_interval=5
        )
        
    @pytest_asyncio.fixture
    async def risk_manager(self, risk_config):
        """创建风险管理器实例"""
        event_bus = Mock(spec=EventBus)
        event_bus.publish = AsyncMock()
        manager = RiskManager(risk_config, event_bus)
        return manager
        
    @pytest.fixture
    def sample_order(self):
        """创建示例订单"""
        return OrderState(
            order_id="test_order",
            client_order_id="client_test",
            symbol="BTCUSDT",
            side="BUY",
            price=Decimal("50000"),
            original_quantity=Decimal("0.1"),
            executed_quantity=Decimal("0.1"),
            status=OrderStatus.FILLED,
            create_time=1234567890.0,
            update_time=1234567890.0,
            last_event_time=1234567890.0
        )
        
    @pytest.mark.asyncio
    async def test_position_risk_check_normal(self, risk_manager):
        """测试正常持仓风险检查"""
        # 设置正常持仓
        risk_manager.current_position = Decimal("0.5")
        
        await risk_manager._check_position_risk()
        
        # 不应该触发风险事件
        risk_manager.event_bus.publish.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_position_risk_check_exceeded(self, risk_manager):
        """测试持仓超限风险检查"""
        # 设置超限持仓
        risk_manager.current_position = Decimal("1.5")
        
        await risk_manager._check_position_risk()
        
        # 应该触发风险事件
        calls = risk_manager.event_bus.publish.call_args_list
        assert any(isinstance(call[0][0], RiskEvent) for call in calls)
        
    @pytest.mark.asyncio
    async def test_price_risk_check_normal(self, risk_manager):
        """测试正常价格风险检查"""
        risk_manager.last_price = Decimal("50000")
        risk_manager.previous_price = Decimal("50100")
        
        await risk_manager._check_price_risk()
        
        # 价格变化在正常范围内，不应该触发风险事件
        risk_manager.event_bus.publish.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_price_risk_check_volatility(self, risk_manager):
        """测试价格波动风险检查"""
        risk_manager.last_price = Decimal("60000")  # 大幅上涨
        risk_manager.previous_price = Decimal("50000")
        
        await risk_manager._check_price_risk()
        
        # 应该触发价格波动风险事件
        risk_manager.event_bus.publish.assert_called()
        call_args = risk_manager.event_bus.publish.call_args[0][0]
        assert isinstance(call_args, RiskEvent)
        assert call_args.data['risk_type'] == 'PRICE_VOLATILITY_HIGH'
        
    @pytest.mark.asyncio
    async def test_on_order_status_filled(self, risk_manager, sample_order):
        """测试订单成交事件处理"""
        # 创建订单状态事件
        order_event = OrderStatusEvent(
            event_type=EventType.ORDER_STATUS,
            timestamp=time.time(),
            data={},
            order_id="test_order",
            status=OrderStatus.FILLED,
            order_data=sample_order
        )
        
        await risk_manager.on_order_status(order_event)
        
        # 检查持仓更新
        assert risk_manager.current_position == Decimal("0.1")  # BUY订单增加持仓
        
    @pytest.mark.asyncio
    async def test_on_order_status_sell_filled(self, risk_manager, sample_order):
        """测试卖单成交事件处理"""
        # 修改为卖单
        sample_order.side = "SELL"
        
        order_event = OrderStatusEvent(
            event_type=EventType.ORDER_STATUS,
            timestamp=time.time(),
            data={},
            order_id="test_order",
            status=OrderStatus.FILLED,
            order_data=sample_order
        )
        
        await risk_manager.on_order_status(order_event)
        
        # 检查持仓更新
        assert risk_manager.current_position == Decimal("-0.1")  # SELL订单减少持仓
        
    @pytest.mark.asyncio
    async def test_on_price_update(self, risk_manager):
        """测试价格更新事件处理"""
        # 创建价格更新事件
        price_event = PriceUpdateEvent(
            event_type=None,
            timestamp=1234567890.0,
            data={},
            reference_price=Decimal("50000"),
            price_change=Decimal("0.01"),
            confidence=0.95
        )
        
        # 设置持仓
        risk_manager.current_position = Decimal("0.5")
        
        await risk_manager.on_price_update(price_event)
        
        # 检查价格和未实现盈亏更新
        assert risk_manager.last_price == Decimal("50000")
        assert risk_manager.unrealized_pnl == Decimal("25000")  # 0.5 * 50000
        
    @pytest.mark.asyncio
    async def test_on_trade(self, risk_manager):
        """测试交易事件处理"""
        # 创建交易事件
        trade_event = TradeEvent(
            symbol="BTCUSDT",
            price=Decimal("50000"),
            quantity=Decimal("0.1"),
            side="BUY"
        )
        
        await risk_manager.on_trade(trade_event)
        
        # 检查订单计数更新
        assert risk_manager.order_count == 1
        
    @pytest.mark.asyncio
    async def test_trigger_emergency_measures(self, risk_manager):
        """测试触发紧急措施"""
        # 触发紧急措施
        await risk_manager._trigger_emergency_measures()
        
        # 检查紧急模式
        assert risk_manager.emergency_mode == True
        
        # 检查事件发布
        calls = risk_manager.event_bus.publish.call_args_list
        assert len(calls) == 2
        
        # 检查紧急停止事件
        emergency_event = calls[0][0][0]
        assert isinstance(emergency_event, EmergencyStopEvent)
        assert emergency_event.data['reason'] == 'RISK_LIMIT_EXCEEDED'
        
        # 检查撤销所有订单事件
        cancel_event = calls[1][0][0]
        assert isinstance(cancel_event, CancelAllOrdersEvent)
        
    @pytest.mark.asyncio
    async def test_comprehensive_risk_check_order_count(self, risk_manager):
        """测试综合风险检查 - 订单数量"""
        # 设置超限订单数量
        risk_manager.order_count = 150
        
        await risk_manager._comprehensive_risk_check()
        
        # 应该触发订单数量风险事件
        risk_manager.event_bus.publish.assert_called()
        call_args = risk_manager.event_bus.publish.call_args[0][0]
        assert isinstance(call_args, RiskEvent)
        assert call_args.data['risk_type'] == 'ORDER_COUNT_EXCEEDED'
        
    @pytest.mark.asyncio
    async def test_comprehensive_risk_check_daily_loss(self, risk_manager):
        """测试综合风险检查 - 日内亏损"""
        # 设置超限日内亏损
        risk_manager.daily_pnl = Decimal("-1500")
        
        await risk_manager._comprehensive_risk_check()
        
        # 应该触发日内亏损风险事件
        risk_manager.event_bus.publish.assert_called()
        call_args = risk_manager.event_bus.publish.call_args[0][0]
        assert isinstance(call_args, RiskEvent)
        assert call_args.data['risk_type'] == 'DAILY_LOSS_EXCEEDED'
        
    @pytest.mark.asyncio
    async def test_risk_level_transitions(self, risk_manager):
        """测试风险等级转换"""
        # 初始状态
        assert risk_manager.risk_level == RiskLevel.NORMAL
        
        # 触发持仓风险
        risk_manager.current_position = Decimal("1.5")
        await risk_manager._check_position_risk()
        
        # 风险等级应该提升
        assert risk_manager.risk_level == RiskLevel.HIGH
        
    @pytest.mark.asyncio
    async def test_emergency_mode_prevention(self, risk_manager):
        """测试紧急模式防止重复触发"""
        # 设置紧急模式
        risk_manager.emergency_mode = True
        
        # 尝试触发紧急措施
        await risk_manager._trigger_emergency_measures()
        
        # 不应该再次发布事件
        risk_manager.event_bus.publish.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_price_risk_no_previous_price(self, risk_manager):
        """测试没有前一个价格时的价格风险检查"""
        risk_manager.last_price = Decimal("50000")
        # 不设置previous_price
        
        # 不应该抛出异常
        await risk_manager._check_price_risk()
        
        # 应该设置previous_price
        assert risk_manager.previous_price == Decimal("50000") 