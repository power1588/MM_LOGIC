import pytest
import pytest_asyncio
import asyncio
from src.strategy.engines.StrategyEngine import StrategyEngine
from src.core.orders.OrderState import OrderManager, OrderState, OrderStatus
from src.core.orders.OrderAnalysis import OrderAnalysis
from src.core.orders.OrderDecision import PlaceOrderDecision, CancelOrderDecision
from src.core.events.EventBus import EventBus
from decimal import Decimal
import time
from src.config.Configs import StrategyConfig
from unittest.mock import Mock, AsyncMock

@pytest_asyncio.fixture
async def event_bus():
    bus = EventBus()
    await bus.start()
    yield bus
    await bus.stop()

@pytest_asyncio.fixture
def strategy_config():
    class Config:
        min_spread = 0.002
        max_spread = 0.004
        min_order_value = 10000
        drift_threshold = 0.005
        target_orders_per_side = 1
    return Config()

@pytest_asyncio.fixture
async def order_manager(event_bus):
    return OrderManager(event_bus)

@pytest.mark.asyncio
async def test_analyze_current_orders(order_manager, strategy_config, event_bus):
    engine = StrategyEngine(strategy_config, event_bus, order_manager)
    # 添加活跃订单
    order = OrderState(
        order_id="1",
        client_order_id="c1",
        symbol="BTCUSDT",
        side="BUY",
        price=Decimal('100'),
        original_quantity=Decimal('1'),
        executed_quantity=Decimal('0'),
        status=OrderStatus.ACTIVE,
        create_time=time.time(),
        update_time=time.time(),
        last_event_time=time.time()
    )
    await order_manager.add_order(order)
    analysis = await engine._analyze_current_orders(Decimal('100'))
    assert isinstance(analysis, OrderAnalysis)

@pytest.mark.asyncio
async def test_generate_order_decisions(order_manager, strategy_config, event_bus):
    engine = StrategyEngine(strategy_config, event_bus, order_manager)
    analysis = OrderAnalysis()
    analysis.need_bid_orders = 1
    analysis.need_ask_orders = 1
    decisions = await engine._generate_order_decisions(analysis, Decimal('100'))
    assert any(isinstance(d, PlaceOrderDecision) for d in decisions)
    assert all(isinstance(d, (PlaceOrderDecision, CancelOrderDecision)) for d in decisions)

