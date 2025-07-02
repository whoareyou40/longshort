#!/usr/bin/env python3
"""
Test script for the OKX momentum strategy
This script tests the strategy logic without making actual trades
"""

import asyncio
import pandas as pd
import numpy as np
import time
from decimal import Decimal
from okx_momentum_strategy import OKXMomentumStrategy
from okx_config import OKXConfig

class OKXTestMomentumStrategy(OKXMomentumStrategy):
    """Test version of the OKX momentum strategy that doesn't make real trades"""
    
    def __init__(self):
        super().__init__()
        self.test_mode = True
        self.logger.info("Running in OKX TEST MODE - no real trades will be executed")
        
    def setup_exchange(self):
        """Override to use test data instead of real exchange"""
        self.logger.info("Using test data instead of real OKX exchange")
        # Create mock exchange data for OKX trading pairs
        self.mock_prices = {
            "BTC/USDT:USDT": 45000,
            "ETH/USDT:USDT": 3000,
            "SOL/USDT:USDT": 100,
            "BNB/USDT:USDT": 300,
            "DOGE/USDT:USDT": 0.08,
            "XRP/USDT:USDT": 0.5,
            "TON/USDT:USDT": 2.5,
            "ADA/USDT:USDT": 0.4,
            "AVAX/USDT:USDT": 25,
            "WLD/USDT:USDT": 3.0
        }
        
    async def fetch_candles(self, symbol: str, timeframe: str = '1H', limit: int = 200):
        """Generate mock candle data for OKX testing"""
        # Create mock price data with some volatility
        base_price = self.mock_prices.get(symbol, 100)
        
        # Generate random price movements
        np.random.seed(hash(symbol) % 1000)  # Consistent seed for each symbol
        price_changes = np.random.normal(0, 0.02, limit)  # 2% daily volatility
        
        prices = [base_price]
        for change in price_changes[1:]:
            prices.append(prices[-1] * (1 + change))
            
        # Create OHLCV data
        ohlcv = []
        for i, price in enumerate(prices):
            high = price * (1 + abs(np.random.normal(0, 0.005)))
            low = price * (1 - abs(np.random.normal(0, 0.005)))
            open_price = prices[i-1] if i > 0 else price
            volume = np.random.uniform(1000, 10000)
            
            ohlcv.append([
                int(time.time() * 1000) - (limit - i) * 3600 * 1000,  # timestamp
                open_price,
                high,
                low,
                price,
                volume
            ])
            
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
        
    async def get_balance(self):
        """Mock balance fetching for OKX"""
        for trading_pair in self.config.TRADING_PAIRS:
            self.price[trading_pair] = Decimal(str(self.mock_prices.get(trading_pair, 100)))
            self.asset_amount[trading_pair] = Decimal('0')
            self.asset_value[trading_pair] = Decimal('0')
            
        self.logger.info(f"Mock OKX positions: {self.asset_value}")
        
    async def cancel_all_orders(self):
        """Mock order cancellation for OKX"""
        self.logger.info("Mock OKX: Cancelled all open orders")
        
    async def create_order(self):
        """Mock order creation for OKX - just log what would be done"""
        for trading_pair in self.config.TRADING_PAIRS:
            current_value = self.asset_value.get(trading_pair, Decimal('0'))
            current_status = self.status.get(trading_pair, 0)
            current_price = self.price.get(trading_pair, Decimal('0'))
            
            if current_price == 0:
                continue
                
            target_amount = abs(self.target_value.get(trading_pair, 0)) / current_price
            
            if current_status == 1 and current_value == 0:
                self.logger.info(f"TEST OKX: Would open LONG position for {trading_pair}: {target_amount:.6f} @ ${current_price}")
                
            elif current_status == -1 and current_value == 0:
                self.logger.info(f"TEST OKX: Would open SHORT position for {trading_pair}: {target_amount:.6f} @ ${current_price}")
                
            elif current_status == 0 and current_value > 0:
                self.logger.info(f"TEST OKX: Would close LONG position for {trading_pair}")
                
            elif current_status == 0 and current_value < 0:
                self.logger.info(f"TEST OKX: Would close SHORT position for {trading_pair}")

async def run_okx_test():
    """Run a test of the OKX strategy"""
    print("=" * 60)
    print("OKX MOMENTUM STRATEGY TEST")
    print("=" * 60)
    
    strategy = OKXTestMomentumStrategy()
    
    try:
        # Test factor calculation
        print("\n1. Testing OKX momentum factor calculation...")
        await strategy.get_factor()
        
        print("\n2. Testing OKX balance fetching...")
        await strategy.get_balance()
        
        print("\n3. Testing OKX order creation logic...")
        await strategy.create_order()
        
        print("\n4. OKX Strategy summary:")
        print(f"   - Trading pairs: {len(strategy.config.TRADING_PAIRS)}")
        print(f"   - Target value per position: ${strategy.config.TARGET_VALUE}")
        print(f"   - Rebalancing interval: {strategy.config.BUY_INTERVAL / 3600:.1f} hours")
        print(f"   - Candle interval: {strategy.config.CANDLE_INTERVAL}")
        print(f"   - Top performers: {strategy.max_key1}, {strategy.max_key2}")
        print(f"   - Bottom performers: {strategy.min_key1}, {strategy.min_key2}")
        
        print("\n5. OKX-specific features:")
        print(f"   - Uses OKX trading pair format (e.g., BTC/USDT:USDT)")
        print(f"   - Uses posSide parameter for position direction")
        print(f"   - Supports OKX perpetual futures")
        
        print("\n" + "=" * 60)
        print("OKX TEST COMPLETED SUCCESSFULLY")
        print("=" * 60)
        
    except Exception as e:
        print(f"OKX test failed with error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(run_okx_test()) 