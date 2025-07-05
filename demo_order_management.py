#!/usr/bin/env python3
"""
订单管理功能演示脚本
展示定时撤单重置和改单功能
"""

import asyncio
import time
import logging
from decimal import Decimal
from src.core.events.EventBus import EventBus
from src.core.orders.OrderManager import OrderManager, OrderState, OrderStatus
from src.core.events.EventType import (
    PriceUpdateEvent, OrderResetEvent, OrderModifyEvent, EventType
)
from src.strategy.engines.StrategyEngine import StrategyEngine
from src.config.Configs import StrategyConfig, OrderManagementConfig, ExecutionConfig
from src.core.orders.OrderDecision import PlaceOrderDecision, CancelOrderDecision, ModifyOrderDecision
import uuid

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OrderManagementDemo:
    def __init__(self):
        # 创建事件总线
        self.event_bus = EventBus()
        
        # 创建配置
        self.strategy_config = StrategyConfig(
            symbol="BTCUSDT",
            min_spread=Decimal('0.002'),
            max_spread=Decimal('0.004'),
            min_order_value=Decimal('10000'),
            target_orders_per_side=2,
            drift_threshold=Decimal('0.005'),
            rebalance_interval=5,
            modify_threshold=Decimal('0.003'),
            max_modify_deviation=Decimal('0.01')
        )
        
        self.order_management_config = OrderManagementConfig(
            reset_interval=60,  # 1分钟重置（演示用）
            max_pending_modifications=10,
            modification_timeout=30,
            cleanup_interval=7200
        )
        
        self.execution_config = ExecutionConfig(
            symbol="BTCUSDT",
            worker_count=2,
            batch_size=5,
            rate_limit=10,
            max_retries=3,
            retry_delay=1.0,
            modify_worker_count=1,
            modify_rate_limit=5
        )
        
        # 创建订单管理器
        self.order_manager = OrderManager(self.event_bus, self.order_management_config.reset_interval)
        
        # 创建策略引擎
        self.strategy_engine = StrategyEngine(self.strategy_config, self.event_bus, self.order_manager)
        
        # 模拟价格数据
        self.current_price = Decimal('50000')
        self.price_history = []
        self.order_id_counter = 0
        
    async def start(self):
        """启动演示"""
        logger.info("启动订单管理功能演示")
        
        # 启动事件总线后台处理器
        await self.event_bus.start()
        
        # 启动订单管理器
        await self.order_manager.start()
        
        # 注册事件处理器
        await self.event_bus.subscribe(EventType.ORDER_RESET, self.handle_order_reset)
        await self.event_bus.subscribe(EventType.ORDER_MODIFY, self.handle_order_modify)
        await self.event_bus.subscribe(EventType.ORDER_STATUS, self.handle_order_status)
        # 拦截策略决策事件，模拟下单/改单/撤单
        await self.event_bus.subscribe(EventType.PLACE_ORDER, self.simulate_place_order)
        await self.event_bus.subscribe(EventType.CANCEL_ORDER, self.simulate_cancel_order)
        await self.event_bus.subscribe(EventType.ORDER_MODIFY, self.simulate_modify_order)
        
        logger.info("事件处理器注册完成")
        
        # 启动演示任务
        asyncio.create_task(self.price_simulation())
        asyncio.create_task(self.order_monitoring())
        asyncio.create_task(self.reset_monitoring())
        
    async def price_simulation(self):
        """价格模拟"""
        logger.info("开始价格模拟")
        
        for i in range(20):  # 运行20轮
            # 模拟价格变化
            price_change = Decimal(str(0.001 * (i % 4 - 2)))  # -0.2% 到 +0.2%
            self.current_price = self.current_price * (Decimal('1') + price_change)
            self.price_history.append(self.current_price)
            
            # 创建价格更新事件
            price_event = PriceUpdateEvent(
                event_type=EventType.PRICE_UPDATE,
                timestamp=time.time(),
                data={},
                reference_price=self.current_price,
                price_change=price_change,
                confidence=0.8
            )
            
            # 发布价格事件
            await self.event_bus.publish(price_event)
            
            # 触发策略分析
            await self.strategy_engine.on_price_update(price_event)
            
            logger.info(f"价格更新: {self.current_price:.2f} USDT (变化: {price_change*100:.2f}%)")
            
            await asyncio.sleep(10)  # 每10秒更新一次价格
            
    async def simulate_place_order(self, event: PlaceOrderDecision):
        """模拟下单，生成订单并激活"""
        logger.info(f"[模拟下单] 收到下单决策: {event.side} {event.quantity} @ {event.price}")
        self.order_id_counter += 1
        order_id = f"sim_{self.order_id_counter}_{int(time.time()*1000)}"
        order = OrderState(
            order_id=order_id,
            client_order_id=str(uuid.uuid4()),
            symbol=self.strategy_config.symbol,
            side=event.side,
            price=event.price,
            original_quantity=event.quantity,
            executed_quantity=Decimal('0'),
            status=OrderStatus.ACTIVE,
            create_time=time.time(),
            update_time=time.time(),
            last_event_time=time.time()
        )
        await self.order_manager.add_order(order)
        logger.info(f"[模拟下单] {order.side} {order.original_quantity} @ {order.price} (订单ID: {order.order_id})")
        await self.print_all_orders()
        
    async def simulate_cancel_order(self, event: CancelOrderDecision):
        """模拟撤单，订单状态流转为CANCELLED"""
        logger.info(f"[模拟撤单] 收到撤单决策: {event.order_id}")
        order = await self.order_manager.get_order_by_id(event.order_id)
        if order and order.is_active:
            await self.order_manager.update_order_status(order.order_id, OrderStatus.PENDING_CANCEL)
            await asyncio.sleep(0.5)  # 模拟撤单延迟
            await self.order_manager.update_order_status(order.order_id, OrderStatus.CANCELLED)
            logger.info(f"[模拟撤单] 订单已撤销: {order.order_id}")
        else:
            logger.info(f"[模拟撤单] 订单不存在或已撤销: {event.order_id}")
        await self.print_all_orders()
        
    async def simulate_modify_order(self, event: ModifyOrderDecision):
        """模拟改单，直接修改订单价格"""
        logger.info(f"[模拟改单] 收到改单决策: {event.order_id} 新价格: {event.new_price}")
        order = await self.order_manager.get_order_by_id(event.order_id)
        if order and order.is_active:
            await self.order_manager.update_order_status(order.order_id, OrderStatus.PENDING_MODIFY)
            await asyncio.sleep(0.5)  # 模拟改单延迟
            # 修改价格
            if event.new_price:
                order.price = Decimal(event.new_price)
            await self.order_manager.update_order_status(order.order_id, OrderStatus.ACTIVE)
            logger.info(f"[模拟改单] 订单已改单: {order.order_id} 新价格: {order.price}")
        else:
            logger.info(f"[模拟改单] 订单不存在或不可改单: {event.order_id}")
        await self.print_all_orders()
        
    async def print_all_orders(self):
        """打印所有订单状态（包括非活跃）"""
        all_orders = list(self.order_manager.orders.values())
        if not all_orders:
            logger.info("[订单总览] 当前无订单")
            return
        logger.info("[订单总览] 当前所有订单:")
        for order in all_orders:
            logger.info(f"  {order.side} {order.original_quantity} @ {order.price} 状态: {order.status.value} 订单ID: {order.order_id}")
        
    async def order_monitoring(self):
        """订单监控"""
        while True:
            try:
                # 获取活跃订单
                active_orders = await self.order_manager.get_active_orders()
                
                # 获取重置统计
                reset_stats = await self.order_manager.get_reset_stats()
                
                # 获取待处理改单
                pending_modifications = await self.order_manager.get_pending_modifications()
                
                # 打印状态
                logger.info(f"=== 订单状态监控 ===")
                logger.info(f"活跃订单数: {len(active_orders)}")
                logger.info(f"待处理改单数: {len(pending_modifications)}")
                logger.info(f"距离下次重置: {reset_stats['time_until_next_reset']:.1f}秒")
                
                if active_orders:
                    logger.info("活跃订单详情:")
                    for order in active_orders:
                        logger.info(f"  {order.side} {order.original_quantity} @ {order.price} "
                                  f"(状态: {order.status.value})")
                
                await asyncio.sleep(15)  # 每15秒监控一次
                
            except Exception as e:
                logger.error(f"订单监控错误: {e}")
                await asyncio.sleep(5)
                
    async def reset_monitoring(self):
        """重置监控"""
        while True:
            try:
                reset_stats = await self.order_manager.get_reset_stats()
                
                if reset_stats['time_until_next_reset'] < 10:  # 距离重置不到10秒
                    logger.warning(f"⚠️  即将进行定时重置，剩余时间: {reset_stats['time_until_next_reset']:.1f}秒")
                    
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"重置监控错误: {e}")
                await asyncio.sleep(5)
                
    async def handle_order_reset(self, event: OrderResetEvent):
        """处理订单重置事件，模拟清空订单管理器"""
        logger.info(f"🔄 收到订单重置事件: {event.data}")
        # 模拟撤销所有订单
        active_orders = await self.order_manager.get_active_orders()
        for order in active_orders:
            await self.simulate_cancel_order(CancelOrderDecision(order_id=order.order_id))
        logger.info("[模拟重置] 所有订单已撤销并重置")
        
    async def handle_order_modify(self, event: OrderModifyEvent):
        """处理改单事件（日志输出）"""
        logger.info(f"✏️  收到改单事件: {event.data}")
        
    async def handle_order_status(self, event):
        """处理订单状态事件"""
        status = event.status
        order_id = event.order_id
        
        if status == "ACTIVE":
            logger.info(f"✅ 订单激活: {order_id}")
        elif status == "CANCELLED":
            logger.info(f"❌ 订单撤销: {order_id}")
        elif status == "PENDING_MODIFY":
            logger.info(f"⏳ 订单待修改: {order_id}")
        elif status == "PENDING_CANCEL":
            logger.info(f"⏳ 订单待撤销: {order_id}")
            
    async def stop(self):
        """停止演示"""
        logger.info("停止订单管理功能演示")
        await self.order_manager.stop()

async def main():
    """主函数"""
    demo = OrderManagementDemo()
    
    try:
        await demo.start()
        
        # 运行演示
        logger.info("演示开始，按 Ctrl+C 停止")
        await asyncio.sleep(300)  # 运行5分钟
        
    except KeyboardInterrupt:
        logger.info("收到停止信号")
    finally:
        await demo.stop()

if __name__ == "__main__":
    asyncio.run(main()) 