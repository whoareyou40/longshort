#!/usr/bin/env python3
"""
测试孤儿持仓平仓逻辑
"""

import asyncio
import sys
import os

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from okx_momentum_strategy import OKXMomentumStrategy

async def test_orphaned_positions():
    """测试孤儿持仓平仓逻辑"""
    print("🧪 测试孤儿持仓平仓逻辑")
    print("=" * 50)
    
    # 创建策略实例
    strategy = OKXMomentumStrategy()
    
    try:
        # 设置模拟的 status 数据
        strategy.status = {
            'BTC/USDT:USDT': 1,    # 策略选中的多头
            'ETH/USDT:USDT': -1,   # 策略选中的空头
            'SOL/USDT:USDT': 0,    # 策略未选中
            'ADA/USDT:USDT': 0,    # 策略未选中
        }
        
        print("📋 当前策略状态:")
        for pair, status in strategy.status.items():
            if status == 1:
                print(f"   ✅ {pair}: 多头 (status: {status})")
            elif status == -1:
                print(f"   ✅ {pair}: 空头 (status: {status})")
            else:
                print(f"   ❌ {pair}: 未选中 (status: {status})")
        
        # 模拟持仓数据
        mock_positions = {
            'BTC/USDT:USDT': {
                'symbol': 'BTC/USDT:USDT',
                'side': 'long',
                'contracts': 0.1,
                'value': 4000,
                'price': 40000
            },
            'ETH/USDT:USDT': {
                'symbol': 'ETH/USDT:USDT',
                'side': 'short',
                'contracts': 1.0,
                'value': 3000,
                'price': 3000
            },
            'SOL/USDT:USDT': {
                'symbol': 'SOL/USDT:USDT',
                'side': 'long',
                'contracts': 10.0,
                'value': 1000,
                'price': 100
            },
            'ADA/USDT:USDT': {
                'symbol': 'ADA/USDT:USDT',
                'side': 'short',
                'contracts': 1000.0,
                'value': 500,
                'price': 0.5
            }
        }
        
        print(f"\n📊 模拟持仓数据:")
        for symbol, pos_info in mock_positions.items():
            print(f"   - {symbol}: {pos_info['side']} {pos_info['contracts']} contracts")
        
        # 模拟 get_all_positions 方法
        async def mock_get_all_positions():
            return mock_positions
        
        strategy.get_all_positions = mock_get_all_positions
        
        # 模拟 place_order 方法
        def mock_place_order(trading_pair, side, order_type, amount, pos_side=None, reduce_only=False):
            print(f"   📤 模拟下单: {trading_pair} {side} {amount} {pos_side} reduce_only={reduce_only}")
            return {'id': 'mock_order_id', 'status': 'closed'}
        
        strategy.place_order = mock_place_order
        
        # 模拟 set_leverage_and_margin_mode 方法
        def mock_set_leverage_and_margin_mode(trading_pair):
            print(f"   ⚙️ 模拟设置杠杆和保证金模式: {trading_pair}")
        
        strategy.set_leverage_and_margin_mode = mock_set_leverage_and_margin_mode
        
        # 执行平仓逻辑
        print(f"\n🔄 执行平仓逻辑...")
        await strategy.close_orphaned_positions()
        
        print(f"\n✅ 测试完成!")
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_orphaned_positions()) 