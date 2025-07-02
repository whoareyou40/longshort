import asyncio
import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from decimal import Decimal
from typing import Dict, List, Optional
import logging
import time
from datetime import datetime
from config import Config

class MomentumStrategy:
    """
    CCXT-based momentum strategy that:
    - Calculates 24h price changes for all trading pairs
    - Takes long positions in top 2 performers
    - Takes short positions in bottom 2 performers
    - Closes positions for middle performers
    """
    
    def __init__(self):
        self.config = Config()
        self.setup_logging()
        self.setup_exchange()
        
        # Strategy state
        self.last_ordered_ts = 0
        self.price = {}
        self.rsi = {}
        self.momentum = {}
        self.asset_value = {}
        self.asset_amount = {}
        self.status = {pair: 0 for pair in self.config.TRADING_PAIRS}
        self.target_value = {pair: 0 for pair in self.config.TRADING_PAIRS}
        
        # Top and bottom performers
        self.max_key1 = None
        self.max_key2 = None
        self.min_key1 = None
        self.min_key2 = None
        
        # Candles data
        self.candles = {}
        self.setup_candles()
        
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, self.config.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('momentum_strategy.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_exchange(self):
        """Initialize CCXT exchange connection"""
        exchange_class = getattr(ccxt, self.config.EXCHANGE_ID)
        self.exchange = exchange_class({
            'apiKey': self.config.API_KEY,
            'secret': self.config.SECRET_KEY,
            'password': self.config.PASSPHRASE,  # OKX requires passphrase
            'sandbox': self.config.SANDBOX,
            'enableRateLimit': True,
        })
        
        if self.config.SANDBOX:
            self.exchange.set_sandbox_mode(True)
            
        self.logger.info(f"Connected to {self.config.EXCHANGE_ID} {'sandbox' if self.config.SANDBOX else 'live'} mode")
        
    def setup_candles(self):
        """Initialize candles data structure"""
        for trading_pair in self.config.TRADING_PAIRS:
            self.candles[trading_pair] = {
                'data': [],
                'last_update': 0
            }
            
    async def fetch_candles(self, symbol: str, timeframe: str = '1h', limit: int = 200):
        """Fetch OHLCV candles from exchange"""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            self.logger.error(f"Error fetching candles for {symbol}: {e}")
            return None
            
    async def get_factor(self):
        """Calculate momentum factors based on 24h price changes"""
        self.logger.info("Calculating momentum factors...")
        
        for trading_pair in self.config.TRADING_PAIRS:
            try:
                # Fetch candles if needed
                current_time = time.time()
                if current_time - self.candles[trading_pair]['last_update'] > 3600:  # Update every hour
                    df = await self.fetch_candles(trading_pair, self.config.CANDLE_INTERVAL, self.config.MAX_CANDLES)
                    if df is not None and len(df) >= 24:
                        self.candles[trading_pair]['data'] = df
                        self.candles[trading_pair]['last_update'] = current_time
                
                # Calculate 24h change
                if len(self.candles[trading_pair]['data']) >= 24:
                    df = self.candles[trading_pair]['data']
                    current_price = df['close'].iloc[-1]
                    price_24h_ago = df['close'].iloc[-24]
                    change_24h = (current_price - price_24h_ago) / price_24h_ago
                    
                    self.rsi[trading_pair] = change_24h
                    self.status[trading_pair] = 0
                    self.logger.debug(f"{trading_pair}: 24h change = {change_24h:.4f}")
                else:
                    self.logger.warning(f"Insufficient data for {trading_pair}")
                    
            except Exception as e:
                self.logger.error(f"Error calculating factor for {trading_pair}: {e}")
                
        # Sort by momentum and select top/bottom performers
        if self.rsi:
            sorted_keys = sorted(self.rsi.keys(), key=lambda k: self.rsi[k])
            
            if len(sorted_keys) >= 4:
                self.min_key1 = sorted_keys[0]  # Worst performer
                self.min_key2 = sorted_keys[1]  # Second worst
                self.max_key2 = sorted_keys[-2]  # Second best
                self.max_key1 = sorted_keys[-1]  # Best performer
                
                # Set target values and status
                self.target_value[self.max_key1] = self.config.TARGET_VALUE
                self.status[self.max_key1] = 1  # Long position
                
                self.target_value[self.max_key2] = self.config.TARGET_VALUE
                self.status[self.max_key2] = 1  # Long position
                
                self.target_value[self.min_key1] = -self.config.TARGET_VALUE
                self.status[self.min_key1] = -1  # Short position
                
                self.target_value[self.min_key2] = -self.config.TARGET_VALUE
                self.status[self.min_key2] = -1  # Short position
                
                self.logger.info(f"Top performers: {self.max_key1} ({self.rsi[self.max_key1]:.4f}), {self.max_key2} ({self.rsi[self.max_key2]:.4f})")
                self.logger.info(f"Bottom performers: {self.min_key1} ({self.rsi[self.min_key1]:.4f}), {self.min_key2} ({self.rsi[self.min_key2]:.4f})")
                
    async def get_balance(self):
        """Get current positions and balances (no USDT balance check)"""
        try:
            # Fetch positions
            positions = await self.exchange.fetch_positions()
            
            for trading_pair in self.config.TRADING_PAIRS:
                # Get current price
                ticker = await self.exchange.fetch_ticker(trading_pair)
                current_price = Decimal(str(ticker['last']))
                self.price[trading_pair] = current_price
                
                # Find position for this pair
                position = None
                for pos in positions:
                    if pos['symbol'] == trading_pair:
                        position = pos
                        break
                if position and abs(float(position['size'])) > 0:
                    amount = Decimal(str(position['size']))
                    self.asset_amount[trading_pair] = amount
                    self.asset_value[trading_pair] = amount * current_price
                else:
                    self.asset_amount[trading_pair] = Decimal('0')
                    self.asset_value[trading_pair] = Decimal('0')
                    
            self.logger.info(f"Current positions: {self.asset_value}")
            
        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}")
            
    async def cancel_all_orders(self):
        """Cancel all open orders"""
        try:
            await self.exchange.cancel_all_orders()
            self.logger.info("Cancelled all open orders")
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {e}")
            
    async def create_order(self):
        """Create orders based on strategy signals"""
        for trading_pair in self.config.TRADING_PAIRS:
            try:
                current_value = self.asset_value.get(trading_pair, Decimal('0'))
                current_status = self.status.get(trading_pair, 0)
                current_price = self.price.get(trading_pair, Decimal('0'))
                
                if current_price == 0:
                    continue
                    
                # Calculate order size
                target_amount = abs(self.target_value.get(trading_pair, 0)) / current_price
                
                if current_status == 1 and current_value == 0:
                    # Open long position
                    await self.exchange.create_market_buy_order(
                        trading_pair, 
                        float(target_amount),
                        {'posSide': 'long'}  # OKX uses posSide instead of positionSide
                    )
                    self.logger.info(f"Opened long position for {trading_pair}: {target_amount}")
                    
                    # Set leverage
                    await self.exchange.set_leverage(20, trading_pair, {'marginMode': 'cross'})
                    
                elif current_status == -1 and current_value == 0:
                    # Open short position
                    await self.exchange.create_market_sell_order(
                        trading_pair, 
                        float(target_amount),
                        {'posSide': 'short'}  # OKX uses posSide instead of positionSide
                    )
                    self.logger.info(f"Opened short position for {trading_pair}: {target_amount}")
                    
                    # Set leverage
                    await self.exchange.set_leverage(20, trading_pair, {'marginMode': 'cross'})
                    
                elif current_status == 0 and current_value > 0:
                    # Close long position
                    await self.exchange.create_market_sell_order(
                        trading_pair, 
                        float(abs(self.asset_amount[trading_pair])),
                        {'posSide': 'long'}  # OKX uses posSide instead of positionSide
                    )
                    self.logger.info(f"Closed long position for {trading_pair}")
                    
                elif current_status == 0 and current_value < 0:
                    # Close short position
                    await self.exchange.create_market_buy_order(
                        trading_pair, 
                        float(abs(self.asset_amount[trading_pair])),
                        {'posSide': 'short'}  # OKX uses posSide instead of positionSide
                    )
                    self.logger.info(f"Closed short position for {trading_pair}")
                    
            except Exception as e:
                self.logger.error(f"Error creating order for {trading_pair}: {e}")
                
    async def run_strategy(self):
        """Main strategy loop"""
        self.logger.info("Starting momentum strategy...")
        
        while True:
            try:
                current_time = time.time()
                
                # Check if it's time to execute strategy
                if current_time - self.last_ordered_ts >= self.config.BUY_INTERVAL:
                    self.logger.info("Executing strategy...")
                    
                    # Execute strategy steps
                    await self.get_factor()
                    await self.cancel_all_orders()
                    await self.get_balance()
                    await self.create_order()
                    
                    self.last_ordered_ts = current_time
                    self.logger.info("Strategy execution completed")
                    
                # Wait before next iteration
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in strategy loop: {e}")
                await asyncio.sleep(60)
                
    async def start(self):
        """Start the strategy"""
        try:
            # Test connection
            await self.exchange.load_markets()
            self.logger.info("Exchange connection successful")
            
            # Start strategy
            await self.run_strategy()
            
        except Exception as e:
            self.logger.error(f"Failed to start strategy: {e}")
            
    async def stop(self):
        """Stop the strategy"""
        self.logger.info("Stopping strategy...")
        await self.exchange.close() 