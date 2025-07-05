import asyncio
import signal
import sys
from pathlib import Path
from config.loaders.ConfigLoader import ConfigLoader
from core.events.EventBus import EventBus
from market.data.MarketDataGateway import MarketDataGateway
from strategy.engines.ReferencePriceEngine import ReferencePriceEngine
from core.orders.OrderState import OrderManager
from strategy.engines.StrategyEngine import StrategyEngine
from execution.ExecutionEngine import ExecutionEngine
from risk.management.RiskManager import RiskManager
from core.events.EventType import SystemStartEvent, SystemStopEvent
import time

class MarketMakingStrategy:
    def __init__(self, config_path: str):
        self.config = ConfigLoader.load_from_file(config_path)
        self.event_bus = EventBus()
        self.components = {}
        self.running = False
        
    async def initialize(self) -> None:
        """初始化所有组件"""
        # 创建组件
        self.components['market_gateway'] = MarketDataGateway(
            self.config, self.event_bus
        )
        
        self.components['price_engine'] = ReferencePriceEngine(
            self.config.price, self.event_bus
        )
        
        self.components['order_manager'] = OrderManager(self.event_bus)
        
        self.components['strategy_engine'] = StrategyEngine(
            self.config.strategy, self.event_bus, self.components['order_manager']
        )
        
        self.components['execution_engine'] = ExecutionEngine(
            self.config.execution, self.event_bus, self.components['order_manager']
        )
        
        self.components['risk_manager'] = RiskManager(
            self.config.risk, self.event_bus
        )
        
        # 启动事件总线
        await self.event_bus.start()
        
        # 启动所有组件
        for component in self.components.values():
            if hasattr(component, 'start'):
                await component.start()
                
    async def start(self) -> None:
        """启动策略"""
        self.running = True
        
        # 发布启动事件
        await self.event_bus.publish(SystemStartEvent(
            timestamp=time.time(),
            data={'config': self.config}
        ))
        
        print(f"Market Making Strategy started for {self.config.strategy.symbol}")
        
        # 保持运行
        while self.running:
            await asyncio.sleep(1)
            
    async def stop(self) -> None:
        """停止策略"""
        self.running = False
        
        print("Shutting down Market Making Strategy...")
        
        # 发布停止事件
        await self.event_bus.publish(SystemStopEvent(
            timestamp=time.time(),
            data={'reason': 'manual_shutdown'}
        ))
        
        # 停止所有组件
        for component in self.components.values():
            if hasattr(component, 'stop'):
                await component.stop()
                
        # 停止事件总线
        await self.event_bus.stop()
        
        print("Market Making Strategy stopped")
        
    def setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        def signal_handler(signum, frame):
            print(f"Received signal {signum}, shutting down...")
            asyncio.create_task(self.stop())
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """主函数"""
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    
    strategy = MarketMakingStrategy(config_path)
    strategy.setup_signal_handlers()
    
    try:
        await strategy.initialize()
        await strategy.start()
    except KeyboardInterrupt:
        await strategy.stop()
    except Exception as e:
        print(f"Fatal error: {e}")
        await strategy.stop()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
