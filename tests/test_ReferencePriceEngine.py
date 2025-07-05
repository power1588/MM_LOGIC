import pytest
from decimal import Decimal
from unittest.mock import Mock
from src.strategy.engines.ReferencePriceEngine import ReferencePriceEngine
import asyncio
from src.core.events.EventBus import EventBus
from src.core.events.EventType import PriceUpdateEvent, EventType

class TestReferencePriceEngine:
    """测试参考价格引擎"""
    
    @pytest.fixture
    def price_config(self):
        """创建价格配置"""
        class MockPriceConfig:
            def __init__(self):
                self.method = "HYBRID"
                self.window_size = 100
                self.smoothing_factor = 0.1
                self.change_threshold = Decimal("0.001")
                self.anomaly_threshold = Decimal("0.05")
        return MockPriceConfig()
        
    @pytest.fixture
    def price_engine(self, price_config):
        """创建价格引擎实例"""
        return ReferencePriceEngine(price_config)
        
    @pytest.fixture
    def mock_market_data(self):
        """创建模拟市场数据"""
        market_data = Mock()
        market_data.mid_price = Decimal("50000")
        market_data.recent_trades = []
        
        # 添加模拟交易数据
        for i in range(10):
            trade = Mock()
            trade.price = Decimal("50000") + Decimal(str(i * 10))
            trade.volume = Decimal("0.1")
            trade.timestamp = 1234567890 + i
            market_data.recent_trades.append(trade)
            
        return market_data
        
    def test_init(self, price_engine, price_config):
        """测试初始化"""
        assert price_engine.calculation_method == price_config.method
        assert price_engine.smoothing_factor == price_config.smoothing_factor
        assert price_engine.change_threshold == price_config.change_threshold
        assert price_engine.window_size == price_config.window_size
        
    @pytest.mark.asyncio
    async def test_calculate_reference_price_hybrid(self, price_engine, mock_market_data):
        """测试混合算法计算参考价格"""
        price_engine.calculation_method = "HYBRID"
        
        result = await price_engine.calculate_reference_price(mock_market_data)
        
        assert isinstance(result, Decimal)
        assert result > 0
        
    @pytest.mark.asyncio
    async def test_calculate_reference_price_vwap(self, price_engine, mock_market_data):
        """测试VWAP算法计算参考价格"""
        price_engine.calculation_method = "VWAP"
        
        result = await price_engine.calculate_reference_price(mock_market_data)
        
        assert isinstance(result, Decimal)
        assert result > 0
        
    @pytest.mark.asyncio
    async def test_calculate_reference_price_twap(self, price_engine, mock_market_data):
        """测试TWAP算法计算参考价格"""
        price_engine.calculation_method = "TWAP"
        
        result = await price_engine.calculate_reference_price(mock_market_data)
        
        assert isinstance(result, Decimal)
        assert result > 0
        
    def test_calculate_vwap_with_trades(self, price_engine, mock_market_data):
        """测试有交易数据的VWAP计算"""
        result = price_engine._calculate_vwap(mock_market_data)
        
        assert isinstance(result, Decimal)
        assert result > 0
        
        # 验证计算结果
        total_volume = sum(trade.volume for trade in mock_market_data.recent_trades)
        total_value = sum(trade.price * trade.volume for trade in mock_market_data.recent_trades)
        expected_vwap = total_value / total_volume
        
        assert abs(result - expected_vwap) < Decimal("0.01")
        
    def test_calculate_vwap_no_trades(self, price_engine):
        """测试无交易数据的VWAP计算"""
        market_data = Mock()
        market_data.recent_trades = []
        market_data.mid_price = Decimal("50000")
        
        result = price_engine._calculate_vwap(market_data)
        
        assert result == Decimal("50000")  # 应该返回中间价
        
    def test_calculate_twap_with_trades(self, price_engine, mock_market_data):
        """测试有交易数据的TWAP计算"""
        result = price_engine._calculate_twap(mock_market_data)
        
        assert isinstance(result, Decimal)
        assert result > 0
        
    def test_calculate_twap_no_trades(self, price_engine):
        """测试无交易数据的TWAP计算"""
        market_data = Mock()
        market_data.recent_trades = []
        market_data.mid_price = Decimal("50000")
        
        result = price_engine._calculate_twap(market_data)
        
        assert result == Decimal("50000")  # 应该返回中间价
        
    def test_calculate_twap_with_timestamps(self, price_engine):
        """测试带时间戳的TWAP计算"""
        market_data = Mock()
        market_data.mid_price = Decimal("50000")
        market_data.recent_trades = []
        
        # 添加带时间戳的交易
        for i in range(5):
            trade = Mock()
            trade.price = Decimal("50000") + Decimal(str(i * 10))
            trade.volume = Decimal("0.1")
            trade.timestamp = 1234567890 + i
            market_data.recent_trades.append(trade)
            
        result = price_engine._calculate_twap(market_data)
        
        assert isinstance(result, Decimal)
        assert result > 0
        
    def test_calculate_twap_without_timestamps(self, price_engine):
        """测试无时间戳的TWAP计算"""
        market_data = Mock()
        market_data.mid_price = Decimal("50000")
        market_data.recent_trades = []
        
        # 添加无时间戳的交易
        for i in range(5):
            trade = Mock()
            trade.price = Decimal("50000") + Decimal(str(i * 10))
            trade.volume = Decimal("0.1")
            # 不设置timestamp
            market_data.recent_trades.append(trade)
            
        result = price_engine._calculate_twap(market_data)
        
        assert isinstance(result, Decimal)
        assert result > 0
        
    @pytest.mark.asyncio
    async def test_hybrid_calculation_weights(self, price_engine, mock_market_data):
        """测试混合算法的权重分配"""
        price_engine.calculation_method = "HYBRID"
        
        # 模拟TWAP和VWAP的计算结果
        price_engine._calculate_twap = Mock(return_value=Decimal("50100"))
        price_engine._calculate_vwap = Mock(return_value=Decimal("50200"))
        
        result = await price_engine.calculate_reference_price(mock_market_data)
        
        # 验证权重计算: 0.6 * 50100 + 0.4 * 50200 = 50140
        expected_result = Decimal("50140")
        assert abs(result - expected_result) < Decimal("0.01")
        
    def test_market_data_attributes(self, price_engine, mock_market_data):
        """测试市场数据属性访问"""
        # 测试访问recent_trades
        assert hasattr(mock_market_data, 'recent_trades')
        assert len(mock_market_data.recent_trades) > 0
        
        # 测试访问mid_price
        assert hasattr(mock_market_data, 'mid_price')
        assert mock_market_data.mid_price > 0
        
    def test_trade_attributes(self, price_engine, mock_market_data):
        """测试交易数据属性"""
        trade = mock_market_data.recent_trades[0]
        
        # 测试交易属性
        assert hasattr(trade, 'price')
        assert hasattr(trade, 'volume')
        assert hasattr(trade, 'timestamp')
        
        assert trade.price > 0
        assert trade.volume > 0
        assert trade.timestamp > 0

@pytest.mark.asyncio
async def test_twap_calculation():
    event_bus = EventBus()
    await event_bus.start()
    config = type('Config', (), {'twap_window': 3, 'confidence_threshold': 0.95, 'max_price_deviation': 0.05})()
    engine = ReferencePriceEngine(config, event_bus)
    # 模拟价格流
    await engine.on_market_price(Decimal('100'))
    await engine.on_market_price(Decimal('102'))
    await engine.on_market_price(Decimal('104'))
    twap = engine._calculate_twap()
    assert twap == Decimal('102')
    await event_bus.stop()

@pytest.mark.asyncio
async def test_price_update_event():
    event_bus = EventBus()
    await event_bus.start()
    config = type('Config', (), {'twap_window': 2, 'confidence_threshold': 0.95, 'max_price_deviation': 0.05})()
    engine = ReferencePriceEngine(config, event_bus)
    received = []
    async def handler(event):
        received.append(event)
    await event_bus.subscribe(EventType.PRICE_UPDATE, handler)
    await engine.on_market_price(Decimal('100'))
    await engine.on_market_price(Decimal('102'))
    await asyncio.sleep(0.1)
    assert any(isinstance(e, PriceUpdateEvent) for e in received)
    await event_bus.stop() 