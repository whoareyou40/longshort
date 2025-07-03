#!/usr/bin/env python3
"""
简单检查当前策略状态和持仓情况
"""

import asyncio
import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

async def check_current_status():
    """检查当前策略状态和持仓情况"""
    print("🔍 检查当前策略状态和持仓情况")
    print("=" * 50)
    
    # 设置交易所连接
    exchange = ccxt.okx({
        'apiKey': os.getenv('OKX_API_KEY'),
        'secret': os.getenv('OKX_SECRET_KEY'),
        'password': os.getenv('OKX_PASSPHRASE'),
        'sandbox': os.getenv('OKX_SANDBOX', 'true').lower() == 'true',
        'enableRateLimit': True,
    })
    
    if os.getenv('OKX_SANDBOX', 'true').lower() == 'true':
        exchange.set_sandbox_mode(True)
        print("🔧 使用沙盒模式")
    
    try:
        # 获取所有持仓
        print("📊 获取所有持仓...")
        positions = exchange.fetch_positions(params={'instType': 'SWAP'})
        
        current_positions = {}
        for pos in positions:
            info = pos.get('info', {})
            inst_id = info.get('instId')
            pos_side = info.get('posSide', '').lower()
            contracts = float(info.get('pos', 0))
            symbol = pos.get('symbol')
            
            if contracts > 0:
                current_positions[symbol] = {
                    'symbol': symbol,
                    'side': pos_side,
                    'contracts': contracts,
                    'inst_id': inst_id
                }
        
        print(f"📊 当前持仓数量: {len(current_positions)}")
        for symbol, pos_info in current_positions.items():
            print(f"   - {symbol}: {pos_info['side']} {pos_info['contracts']} contracts")
        
        # 这里需要手动设置策略状态，因为无法直接获取
        print(f"\n📋 策略状态检查:")
        print("   💡 请手动检查策略日志中的 status 字典")
        print("   💡 或者运行策略来获取当前状态")
        
        # 模拟一些常见的策略状态
        print(f"\n🔍 模拟检查:")
        print("   如果某个持仓的币种不在当前策略的 status=1 或 status=-1 列表中")
        print("   那么这个持仓就应该被平仓")
        
        if current_positions:
            print(f"\n📝 建议:")
            print("   1. 检查策略日志中的 status 字典")
            print("   2. 确认哪些币种的 status 为 0（未选中）")
            print("   3. 如果持仓中有 status=0 的币种，应该平仓")
        else:
            print(f"\n✅ 当前没有持仓")
        
    except Exception as e:
        print(f"❌ 检查异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_current_status()) 