#!/usr/bin/env python3
"""
手动运行策略的get_factor方法，查看币种状态
"""

import asyncio
import sys
import os

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 临时禁用pandas_ta导入
import builtins
original_import = builtins.__import__

def custom_import(name, *args, **kwargs):
    if name == 'pandas_ta':
        # 创建一个模拟的pandas_ta模块
        class MockPandasTA:
            def __getattr__(self, name):
                return lambda *args, **kwargs: None
        return MockPandasTA()
    return original_import(name, *args, **kwargs)

builtins.__import__ = custom_import

from okx_momentum_strategy import OKXMomentumStrategy

async def debug_strategy_status():
    """调试策略状态"""
    print("🔍 调试策略状态")
    print("=" * 50)
    
    try:
        # 创建策略实例
        strategy = OKXMomentumStrategy()
        
        print("📊 运行 get_factor 方法...")
        await strategy.get_factor()
        
        print(f"\n📋 策略状态结果:")
        print(f"   总币种数: {len(strategy.status)}")
        
        # 统计不同状态的数量
        status_counts = {}
        for pair, status in strategy.status.items():
            if status not in status_counts:
                status_counts[status] = []
            status_counts[status].append(pair)
        
        for status, pairs in status_counts.items():
            if status == 1:
                print(f"   ✅ 多头 (status=1): {len(pairs)} 个")
                for pair in pairs[:5]:  # 只显示前5个
                    print(f"      - {pair}")
                if len(pairs) > 5:
                    print(f"      ... 还有 {len(pairs) - 5} 个")
            elif status == -1:
                print(f"   ✅ 空头 (status=-1): {len(pairs)} 个")
                for pair in pairs[:5]:  # 只显示前5个
                    print(f"      - {pair}")
                if len(pairs) > 5:
                    print(f"      ... 还有 {len(pairs) - 5} 个")
            else:
                print(f"   ❌ 未选中 (status=0): {len(pairs)} 个")
        
        # 检查当前持仓的币种状态
        print(f"\n🔍 检查当前持仓的币种状态:")
        current_positions = ['ALPHA/USDT:USDT', 'BONK/USDT:USDT', 'PI/USDT:USDT', 'ARC/USDT:USDT']
        
        for symbol in current_positions:
            status = strategy.status.get(symbol, 'NOT_FOUND')
            if status == 1:
                print(f"   ✅ {symbol}: 多头 (status=1) - 保留持仓")
            elif status == -1:
                print(f"   ✅ {symbol}: 空头 (status=-1) - 保留持仓")
            elif status == 0:
                print(f"   🚨 {symbol}: 未选中 (status=0) - 需要平仓")
            else:
                print(f"   ❓ {symbol}: 未找到 (status={status}) - 需要平仓")
        
        # 找出需要平仓的币种
        print(f"\n📊 平仓分析:")
        to_close = []
        to_keep = []
        
        for symbol in current_positions:
            status = strategy.status.get(symbol, 0)
            if status == 1 or status == -1:
                to_keep.append(symbol)
            else:
                to_close.append(symbol)
        
        if to_close:
            print(f"   🚨 需要平仓: {len(to_close)} 个")
            for symbol in to_close:
                print(f"      - {symbol}")
        else:
            print(f"   ✅ 没有需要平仓的币种")
        
        if to_keep:
            print(f"   ✅ 保留持仓: {len(to_keep)} 个")
            for symbol in to_keep:
                status = strategy.status.get(symbol)
                direction = "多头" if status == 1 else "空头"
                print(f"      - {symbol} ({direction})")
        
        print(f"\n💡 总结:")
        print(f"   - 如果币种状态为 0，说明不在当前策略的选中范围内")
        print(f"   - 这些币种应该被平仓")
        print(f"   - 如果币种状态为 1 或 -1，说明在当前策略选中范围内，应该保留")
        
    except Exception as e:
        print(f"❌ 调试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_strategy_status()) 