import asyncio
import ccxt.async_support as ccxt
from decimal import Decimal
import time
import signal
import sys
from typing import List, Dict, Optional
import json
from collections import deque

from src.core.events.EventBus import EventBus
from src.core.events.EventType import PriceUpdateEvent, EventType
from src.strategy.engines.StrategyEngine import StrategyEngine
from src.core.orders.OrderState import OrderManager, OrderState, OrderStatus
from src.risk.management.RiskManager import RiskManager
from src.risk.management.RiskConfig import RiskConfig
from src.config.Configs import StrategyConfig

# 全局变量用于控制程序退出
running = True

# 模拟订单存储
mock_orders: Dict[str, OrderState] = {}
order_counter = 0

# 市场数据缓存和历史数据
market_data = {
    'last_price': None,
    'bid_price': None,
    'ask_price': None,
    'bid_volume': None,
    'ask_volume': None,
    'last_update': None,
    'price_history': deque(maxlen=100),  # 保留最近100个价格
    'spread_history': deque(maxlen=100),  # 保留最近100个价差
    'volume_history': deque(maxlen=100),  # 保留最近100个成交量
}

class WebSocketMarketData:
    """WebSocket市场数据监听器"""
    
    def __init__(self, exchange, symbol):
        self.exchange = exchange
        self.symbol = symbol
        self.orderbook_cache = None
        self.trades_cache = []
        self.last_orderbook_update = 0
        self.last_trades_update = 0
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
    async def start_listening(self):
        """开始监听市场数据"""
        print(f"🔌 开始监听 {self.symbol} 的WebSocket数据...")
        
        # 并行启动orderbook和trades监听
        orderbook_task = asyncio.create_task(self._watch_orderbook())
        trades_task = asyncio.create_task(self._watch_trades())
        
        try:
            await asyncio.gather(orderbook_task, trades_task)
        except Exception as e:
            print(f"❌ WebSocket监听错误: {e}")
            
    async def _watch_orderbook(self):
        """监听orderbook数据"""
        while running:
            try:
                orderbook = await self.exchange.watch_order_book(self.symbol)
                
                if orderbook and orderbook['bids'] and orderbook['asks']:
                    await self._process_orderbook(orderbook)
                    self.last_orderbook_update = time.time()
                    self.reconnect_attempts = 0  # 重置重连计数
                    
            except Exception as e:
                print(f"❌ Orderbook监听错误: {e}")
                await self._handle_reconnect()
                
    async def _watch_trades(self):
        """监听trades数据"""
        while running:
            try:
                trades = await self.exchange.watch_trades(self.symbol)
                
                if trades and len(trades) > 0:
                    await self._process_trades(trades)
                    self.last_trades_update = time.time()
                    self.reconnect_attempts = 0  # 重置重连计数
                    
            except Exception as e:
                print(f"❌ Trades监听错误: {e}")
                await self._handle_reconnect()
                
    async def _process_orderbook(self, orderbook):
        """处理orderbook数据"""
        global market_data
        
        bid_price = Decimal(str(orderbook['bids'][0][0]))
        ask_price = Decimal(str(orderbook['asks'][0][0]))
        bid_volume = Decimal(str(orderbook['bids'][0][1]))
        ask_volume = Decimal(str(orderbook['asks'][0][1]))
        
        # 计算中间价格
        mid_price = (bid_price + ask_price) / Decimal('2')
        spread = (ask_price - bid_price) / mid_price
        
        # 更新市场数据
        market_data.update({
            'last_price': mid_price,
            'bid_price': bid_price,
            'ask_price': ask_price,
            'bid_volume': bid_volume,
            'ask_volume': ask_volume,
            'last_update': time.time()
        })
        
        # 添加到历史数据
        market_data['price_history'].append(mid_price)
        market_data['spread_history'].append(spread)
        
        # 缓存orderbook数据
        self.orderbook_cache = {
            'bid_price': bid_price,
            'ask_price': ask_price,
            'bid_volume': bid_volume,
            'ask_volume': ask_volume,
            'spread': spread,
            'timestamp': time.time()
        }
        
        print(f"📊 Orderbook更新 - Bid: {format_price(bid_price)} Ask: {format_price(ask_price)} Mid: {format_price(mid_price)} Spread: {float(spread*100):.3f}%")
        
    async def _process_trades(self, trades):
        """处理trades数据"""
        if not trades:
            return
            
        latest_trade = trades[-1]
        trade_price = Decimal(str(latest_trade['price']))
        trade_volume = Decimal(str(latest_trade['amount']))
        trade_side = latest_trade['side']
        
        # 添加到历史数据
        market_data['volume_history'].append(trade_volume)
        
        # 缓存最新trades
        self.trades_cache = trades[-10:]  # 保留最近10笔交易
        
        print(f"💱 最新成交 - {trade_side}: {format_price(trade_price)} × {format_quantity(trade_volume)}")
        
    async def _handle_reconnect(self):
        """处理重连逻辑"""
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts <= self.max_reconnect_attempts:
            wait_time = min(2 ** self.reconnect_attempts, 30)  # 指数退避
            print(f"🔄 尝试重连 ({self.reconnect_attempts}/{self.max_reconnect_attempts})，等待 {wait_time} 秒...")
            await asyncio.sleep(wait_time)
        else:
            print("❌ 重连次数超限，停止监听")
            global running
            running = False
            
    def get_market_summary(self):
        """获取市场数据摘要"""
        if not market_data['price_history']:
            return None
            
        prices = list(market_data['price_history'])
        spreads = list(market_data['spread_history'])
        volumes = list(market_data['volume_history'])
        
        if len(prices) < 2:
            return None
            
        # 计算价格变化
        price_change = (prices[-1] - prices[-2]) / prices[-2]
        
        # 计算平均价差
        avg_spread = sum(spreads) / len(spreads) if spreads else Decimal('0')
        
        # 计算平均成交量
        avg_volume = sum(volumes) / len(volumes) if volumes else Decimal('0')
        
        return {
            'current_price': prices[-1],
            'price_change': price_change,
            'avg_spread': avg_spread,
            'avg_volume': avg_volume,
            'data_points': len(prices)
        }

