#!/usr/bin/env python3
"""
Force close all current positions for testing
"""

import asyncio
import ccxt
import os
from decimal import Decimal
from dotenv import load_dotenv
from okx_config import OKXConfig

load_dotenv()

class ForceClosePositions:
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
        
        if self.config.SANDBOX:
            self.exchange.set_sandbox_mode(True)
            
        print(f"Connected to OKX {'sandbox' if self.config.SANDBOX else 'live'} mode")
    
    async def get_all_positions(self):
        """Get all current positions"""
        try:
            positions = self.exchange.fetch_positions(params={'instType': 'SWAP'})
            
            all_positions = {}
            for pos in positions:
                info = pos.get('info', {})
                inst_id = info.get('instId')
                pos_side = info.get('posSide', '').lower()
                pos_value = info.get('pos', 0)
                
                # Handle None values
                if pos_value is None:
                    continue
                    
                contracts = float(pos_value)
                symbol = pos.get('symbol')
                
                if contracts > 0:
                    all_positions[symbol] = {
                        'symbol': symbol,
                        'inst_id': inst_id,
                        'side': pos_side,
                        'contracts': contracts
                    }
            
            return all_positions
            
        except Exception as e:
            print(f"❌ Error getting positions: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def set_leverage_and_margin_mode(self, trading_pair: str):
        """Set leverage and margin mode"""
        try:
            self.exchange.set_leverage(20, trading_pair, {'marginMode': 'cross'})
            print(f"Set leverage to 20x for {trading_pair}")
        except Exception as e:
            print(f"Error setting leverage for {trading_pair}: {e}")
    
    def place_close_order(self, trading_pair: str, side: str, amount: float, pos_side: str):
        """Place close order"""
        try:
            params = {
                'tdMode': 'cross',
                'reduceOnly': True,
                'posSide': pos_side
            }
            
            if side == 'sell':
                order = self.exchange.create_market_sell_order(trading_pair, amount, params)
            else:
                order = self.exchange.create_market_buy_order(trading_pair, amount, params)
                
            print(f"✅ Successfully placed {side} order for {trading_pair}: {amount} contracts")
            return order
            
        except Exception as e:
            print(f"❌ Error placing {side} order for {trading_pair}: {e}")
            return None
    
    async def force_close_all_positions(self, dry_run=True):
        """Force close all positions"""
        print(f"🛡️ Force closing all positions (dry_run={dry_run})...")
        
        try:
            # Get all positions
            all_positions = await self.get_all_positions()
            
            if not all_positions:
                print("✅ No positions found to close")
                return
            
            print(f"📊 Found {len(all_positions)} positions to close:")
            for symbol, pos_info in all_positions.items():
                print(f"  - {symbol}: {pos_info['side']} {pos_info['contracts']} contracts")
            
            if dry_run:
                print("\n🔍 DRY RUN - Would close the following positions:")
                for symbol, pos_info in all_positions.items():
                    print(f"  - {symbol}: {pos_info['side']} {pos_info['contracts']} contracts")
                print("💡 Set dry_run=False to actually close positions")
                return
            
            print("\n⚠️ WARNING: This will actually close all positions!")
            print("Press Ctrl+C to cancel, or wait 5 seconds to continue...")
            await asyncio.sleep(5)
            
            # Close each position
            for symbol, pos_info in all_positions.items():
                try:
                    print(f"\n🔄 Closing {symbol}...")
                    
                    # Set leverage and margin mode
                    self.set_leverage_and_margin_mode(symbol)
                    
                    # Close position
                    if pos_info['side'] == 'long':
                        order = self.place_close_order(
                            trading_pair=symbol,
                            side='sell',
                            amount=pos_info['contracts'],
                            pos_side='long'
                        )
                    elif pos_info['side'] == 'short':
                        order = self.place_close_order(
                            trading_pair=symbol,
                            side='buy',
                            amount=pos_info['contracts'],
                            pos_side='short'
                        )
                    
                    if order:
                        print(f"✅ Successfully closed {symbol}")
                    else:
                        print(f"❌ Failed to close {symbol}")
                        
                except Exception as e:
                    print(f"❌ Error closing {symbol}: {e}")
            
            print(f"\n🎉 Force close operation completed!")
            
        except Exception as e:
            print(f"❌ Error in force_close_all_positions: {e}")
    
    async def run_test(self):
        """Run the test"""
        print("🚀 Force Close Positions Test")
        print("=" * 40)
        
        # First show current positions
        print("\n📋 Current Positions:")
        print("-" * 30)
        all_positions = await self.get_all_positions()
        
        if all_positions:
            for symbol, pos_info in all_positions.items():
                print(f"  - {symbol}: {pos_info['side']} {pos_info['contracts']} contracts")
        else:
            print("  No positions found")
        
        # Force close (dry run by default)
        print("\n📋 Force Close (Dry Run):")
        print("-" * 30)
        await self.force_close_all_positions(dry_run=False)
        
        print(f"\n💡 To actually close all positions, run:")
        print(f"   await force_close_all_positions(dry_run=False)")

async def main():
    closer = ForceClosePositions()
    await closer.run_test()

if __name__ == "__main__":
    asyncio.run(main()) 