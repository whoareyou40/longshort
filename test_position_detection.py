#!/usr/bin/env python3
"""
Simple test script to verify OKX position detection and prevent duplicate opening
"""

import asyncio
import ccxt
import os
from decimal import Decimal
from dotenv import load_dotenv
from okx_config import OKXConfig

load_dotenv()

class PositionTest:
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
        
    def get_positions(self):
        """Get current positions using the fixed method"""
        try:
            # Fetch positions with SWAP filter
            positions = self.exchange.fetch_positions(params={'instType': 'SWAP'})
            
            asset_value = {}
            asset_amount = {}
            
            # Test with a few trading pairs
            test_pairs = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
            
            for trading_pair in test_pairs:
                try:
                    # Get current price
                    ticker = self.exchange.fetch_ticker(trading_pair)
                    current_price = Decimal(str(ticker['last']))
                    
                    # Find position for this pair using instId
                    position_found = False
                    for pos in positions:
                        info = pos.get('info', {})
                        inst_id = info.get('instId')
                        pos_side = info.get('posSide', '').lower()
                        contracts = float(info.get('pos', 0))
                        
                        # Match by instId and check if has position
                        if inst_id == trading_pair and contracts > 0:
                            position_found = True
                            # Handle long position
                            if pos_side == 'long':
                                asset_amount[trading_pair] = Decimal(str(contracts))
                                asset_value[trading_pair] = Decimal(str(contracts)) * current_price
                                print(f"✅ Found LONG position for {trading_pair}: {contracts} contracts, value: ${asset_value[trading_pair]:.2f}")
                            # Handle short position
                            elif pos_side == 'short':
                                asset_amount[trading_pair] = Decimal(str(-contracts))
                                asset_value[trading_pair] = Decimal(str(-contracts)) * current_price
                                print(f"✅ Found SHORT position for {trading_pair}: {contracts} contracts, value: ${asset_value[trading_pair]:.2f}")
                            break
                    
                    # No position found for this pair
                    if not position_found:
                        asset_amount[trading_pair] = Decimal('0')
                        asset_value[trading_pair] = Decimal('0')
                        print(f"❌ No position for {trading_pair}")
                        
                except Exception as e:
                    print(f"❌ Error processing {trading_pair}: {e}")
                    asset_amount[trading_pair] = Decimal('0')
                    asset_value[trading_pair] = Decimal('0')
            
            print(f"\n📊 Summary:")
            print(f"Asset amounts: {asset_amount}")
            print(f"Asset values: {asset_value}")
            
            return asset_value, asset_amount
            
        except Exception as e:
            print(f"❌ Error fetching positions: {e}")
            return {}, {}
    
    def test_duplicate_opening_logic(self):
        """Test the logic that prevents duplicate opening"""
        print("\n🧪 Testing duplicate opening prevention logic...")
        
        # Simulate different scenarios
        scenarios = [
            {"current_value": Decimal('0'), "current_status": 1, "description": "No position, should open long"},
            {"current_value": Decimal('100'), "current_status": 1, "description": "Has position, should skip opening"},
            {"current_value": Decimal('0'), "current_status": -1, "description": "No position, should open short"},
            {"current_value": Decimal('-50'), "current_status": -1, "description": "Has position, should skip opening"},
            {"current_value": Decimal('0'), "current_status": 0, "description": "No position, neutral status"},
        ]
        
        for scenario in scenarios:
            current_value = scenario["current_value"]
            current_status = scenario["current_status"]
            description = scenario["description"]
            
            # Apply the same logic as in create_order
            should_skip = current_value != 0 and (current_status == 1 or current_status == -1)
            
            if should_skip:
                print(f"⏭️  {description}: SKIP (already have position)")
            else:
                print(f"✅ {description}: PROCEED")
    
    def test_with_simulated_positions(self):
        """Test with simulated positions to verify duplicate opening prevention"""
        print("\n📋 Test 4: Simulated Positions Test")
        print("-" * 30)
        
        # Simulate having some positions
        simulated_asset_value = {
            "BTC/USDT:USDT": Decimal('150.50'),  # Has long position
            "ETH/USDT:USDT": Decimal('0'),       # No position
            "SOL/USDT:USDT": Decimal('-75.25'),  # Has short position
        }
        
        test_scenarios = [
            {"pair": "BTC/USDT:USDT", "status": 1, "description": "BTC has long position, long signal"},
            {"pair": "BTC/USDT:USDT", "status": -1, "description": "BTC has long position, short signal"},
            {"pair": "ETH/USDT:USDT", "status": 1, "description": "ETH no position, long signal"},
            {"pair": "ETH/USDT:USDT", "status": -1, "description": "ETH no position, short signal"},
            {"pair": "SOL/USDT:USDT", "status": 1, "description": "SOL has short position, long signal"},
            {"pair": "SOL/USDT:USDT", "status": -1, "description": "SOL has short position, short signal"},
        ]
        
        for scenario in test_scenarios:
            pair = scenario["pair"]
            status = scenario["status"]
            description = scenario["description"]
            
            current_value = simulated_asset_value.get(pair, Decimal('0'))
            
            # Apply the same logic as in create_order
            should_skip = current_value != 0 and (status == 1 or status == -1)
            
            if should_skip:
                print(f"⏭️  {description}: SKIP (current_value=${current_value:.2f})")
            else:
                print(f"✅ {description}: PROCEED (current_value=${current_value:.2f})")
    
    def run_test(self):
        """Run the complete test"""
        print("🚀 Starting OKX Position Detection Test")
        print("=" * 50)
        
        # Test 1: Get current positions
        print("\n📋 Test 1: Current Position Detection")
        print("-" * 30)
        asset_value, asset_amount = self.get_positions()
        
        # Test 2: Duplicate opening logic
        print("\n📋 Test 2: Duplicate Opening Prevention Logic")
        print("-" * 30)
        self.test_duplicate_opening_logic()
        
        # Test 3: Show what would happen for each pair
        print("\n📋 Test 3: Strategy Decision for Each Pair")
        print("-" * 30)
        test_pairs = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
        
        for pair in test_pairs:
            current_value = asset_value.get(pair, Decimal('0'))
            current_status = 1  # Simulate long signal
            
            if current_value != 0:
                print(f"⏭️  {pair}: Has position (${current_value:.2f}), would SKIP opening new position")
            else:
                print(f"✅ {pair}: No position, would PROCEED to open position")
        
        # Test 4: Simulated positions
        self.test_with_simulated_positions()

if __name__ == "__main__":
    test = PositionTest()
    test.run_test() 