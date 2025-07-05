from decimal import Decimal
import time

class ReferencePriceEngine:
    def __init__(self, config, event_bus=None):
        self.config = config
        self.event_bus = event_bus
        self.calculation_method = getattr(config, 'method', 'HYBRID')
        self.smoothing_factor = getattr(config, 'smoothing_factor', 0.1)
        self.change_threshold = getattr(config, 'change_threshold', Decimal('0.001'))
        self.window_size = getattr(config, 'window_size', 10)
        self.twap_window = getattr(config, 'twap_window', 10)
        self.confidence_threshold = getattr(config, 'confidence_threshold', 0.95)
        self.max_price_deviation = getattr(config, 'max_price_deviation', 0.05)
        self.prices = []

    async def on_market_price(self, price: Decimal):
        self.prices.append(price)
        if len(self.prices) > self.twap_window:
            self.prices.pop(0)
        # Emit PriceUpdateEvent if event_bus is set
        if self.event_bus is not None:
            from src.core.events.EventType import PriceUpdateEvent, EventType
            event = PriceUpdateEvent(
                event_type=EventType.PRICE_UPDATE,
                timestamp=time.time(),
                data={},
                reference_price=price,
                price_change=Decimal('0'),
                confidence=self.confidence_threshold
            )
            await self.event_bus.publish(event)

    def _calculate_twap(self, market_data=None):
        # 支持传入market_data或用自身prices
        if market_data is not None:
            if not hasattr(market_data, 'recent_trades') or not market_data.recent_trades:
                return getattr(market_data, 'mid_price', Decimal('0'))
            total_time = Decimal('0')
            total_value = Decimal('0')
            for i, trade in enumerate(market_data.recent_trades):
                # 使用交易时间作为权重
                if hasattr(trade, 'timestamp') and trade.timestamp is not None:
                    try:
                        time_weight = Decimal(str(trade.timestamp))
                    except Exception:
                        time_weight = Decimal(i)
                else:
                    time_weight = Decimal(i)
                total_time += time_weight
                total_value += getattr(trade, 'price', Decimal('0')) * time_weight
            if total_time == 0:
                return getattr(market_data, 'mid_price', Decimal('0'))
            return total_value / total_time
        else:
            if not self.prices:
                return Decimal('0')
            return sum(self.prices) / Decimal(len(self.prices))

    async def calculate_reference_price(self, market_data) -> Decimal:
        # 混合算法：结合TWAP和VWAP
        if self.calculation_method == 'HYBRID':
            twap = self._calculate_twap(market_data)
            vwap = self._calculate_vwap(market_data)
            return (twap * Decimal('0.6') + vwap * Decimal('0.4'))
        elif self.calculation_method == 'VWAP':
            return self._calculate_vwap(market_data)
        elif self.calculation_method == 'TWAP':
            return self._calculate_twap(market_data)
        else:
            return self._calculate_twap(market_data)

    def _calculate_vwap(self, market_data):
        # 简单VWAP实现
        if not hasattr(market_data, 'recent_trades') or not market_data.recent_trades:
            return getattr(market_data, 'mid_price', Decimal('0'))
        total_volume = sum(getattr(trade, 'volume', Decimal('0')) for trade in market_data.recent_trades)
        if total_volume == 0:
            return getattr(market_data, 'mid_price', Decimal('0'))
        total_value = sum(getattr(trade, 'price', Decimal('0')) * getattr(trade, 'volume', Decimal('0')) for trade in market_data.recent_trades)
        return total_value / total_volume
