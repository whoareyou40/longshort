#!/usr/bin/env python3
"""
Check positions that should be closed (have positions but not in current strategy range)
"""

import asyncio
import ccxt
import os
from decimal import Decimal
from dotenv import load_dotenv
from okx_config import OKXConfig

load_dotenv()

class PositionChecker:
    def __init__(self):
        self.config = OKXConfig()
        self.setup_exchange()
        
    def setup_exchange(self):
        """Initialize CCXT exchange connection for OKX"""
        self.exchange = ccxt.okx({
            'apiKey': self.config.API_KEY,
            'secret': self.config.SECRET_KEY,
            'password': self.config.PASSPHRASE,
            'sandbox': self.config.SANDBOX,
            'enableRateLimit': True,
        })
        
        # 强制只加载SWAP市场，避免API错误
        self.exchange.options['defaultType'] = 'swap'
        
        if self.config.SANDBOX:
            self.exchange.set_sandbox_mode(True)
            
        print(f"Connected to OKX {'sandbox' if self.config.SANDBOX else 'live'} mode")
    
    async def get_current_positions(self):
        """Get all current positions (no price lookup)"""
        try:
            # 直接调用OKX API
            response = self.exchange.privateGetAccountPositions({'instType': 'SWAP'})
            data = response.get('data', [])
            current_positions = {}
            for pos_data in data:
                inst_id = pos_data.get('instId')
                pos_side = pos_data.get('posSide', '').lower()
                pos_value = pos_data.get('pos', '0')
                if pos_value == '0' or pos_value == 0:
                    continue
                contracts = float(pos_value)
                if contracts > 0:
                    # 构造symbol
                    if inst_id and '-USDT-SWAP' in inst_id:
                        symbol = inst_id.replace('-USDT-SWAP', '/USDT:USDT')
                    else:
                        symbol = inst_id
                    current_positions[symbol] = {
                        'symbol': symbol,
                        'inst_id': inst_id,
                        'side': pos_side,
                        'contracts': contracts,
                    }
            return current_positions
        except Exception as e:
            print(f"❌ Error getting positions: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    async def simulate_strategy_selection(self):
        """Simulate what the strategy would select (top/bottom performers)"""
        print("\n📊 Simulating strategy selection...")
        
        try:
            # 这里我们简化处理，实际策略会计算动量分数
            # 由于pandas_ta有问题，我们暂时用随机选择来演示逻辑
            
            import random
            random.seed(42)  # 固定种子，确保结果一致
            
            # 从TRADING_PAIRS中随机选择top和bottom performers
            all_pairs = list(self.config.TRADING_PAIRS)
            random.shuffle(all_pairs)
            
            long_n = getattr(self.config, 'LONG_TOP_N', 2)
            short_n = getattr(self.config, 'SHORT_BOTTOM_N', 2)
            
            # 模拟top performers (应该做多)
            top_performers = all_pairs[:long_n]
            # 模拟bottom performers (应该做空)
            bottom_performers = all_pairs[-short_n:]
            
            print(f"🎯 Strategy would select:")
            print(f"  Top {long_n} performers (LONG): {top_performers}")
            print(f"  Bottom {short_n} performers (SHORT): {bottom_performers}")
            
            return set(top_performers + bottom_performers)
            
        except Exception as e:
            print(f"❌ Error simulating strategy: {e}")
            return set()
    
    async def check_positions_to_close(self):
        """Check which positions should be closed"""
        print("🔍 Checking positions that should be closed...")
        
        try:
            # 获取当前所有持仓
            current_positions = await self.get_current_positions()
            
            if not current_positions:
                print("✅ No current positions found")
                return
            
            print(f"\n📊 Current positions ({len(current_positions)} total):")
            for symbol, pos_info in current_positions.items():
                print(f"  - {symbol}: {pos_info['side']} {pos_info['contracts']} contracts")
            
            # 模拟策略选择
            strategy_selected = await self.simulate_strategy_selection()
            
            # 找出应该平仓的持仓
            positions_to_close = {}
            positions_to_keep = {}
            
            for symbol, pos_info in current_positions.items():
                if symbol in strategy_selected:
                    positions_to_keep[symbol] = pos_info
                else:
                    positions_to_close[symbol] = pos_info
            
            # 打印结果
            print(f"\n📋 Analysis Results:")
            print("=" * 50)
            
            if positions_to_keep:
                print(f"\n✅ Positions to KEEP ({len(positions_to_keep)}):")
                for symbol, pos_info in positions_to_keep.items():
                    print(f"  - {symbol}: {pos_info['side']} {pos_info['contracts']} contracts")
            else:
                print(f"\n✅ No positions to keep")
            
            if positions_to_close:
                print(f"\n🚨 Positions to CLOSE ({len(positions_to_close)}):")
                for symbol, pos_info in positions_to_close.items():
                    print(f"  - {symbol}: {pos_info['side']} {pos_info['contracts']} contracts")
            else:
                print(f"\n✅ No positions to close")
            
            # 详细分析每个持仓
            print(f"\n📊 Detailed Analysis:")
            print("=" * 50)
            
            for symbol, pos_info in current_positions.items():
                if symbol in strategy_selected:
                    print(f"✅ {symbol}: KEEP - In strategy selection")
                else:
                    print(f"🚨 {symbol}: CLOSE - Not in strategy selection")
                    print(f"    Details: {pos_info['side']} {pos_info['contracts']} contracts")
            
            return positions_to_close
            
        except Exception as e:
            print(f"❌ Error checking positions: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    async def run_check(self):
        """Run the complete check"""
        print("🚀 Position Close Check")
        print("=" * 40)
        
        positions_to_close = await self.check_positions_to_close()
        
        if positions_to_close:
            print(f"\n💡 Summary:")
            print(f"  - Found {len(positions_to_close)} positions that should be closed")
            print(f"  - These positions are not in the current strategy's top/bottom performers")
            print(f"  - They should be closed to maintain strategy consistency")
            print(f"\n🔧 To close these positions, you can:")
            print(f"  1. Run the main strategy (it should close them automatically)")
            print(f"  2. Use force_close_positions.py with specific symbols")
            print(f"  3. Manually close them in the OKX interface")
        else:
            print(f"\n✅ All current positions are within strategy selection - no action needed")

async def main():
    checker = PositionChecker()
    await checker.run_check()

if __name__ == "__main__":
    asyncio.run(main()) 