from decimal import Decimal
from typing import List
from ...core.orders.OrderState import OrderManager
from ...core.orders.OrderAnalysis import OrderAnalysis
from ...core.orders.OrderDecision import CancelOrderDecision, PlaceOrderDecision, OrderDecision
import random

class StrategyEngine:
    def __init__(self, config, event_bus, order_manager):
        self.config = config
        self.event_bus = event_bus
        self.order_manager = order_manager
        self.min_spread = Decimal(str(config.min_spread))  # 0.002 (0.2%)
        self.max_spread = Decimal(str(config.max_spread))  # 0.004 (0.4%)
        self.min_order_value = Decimal(str(config.min_order_value))  # 10000 USDT
        self.drift_threshold = Decimal(str(config.drift_threshold))  # 0.005 (0.5%)
        self.target_orders_per_side = config.target_orders_per_side  # 1
        
    async def on_price_update(self, price_event) -> None:
        """处理价格更新事件"""
        new_price = price_event.reference_price
        
        # 1. 分析当前订单状态
        analysis = await self._analyze_current_orders(new_price)
        
        # 2. 生成订单调整决策
        decisions = await self._generate_order_decisions(analysis, new_price)
        
        # 3. 发布决策事件
        for decision in decisions:
            await self.event_bus.publish(decision)
            
    async def _analyze_current_orders(self, reference_price: Decimal) -> OrderAnalysis:
        """分析当前订单状态"""
        active_orders = await self.order_manager.get_active_orders()
        
        analysis = OrderAnalysis()
        
        for order in active_orders:
            # 计算价格偏差
            price_deviation = abs(order.price - reference_price) / reference_price
            
            # 检查是否需要调整
            if price_deviation > self.drift_threshold:
                analysis.orders_to_cancel.append(order.order_id)
            elif price_deviation < (self.min_spread * Decimal('0.8')):  # 过于接近
                analysis.orders_to_cancel.append(order.order_id)
                
        # 检查订单数量
        bid_count = len([o for o in active_orders if o.side == 'BUY'])
        ask_count = len([o for o in active_orders if o.side == 'SELL'])
        
        analysis.need_bid_orders = max(0, self.target_orders_per_side - bid_count)
        analysis.need_ask_orders = max(0, self.target_orders_per_side - ask_count)
        
        return analysis
        
    async def _generate_order_decisions(self, analysis: OrderAnalysis, 
                                      reference_price: Decimal) -> List['OrderDecision']:
        """生成订单决策"""
        decisions = []
        
        # 1. 撤单决策
        for order_id in analysis.orders_to_cancel:
            decisions.append(CancelOrderDecision(order_id=order_id))
            
        # 2. 发单决策 - 优化订单位置以降低成交风险
        if analysis.need_bid_orders > 0:
            # 买单放置在区间较低位置，降低成交风险
            optimal_bid_price = reference_price * (Decimal('1') - self.max_spread * Decimal('0.8'))
            quantity = self._calculate_order_quantity(optimal_bid_price)
            
            decisions.append(PlaceOrderDecision(
                side='BUY',
                price=optimal_bid_price,
                quantity=quantity
            ))
            
        if analysis.need_ask_orders > 0:
            # 卖单放置在区间较高位置，降低成交风险
            optimal_ask_price = reference_price * (Decimal('1') + self.max_spread * Decimal('0.8'))
            quantity = self._calculate_order_quantity(optimal_ask_price)
            
            decisions.append(PlaceOrderDecision(
                side='SELL',
                price=optimal_ask_price,
                quantity=quantity
            ))
            
        return decisions
        
    def _calculate_order_quantity(self, price: Decimal) -> Decimal:
        """计算订单数量，确保满足最小价值要求"""
        base_quantity = self.min_order_value / price
        # 添加少量随机性，避免订单过于规整
        randomness = Decimal(str(random.uniform(0.95, 1.05)))
        quantity = base_quantity * randomness
        # 保证订单价值不低于最小要求
        if quantity * price < self.min_order_value:
            quantity = (self.min_order_value / price).quantize(Decimal('0.00000001'))
        return quantity