def signal_handler(signum, frame):
    """信号处理器，用于优雅退出"""
    global running
    print(f"\n收到退出信号 {signum}，正在优雅退出...")
    running = False

def create_mock_order(side: str, price: Decimal, quantity: Decimal) -> OrderState:
    """创建模拟订单"""
    global order_counter
    order_counter += 1
    order_id = f"mock_{order_counter}"
    
    order = OrderState(
        order_id=order_id,
        client_order_id=f"client_{order_id}",
        symbol="BTC/USDT",
        side=side,
        price=price,
        original_quantity=quantity,
        executed_quantity=Decimal('0'),
        status=OrderStatus.ACTIVE,
        create_time=time.time(),
        update_time=time.time(),
        last_event_time=time.time()
    )
    
    mock_orders[order_id] = order
    return order

def check_order_price_validity(order: OrderState, current_price: Decimal, min_spread: Decimal, max_spread: Decimal) -> bool:
    """检查订单价格是否在有效区间内"""
    price_deviation = abs(order.price - current_price) / current_price
    return min_spread <= price_deviation <= max_spread

def format_price(price: Decimal) -> str:
    """格式化价格显示"""
    return f"{float(price):.2f}"

def format_quantity(quantity: Decimal) -> str:
    """格式化数量显示"""
    return f"{float(quantity):.8f}"

def print_market_summary(summary):
    """打印市场摘要"""
    if not summary:
        return
        
    print(f"📈 市场摘要:")
    print(f"  当前价格: {format_price(summary['current_price'])}")
    print(f"  价格变化: {float(summary['price_change']*100):+.3f}%")
    print(f"  平均价差: {float(summary['avg_spread']*100):.3f}%")
    print(f"  平均成交量: {format_quantity(summary['avg_volume'])}")
    print(f"  数据点数: {summary['data_points']}")

def print_order_summary(current_price: Decimal):
    """打印订单汇总信息"""
    if not mock_orders:
        print("📋 当前无活跃订单")
        return
    
    print(f"📋 订单汇总 (当前价格: {format_price(current_price)})")
    print("─" * 80)
    
    bid_orders = [o for o in mock_orders.values() if o.side == 'BUY' and o.status == OrderStatus.ACTIVE]
    ask_orders = [o for o in mock_orders.values() if o.side == 'SELL' and o.status == OrderStatus.ACTIVE]
    
    # 按价格排序
    bid_orders.sort(key=lambda x: x.price, reverse=True)
    ask_orders.sort(key=lambda x: x.price)
    
    print("🔵 买单:")
    for order in bid_orders:
        price_valid = check_order_price_validity(order, current_price, Decimal('0.0002'), Decimal('0.002'))
        status_icon = "✅" if price_valid else "⚠️"
        print(f"  {status_icon} {order.order_id}: {format_price(order.price)} × {format_quantity(order.original_quantity)}")
    
    print("🔴 卖单:")
    for order in ask_orders:
        price_valid = check_order_price_validity(order, current_price, Decimal('0.0002'), Decimal('0.002'))
        status_icon = "✅" if price_valid else "⚠️"
        print(f"  {status_icon} {order.order_id}: {format_price(order.price)} × {format_quantity(order.original_quantity)}")
    
    print("─" * 80)

