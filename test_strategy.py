#!/usr/bin/env python3
"""
Test script to verify position detection and duplicate opening prevention in OKX main strategy
"""

import asyncio
import ccxt
import os
from decimal import Decimal
from dotenv import load_dotenv
from okx_config import OKXConfig
from okx_momentum_strategy import OKXMomentumStrategy

load_dotenv()

class StrategyTest:
    def __init__(self):
        self.config = OKXConfig()
        self.strategy = OKXMomentumStrategy()
        
    async def test_position_detection(self):
        """Test position detection logic"""
        print("🔍 Testing position detection...")
        
        try:
            # Get current positions
            await self.strategy.get_balance()
            
            print(f"📊 Current positions: {self.strategy.asset_value}")
            print(f"📊 Current amounts: {self.strategy.asset_amount}")
            
            # Test with a specific pair (e.g., ETH)
            test_pair = "ETH/USDT:USDT"
            if test_pair in self.strategy.asset_value:
                current_value = self.strategy.asset_value[test_pair]
                current_amount = self.strategy.asset_amount[test_pair]
                
                print(f"\n📋 Test pair: {test_pair}")
                print(f"📊 Current value: {current_value}")
                print(f"📊 Current amount: {current_amount}")
                
                if current_value != 0:
                    print(f"✅ Position detected for {test_pair}")
                    return True
                else:
                    print(f"❌ No position for {test_pair}")
                    return False
            else:
                print(f"❌ Test pair {test_pair} not found in positions")
                return False
                
        except Exception as e:
            print(f"❌ Error testing position detection: {e}")
            return False
    
    async def test_duplicate_prevention(self):
        """Test duplicate opening prevention logic"""
        print("\n🛡️ Testing duplicate opening prevention...")
        
        try:
            # Get current positions
            await self.strategy.get_balance()
            
            # Test the logic from create_order method
            for trading_pair in self.config.TRADING_PAIRS[:3]:  # Test first 3 pairs
                current_value = self.strategy.asset_value.get(trading_pair, Decimal('0'))
                current_status = self.strategy.status.get(trading_pair, 0)
                
                print(f"\n📋 Testing {trading_pair}:")
                print(f"📊 Current value: {current_value}")
                print(f"📊 Current status: {current_status}")
                
                # Simulate the duplicate prevention logic
                if current_value != 0 and (current_status == 1 or current_status == -1):
                    print(f"🛡️ Would skip opening new position for {trading_pair} (already have position)")
                else:
                    print(f"✅ Would allow opening position for {trading_pair}")
                    
        except Exception as e:
            print(f"❌ Error testing duplicate prevention: {e}")
    
    async def test_strategy_initialization(self):
        """Test strategy initialization and connection"""
        print("🚀 Testing strategy initialization...")
        
        try:
            # Test exchange connection
            self.strategy.exchange.load_markets()
            print("✅ Exchange connection successful")
            
            # Test market precision setup
            print(f"📊 Market precision data: {len(self.strategy.market_precision)} pairs")
            
            # Test candles setup
            print(f"📈 Candles data: {len(self.strategy.candles)} pairs")
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing strategy initialization: {e}")
            return False
    
    async def run_complete_test(self):
        """Run complete test suite"""
        print("🚀 OKX Strategy Test Suite")
        print("=" * 40)
        
        # Test 1: Strategy initialization
        print("\n📋 Test 1: Strategy Initialization")
        print("-" * 30)
        init_success = await self.test_strategy_initialization()
        
        if init_success:
            # Test 2: Position detection
            print("\n📋 Test 2: Position Detection")
            print("-" * 30)
            await self.test_position_detection()
            
            # Test 3: Duplicate opening prevention
            print("\n📋 Test 3: Duplicate Opening Prevention")
            print("-" * 30)
            await self.test_duplicate_prevention()
            
            print("\n🎉 All tests completed!")
        else:
            print("\n❌ Strategy initialization failed, skipping other tests")

async def main():
    test = StrategyTest()
    await test.run_complete_test()

if __name__ == "__main__":
    asyncio.run(main()) 