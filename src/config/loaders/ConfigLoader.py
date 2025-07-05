import yaml
import os
from typing import Dict, Any
from ..Configs import MasterConfig, StrategyConfig, PriceConfig, ExecutionConfig, RiskConfig

class ConfigLoader:
    """配置加载器"""
    
    @staticmethod
    def load_from_file(file_path: str) -> MasterConfig:
        """从文件加载配置"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Config file not found: {file_path}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            
        return ConfigLoader._parse_config(config_data)
        
    @staticmethod
    def load_from_dict(config_dict: Dict[str, Any]) -> MasterConfig:
        """从字典加载配置"""
        return ConfigLoader._parse_config(config_dict)
        
    @staticmethod
    def _parse_config(config_data: Dict[str, Any]) -> MasterConfig:
        """解析配置数据"""
        # 解析策略配置
        strategy_config = StrategyConfig(
            symbol=config_data['strategy']['symbol'],
            min_spread=config_data['strategy']['min_spread'],
            max_spread=config_data['strategy']['max_spread'],
            min_order_value=config_data['strategy']['min_order_value'],
            drift_threshold=config_data['strategy']['drift_threshold'],
            target_orders_per_side=config_data['strategy']['target_orders_per_side']
        )
        
        # 解析价格配置
        price_config = PriceConfig(
            twap_window=config_data['price']['twap_window'],
            confidence_threshold=config_data['price']['confidence_threshold'],
            max_price_deviation=config_data['price']['max_price_deviation']
        )
        
        # 解析执行配置
        execution_config = ExecutionConfig(
            symbol=config_data['execution']['symbol'],
            batch_size=config_data['execution']['batch_size'],
            worker_count=config_data['execution']['worker_count'],
            rate_limit=config_data['execution']['rate_limit'],
            max_retries=config_data['execution']['max_retries'],
            retry_delay=config_data['execution']['retry_delay']
        )
        
        # 解析风险配置
        risk_config = RiskConfig(
            max_position=config_data['risk']['max_position'],
            max_order_count=config_data['risk']['max_order_count'],
            max_daily_loss=config_data['risk']['max_daily_loss'],
            max_price_change=config_data['risk']['max_price_change'],
            check_interval=config_data['risk']['check_interval']
        )
        
        return MasterConfig(
            strategy=strategy_config,
            price=price_config,
            execution=execution_config,
            risk=risk_config
        )