async def main():
    global running
    
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化ccxt
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot',
        }
    })
    symbol = 'BTC/USDT'

    # 初始化事件总线
    event_bus = EventBus()

    # 初始化订单管理、风控、策略
    order_manager = OrderManager(event_bus)
    risk_config = RiskConfig(max_position=Decimal('2'), max_order_count=10, max_daily_loss=Decimal('10000'), max_price_change=Decimal('0.05'), check_interval=5)
    risk_manager = RiskManager(risk_config, event_bus)
    strategy_config = StrategyConfig(
        symbol="BTC/USDT",
        min_spread=Decimal('0.0002'),
        max_spread=Decimal('0.002'),
        min_order_value=Decimal('10'),
        drift_threshold=Decimal('0.001'),
        target_orders_per_side=2,
        rebalance_interval=10
    )
    strategy_engine = StrategyEngine(strategy_config, event_bus, order_manager)

    # 启动风控
    await risk_manager.start()

    # 创建WebSocket监听器
    ws_listener = WebSocketMarketData(exchange, symbol)

    print("🚀 === 高级WebSocket被动做市 DEMO（Binance BTC/USDT）===")
    print("💡 按 Ctrl+C 退出程序")
    print("📊 使用WebSocket持续监听orderbook和trades")
    print("⚡ 实时数据，无rate limit限制")
    print("📈 市场数据分析和历史追踪")
    print("=" * 80)
    
    round_count = 0
    start_time = time.time()
    
    try:
        # 启动WebSocket监听
        ws_task = asyncio.create_task(ws_listener.start_listening())
        
        while running:
            round_count += 1
            current_time = time.time()
            runtime = current_time - start_time
            
            # 等待市场数据更新
            await asyncio.sleep(3)  # 每3秒处理一次策略逻辑
            
            if market_data['last_price'] is not None:
                price = market_data['last_price']
                print(f"\n⏰ [{time.strftime('%X')}] 第{round_count}轮 (运行{int(runtime)}秒)")

                # 打印市场摘要
                summary = ws_listener.get_market_summary()
                print_market_summary(summary)

                # 构造并推送价格事件
                price_event = PriceUpdateEvent(
                    event_type=EventType.PRICE_UPDATE,
                    timestamp=current_time,
                    data=ws_listener.orderbook_cache or {},
                    reference_price=price,
                    price_change=summary['price_change'] if summary else Decimal('0'),
                    confidence=0.99
                )
                await event_bus.publish(price_event)

                # 检查现有订单价格有效性
                orders_to_cancel = []
                for order_id, order in mock_orders.items():
                    if order.status == OrderStatus.ACTIVE:
                        if not check_order_price_validity(order, price, strategy_config.min_spread, strategy_config.max_spread):
                            orders_to_cancel.append(order_id)
                            print(f"❌ 订单 {order_id} 价格 {format_price(order.price)} 超出有效区间，标记撤单")

                # 策略分析
                analysis = await strategy_engine._analyze_current_orders(price)
                
                # 模拟撤单
                for order_id in orders_to_cancel:
                    if order_id in mock_orders:
                        mock_orders[order_id].status = OrderStatus.CANCELLED
                        mock_orders[order_id].update_time = current_time
                        print(f"🗑️  撤单: {order_id}")

                # 模拟新下单
                if analysis.need_bid_orders > 0 or analysis.need_ask_orders > 0:
                    decisions = await strategy_engine._generate_order_decisions(analysis, price)
                    for decision in decisions:
                        if hasattr(decision, 'side') and hasattr(decision, 'price') and hasattr(decision, 'quantity'):
                            mock_order = create_mock_order(decision.side, decision.price, decision.quantity)
                            print(f"📝 新下单: {decision.side} {format_price(decision.price)} × {format_quantity(decision.quantity)} (ID: {mock_order.order_id})")

                # 打印订单汇总
                print_order_summary(price)
            
    except KeyboardInterrupt:
        print("\n收到键盘中断，正在退出...")
    finally:
        # 取消WebSocket任务
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass
            
        await exchange.close()
        print(f"\n🏁 === DEMO结束，共运行{round_count}轮，总时长{int(time.time() - start_time)}秒 ===")
        print(f"📈 模拟订单统计: 创建{order_counter}个订单")

if __name__ == "__main__":
    asyncio.run(main()) 