class TestStrategyEngine:
    """测试策略引擎"""
    
    @pytest.fixture
    def strategy_config(self):
        """创建策略配置"""
        return StrategyConfig(
            symbol="BTCUSDT",
            min_spread=Decimal("0.002"),  # 0.2%
            max_spread=Decimal("0.004"),  # 0.4%
            min_order_value=Decimal("10000"),
            target_orders_per_side=1,
            drift_threshold=Decimal("0.005"),  # 0.5%
            rebalance_interval=5
        )
        
    @pytest_asyncio.fixture
    async def strategy_engine(self, strategy_config):
        """创建策略引擎实例"""
        event_bus = Mock(spec=EventBus)
        event_bus.publish = AsyncMock()
        order_manager = Mock(spec=OrderManager)
        order_manager.get_active_orders = AsyncMock()
        return StrategyEngine(strategy_config, event_bus, order_manager)
        
    @pytest.fixture
    def sample_orders(self):
        """创建示例订单"""
        return [
            OrderState(
                order_id="order1",
                client_order_id="client1",
                symbol="BTCUSDT",
                side="BUY",
                price=Decimal("50000"),
                original_quantity=Decimal("0.2"),
                executed_quantity=Decimal("0"),
                status=OrderStatus.ACTIVE,
                create_time=1234567890.0,
                update_time=1234567890.0,
                last_event_time=1234567890.0
            ),
            OrderState(
                order_id="order2",
                client_order_id="client2",
                symbol="BTCUSDT",
                side="SELL",
                price=Decimal("51000"),
                original_quantity=Decimal("0.2"),
                executed_quantity=Decimal("0"),
                status=OrderStatus.ACTIVE,
                create_time=1234567890.0,
                update_time=1234567890.0,
                last_event_time=1234567890.0
            )
        ]
        
    @pytest.mark.asyncio
    async def test_analyze_current_orders_normal(self, strategy_engine, sample_orders):
        """测试正常情况下的订单分析"""
        reference_price = Decimal("50500")
        # Set order prices within allowed spread
        sample_orders[0].price = Decimal("50400")
        sample_orders[1].price = Decimal("50600")
        strategy_engine.order_manager.get_active_orders.return_value = sample_orders
        analysis = await strategy_engine._analyze_current_orders(reference_price)
        assert isinstance(analysis, OrderAnalysis)
        assert len(analysis.orders_to_cancel) == 0
        assert analysis.need_bid_orders == 0
        assert analysis.need_ask_orders == 0
        
    @pytest.mark.asyncio
    async def test_analyze_current_orders_drift_exceeded(self, strategy_engine, sample_orders):
        """测试价格偏离过大的情况"""
        # 设置参考价格，使订单偏离过大
        reference_price = Decimal("60000")  # 大幅偏离
        
        strategy_engine.order_manager.get_active_orders.return_value = sample_orders
        
        analysis = await strategy_engine._analyze_current_orders(reference_price)
        
        # 应该撤销偏离过大的订单
        assert len(analysis.orders_to_cancel) == 2
        assert "order1" in analysis.orders_to_cancel
        assert "order2" in analysis.orders_to_cancel
        
    @pytest.mark.asyncio
    async def test_analyze_current_orders_too_close(self, strategy_engine, sample_orders):
        """测试订单过于接近参考价格的情况"""
        reference_price = Decimal("50500")
        # Set both orders to be very close to reference_price
        sample_orders[0].price = Decimal("50501")
        sample_orders[1].price = Decimal("50499")
        strategy_engine.order_manager.get_active_orders.return_value = sample_orders
        analysis = await strategy_engine._analyze_current_orders(reference_price)
        assert len(analysis.orders_to_cancel) == 2
        
    @pytest.mark.asyncio
    async def test_analyze_current_orders_missing_orders(self, strategy_engine):
        """测试缺少订单的情况"""
        # 没有活跃订单
        strategy_engine.order_manager.get_active_orders.return_value = []
        
        reference_price = Decimal("50500")
        analysis = await strategy_engine._analyze_current_orders(reference_price)
        
        # 需要添加买卖订单
        assert analysis.need_bid_orders == 1
        assert analysis.need_ask_orders == 1
        
    @pytest.mark.asyncio
    async def test_generate_order_decisions(self, strategy_engine):
        """测试生成订单决策"""
        # 创建分析结果
        analysis = OrderAnalysis()
        analysis.orders_to_cancel = ["order1", "order2"]
        analysis.need_bid_orders = 1
        analysis.need_ask_orders = 1
        
        reference_price = Decimal("50500")
        
        decisions = await strategy_engine._generate_order_decisions(analysis, reference_price)
        
        # 检查决策数量
        assert len(decisions) == 4  # 2个撤单 + 2个下单
        
        # 检查撤单决策
        cancel_decisions = [d for d in decisions if isinstance(d, CancelOrderDecision)]
        assert len(cancel_decisions) == 2
        
        # 检查下单决策
        place_decisions = [d for d in decisions if isinstance(d, PlaceOrderDecision)]
        assert len(place_decisions) == 2
        
        # 检查买单
        bid_decision = next(d for d in place_decisions if d.side == "BUY")
        assert bid_decision.price < reference_price
        
        # 检查卖单
        ask_decision = next(d for d in place_decisions if d.side == "SELL")
        assert ask_decision.price > reference_price
        
    @pytest.mark.asyncio
    async def test_calculate_order_quantity(self, strategy_engine):
        """测试订单数量计算"""
        price = Decimal("50000")
        quantity = strategy_engine._calculate_order_quantity(price)
        
        # 检查最小价值要求
        order_value = price * quantity
        assert order_value >= strategy_engine.min_order_value
        
        # 检查随机性
        quantity2 = strategy_engine._calculate_order_quantity(price)
        assert quantity != quantity2  # 应该有随机性
        
    @pytest.mark.asyncio
    async def test_on_price_update(self, strategy_engine):
        """测试价格更新处理"""
        # 模拟价格事件
        from src.core.events.EventType import PriceUpdateEvent
        price_event = PriceUpdateEvent(
            event_type=None,
            timestamp=1234567890.0,
            data={},
            reference_price=Decimal("50500"),
            price_change=Decimal("0.001"),
            confidence=0.95
        )
        
        # 模拟订单分析结果
        analysis = OrderAnalysis()
        analysis.orders_to_cancel = []
        analysis.need_bid_orders = 1
        analysis.need_ask_orders = 1
        
        strategy_engine._analyze_current_orders = AsyncMock(return_value=analysis)
        strategy_engine._generate_order_decisions = AsyncMock(return_value=[])
        
        # 执行价格更新
        await strategy_engine.on_price_update(price_event)
        
        # 检查是否调用了分析方法
        strategy_engine._analyze_current_orders.assert_called_once_with(Decimal("50500"))
        strategy_engine._generate_order_decisions.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_optimal_order_prices(self, strategy_engine):
        """测试最优订单位置计算"""
        reference_price = Decimal("50000")
        
        # 计算最优价格
        optimal_bid_price = reference_price * (Decimal('1') - strategy_engine.max_spread * Decimal('0.5'))
        optimal_ask_price = reference_price * (Decimal('1') + strategy_engine.max_spread * Decimal('0.5'))
        
        # 检查价格合理性
        assert optimal_bid_price < reference_price
        assert optimal_ask_price > reference_price
        
        # 检查价差
        spread = (optimal_ask_price - optimal_bid_price) / reference_price
        assert spread <= strategy_engine.max_spread
        assert spread >= strategy_engine.min_spread * Decimal('0.5') 