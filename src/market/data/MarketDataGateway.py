import asyncio
import json
import websockets
import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from ...core.events.EventBus import EventBus
from ...core.events.EventType import EventType, BaseEvent, PriceUpdateEvent
from ...config.Configs import MasterConfig

class MarketData:
    """市场数据对象"""
    def __init__(self):
        self.symbol = ""
        self.bid_price = Decimal('0')
        self.ask_price = Decimal('0')
        self.mid_price = Decimal('0')
        self.last_price = Decimal('0')
        self.volume_24h = Decimal('0')
        self.price_change_24h = Decimal('0')
        self.recent_trades = []
        self.order_book = {'bids': [], 'asks': []}

class Trade:
    """交易对象"""
    def __init__(self, price: Decimal, volume: Decimal, timestamp: float = None):
        self.price = price
        self.volume = volume
        self.timestamp = timestamp or asyncio.get_event_loop().time()

class MarketDataGateway:
    """市场数据网关"""
    
    def __init__(self, config: MasterConfig, event_bus: EventBus):
        self.config = config
        self.event_bus = event_bus
        self.symbol = config.strategy.symbol.lower()
        self.ws_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@ticker/{self.symbol}@depth20@100ms"
        self.running = False
        self.logger = logging.getLogger(__name__)
        self.current_market_data = MarketData()
        
    async def start(self) -> None:
        """启动市场数据网关"""
        self.running = True
        asyncio.create_task(self._connect_websocket())
        self.logger.info(f"Market data gateway started for {self.symbol}")
        
    async def stop(self) -> None:
        """停止市场数据网关"""
        self.running = False
        self.logger.info("Market data gateway stopped")
        
    async def _connect_websocket(self) -> None:
        """连接WebSocket"""
        while self.running:
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    self.logger.info(f"Connected to Binance WebSocket for {self.symbol}")
                    
                    while self.running:
                        try:
                            message = await websocket.recv()
                            await self._process_message(json.loads(message))
                        except websockets.exceptions.ConnectionClosed:
                            self.logger.warning("WebSocket connection closed, reconnecting...")
                            break
                        except Exception as e:
                            self.logger.error(f"Error processing message: {e}")
                            
            except Exception as e:
                self.logger.error(f"WebSocket connection error: {e}")
                await asyncio.sleep(5)  # 重连延迟
                
    async def _process_message(self, message: Dict[str, Any]) -> None:
        """处理WebSocket消息"""
        try:
            if 'e' in message:  # 事件类型
                event_type = message['e']
                
                if event_type == '24hrTicker':
                    await self._process_ticker(message)
                elif event_type == 'depthUpdate':
                    await self._process_depth(message)
                elif event_type == 'trade':
                    await self._process_trade(message)
                    
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            
    async def _process_ticker(self, data: Dict[str, Any]) -> None:
        """处理Ticker数据"""
        self.current_market_data.symbol = data['s']
        self.current_market_data.last_price = Decimal(str(data['c']))
        self.current_market_data.volume_24h = Decimal(str(data['v']))
        self.current_market_data.price_change_24h = Decimal(str(data['P']))
        
        # 计算中间价
        if self.current_market_data.bid_price > 0 and self.current_market_data.ask_price > 0:
            self.current_market_data.mid_price = (
                self.current_market_data.bid_price + self.current_market_data.ask_price
            ) / 2
            
            # 发布价格更新事件
            await self.event_bus.publish(PriceUpdateEvent(
                event_type=EventType.PRICE_UPDATE,
                timestamp=asyncio.get_event_loop().time(),
                data={'symbol': self.symbol},
                reference_price=self.current_market_data.mid_price,
                price_change=self.current_market_data.price_change_24h,
                confidence=0.95
            ))
            
    async def _process_depth(self, data: Dict[str, Any]) -> None:
        """处理深度数据"""
        bids = [[Decimal(str(price)), Decimal(str(qty))] for price, qty in data['b']]
        asks = [[Decimal(str(price)), Decimal(str(qty))] for price, qty in data['a']]
        
        self.current_market_data.order_book['bids'] = bids
        self.current_market_data.order_book['asks'] = asks
        
        # 更新买卖价格
        if bids:
            self.current_market_data.bid_price = bids[0][0]
        if asks:
            self.current_market_data.ask_price = asks[0][0]
            
        # 发布深度更新事件
        await self.event_bus.publish(BaseEvent(
            event_type=EventType.MARKET_DEPTH,
            timestamp=asyncio.get_event_loop().time(),
            data={
                'symbol': self.symbol,
                'bids': [[float(price), float(qty)] for price, qty in bids],
                'asks': [[float(price), float(qty)] for price, qty in asks]
            }
        ))
        
    async def _process_trade(self, data: Dict[str, Any]) -> None:
        """处理交易数据"""
        trade = Trade(
            price=Decimal(str(data['p'])),
            volume=Decimal(str(data['q'])),
            timestamp=data['T'] / 1000.0
        )
        
        # 添加到最近交易列表
        self.current_market_data.recent_trades.append(trade)
        
        # 保持最近100笔交易
        if len(self.current_market_data.recent_trades) > 100:
            self.current_market_data.recent_trades.pop(0)
            
        # 发布交易事件
        await self.event_bus.publish(BaseEvent(
            event_type=EventType.MARKET_TRADE,
            timestamp=asyncio.get_event_loop().time(),
            data={
                'symbol': self.symbol,
                'price': float(trade.price),
                'volume': float(trade.volume),
                'timestamp': trade.timestamp
            }
        )) 