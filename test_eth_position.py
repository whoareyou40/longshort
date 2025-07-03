#!/usr/bin/env python3
"""
Test script to open a 10 USDT ETH position and detect it
"""

import ccxt
import os
from decimal import Decimal
from dotenv import load_dotenv
from okx_config import OKXConfig

load_dotenv()

class ETHPositionTest:
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
    
    def get_eth_price(self):
        """Get current ETH price"""
        try:
            ticker = self.exchange.fetch_ticker("ETH/USDT:USDT")
            price = float(ticker['last'])
            print(f"📊 Current ETH price: ${price:.2f}")
            return price
        except Exception as e:
            print(f"❌ Error getting ETH price: {e}")
            return None
    
    def calculate_contracts(self, usdt_amount, price):
        """Calculate number of contracts for given USDT amount"""
        try:
            # Get market info for contract size
            market = self.exchange.market("ETH/USDT:USDT")
            contract_size = float(market.get('contractSize', 1))
            
            # Calculate contracts: contracts = USDT_amount / (contract_size * price)
            contracts = usdt_amount / (contract_size * price)
            
            print(f"📈 Contract size: {contract_size}")
            print(f"📈 Calculated contracts: {contracts:.4f}")
            
            return contracts
        except Exception as e:
            print(f"❌ Error calculating contracts: {e}")
            return None
    
    def open_eth_position(self, usdt_amount=10):
        """Open ETH long position"""
        try:
            print(f"\n🚀 Opening ETH position for ${usdt_amount} USDT...")
            
            # Get current price
            price = self.get_eth_price()
            if not price:
                return False
            
            # Calculate contracts
            contracts = self.calculate_contracts(usdt_amount, price)
            if not contracts:
                return False
            
            # Set leverage and margin mode
            print("⚙️ Setting leverage and margin mode...")
            self.exchange.set_leverage(20, "ETH/USDT:USDT", {'marginMode': 'cross'})
            
            # Place order
            params = {
                'tdMode': 'cross',
                'reduceOnly': False,
                'posSide': 'long'
            }
            
            print(f"📝 Placing order: {contracts:.4f} contracts at market price...")
            order = self.exchange.create_market_buy_order("ETH/USDT:USDT", contracts, params)
            
            print(f"✅ Order placed successfully!")
            print(f"📋 Order ID: {order.get('id', 'N/A')}")
            print(f"📋 Status: {order.get('status', 'N/A')}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error opening ETH position: {e}")
            return False
    
    def check_eth_position(self):
        """Check if ETH position exists"""
        try:
            print(f"\n🔍 Checking ETH position...")
            
            # Fetch positions with SWAP filter
            positions = self.exchange.fetch_positions(params={'instType': 'SWAP'})
            
            # Get current price
            ticker = self.exchange.fetch_ticker("ETH/USDT:USDT")
            current_price = Decimal(str(ticker['last']))
            
            # Find ETH position
            eth_position = None
            for pos in positions:
                info = pos.get('info', {})
                inst_id = info.get('instId')
                pos_side = info.get('posSide', '').lower()
                contracts = float(info.get('pos', 0))
                
                if inst_id == "ETH/USDT:USDT" and contracts > 0:
                    eth_position = {
                        'side': pos_side,
                        'contracts': contracts,
                        'value': contracts * float(current_price)
                    }
                    break
            
            if eth_position:
                print(f"✅ Found ETH position!")
                print(f"📊 Side: {eth_position['side'].upper()}")
                print(f"📊 Contracts: {eth_position['contracts']:.4f}")
                print(f"📊 Value: ${eth_position['value']:.2f}")
                return eth_position
            else:
                print(f"❌ No ETH position found")
                return None
                
        except Exception as e:
            print(f"❌ Error checking ETH position: {e}")
            return None
    
    def run_test(self):
        """Run the complete test"""
        print("🚀 ETH Position Test")
        print("=" * 30)
        
        # Step 1: Check initial position
        print("\n📋 Step 1: Check Initial Position")
        print("-" * 20)
        initial_position = self.check_eth_position()
        
        # Step 2: Open position
        print("\n📋 Step 2: Open ETH Position")
        print("-" * 20)
        success = self.open_eth_position(10)
        
        if success:
            # Step 3: Check position after opening
            print("\n📋 Step 3: Check Position After Opening")
            print("-" * 20)
            final_position = self.check_eth_position()
            
            if final_position:
                print(f"\n🎉 Success! ETH position opened and detected!")
                print(f"📊 Position details: {final_position}")
            else:
                print(f"\n⚠️ Position opened but not detected immediately")
        else:
            print(f"\n❌ Failed to open ETH position")

if __name__ == "__main__":
    test = ETHPositionTest()
    test.run_test() 