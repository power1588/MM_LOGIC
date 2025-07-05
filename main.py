#!/usr/bin/env python3
"""
被动做市策略系统主程序
Market Making Strategy System Main Entry
"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from strategy_main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main()) 