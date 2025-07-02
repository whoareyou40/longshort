import asyncio
import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from decimal import Decimal
from typing import Dict, List, Optional
import logging
import time
import math
from datetime import datetime
from okx_config import OKXConfig

class OKXMomentumStrategy:
    """
    OKX-specific momentum strategy that:
    - Calculates 24h price changes for all trading pairs
    - Takes long positions in top 2 performers
    - Takes short positions in bottom 2 performers
    - Closes positions for middle performers
    - Uses OKX-specific API calls and trading pair formats
    """
    
    def __init__(self):
        self.config = OKXConfig()
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
        
        # Market precision data
        self.market_precision = {}
        self.setup_market_precision()
        
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, self.config.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('okx_momentum_strategy.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_exchange(self):
        """Initialize CCXT exchange connection for OKX"""
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
        
    def setup_market_precision(self):
        """Setup market precision data for all trading pairs"""
        try:
            markets = self.exchange.load_markets()
            for trading_pair in self.config.TRADING_PAIRS:
                if trading_pair in markets:
                    market = markets[trading_pair]
                    self.market_precision[trading_pair] = {
                        'price_precision': market.get('precision', {}).get('price', 0),
                        'amount_precision': market.get('precision', {}).get('amount', 0),
                        'min_amount': market.get('limits', {}).get('amount', {}).get('min', 0),
                        'min_cost': market.get('limits', {}).get('cost', {}).get('min', 0)
                    }
                    self.logger.info(f"Market precision for {trading_pair}: {self.market_precision[trading_pair]}")
                else:
                    self.logger.warning(f"Market data not found for {trading_pair}")
        except Exception as e:
            self.logger.error(f"Error setting up market precision: {e}", exc_info=True)
        
    def setup_candles(self):
        """Initialize candles data structure"""
        for trading_pair in self.config.TRADING_PAIRS:
            self.candles[trading_pair] = {
                'data': [],
                'last_update': 0
            }
            
    async def fetch_candles(self, symbol: str, timeframe: str = '1H', limit: int = 200):
        """Fetch OHLCV candles from OKX exchange"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            self.logger.error(f"Error fetching candles for {symbol}: {e}", exc_info=True)
            return None
            
    async def get_factor(self):
        """Calculate momentum factors based on weighted 7d, 3d, 1d price changes"""
        self.logger.info("Calculating multi-factor momentum (7d, 3d, 1d weighted)...")
        
        for trading_pair in self.config.TRADING_PAIRS:
            try:
                # Fetch candles if needed
                current_time = time.time()
                if current_time - self.candles[trading_pair]['last_update'] > 3600:  # Update every hour
                    df = await self.fetch_candles(trading_pair, self.config.CANDLE_INTERVAL, self.config.MAX_CANDLES)
                    if df is not None and len(df) >= 24*7:
                        self.candles[trading_pair]['data'] = df
                        self.candles[trading_pair]['last_update'] = current_time
                
                # Calculate 7d, 3d, 1d change
                df = self.candles[trading_pair]['data']
                if len(df) >= 24*7:
                    close = df['close']
                    ret_1d = (close.iloc[-1] - close.iloc[-24]) / close.iloc[-24]
                    ret_3d = (close.iloc[-1] - close.iloc[-24*3]) / close.iloc[-24*3]
                    ret_7d = (close.iloc[-1] - close.iloc[-24*7]) / close.iloc[-24*7]
                    # 加权动量分数
                    score = 0.5 * ret_7d + 0.3 * ret_3d + 0.2 * ret_1d
                    self.rsi[trading_pair] = score
                    self.status[trading_pair] = 0
                    self.logger.debug(f"{trading_pair}: 7d={ret_7d:.4f}, 3d={ret_3d:.4f}, 1d={ret_1d:.4f}, score={score:.4f}")
                else:
                    self.logger.warning(f"Insufficient data for {trading_pair}")
                    
            except Exception as e:
                self.logger.error(f"Error calculating factor for {trading_pair}: {e}", exc_info=True)
        
        # Sort by momentum score and select top/bottom performers
        if self.rsi:
            sorted_keys = sorted(self.rsi.keys(), key=lambda k: self.rsi[k])
            long_n = getattr(self.config, 'LONG_TOP_N', 2)
            short_n = getattr(self.config, 'SHORT_BOTTOM_N', 2)
            if len(sorted_keys) >= long_n + short_n:
                long_keys = sorted_keys[-long_n:]
                short_keys = sorted_keys[:short_n]
                # Reset all
                for k in sorted_keys:
                    self.target_value[k] = 0
                    self.status[k] = 0
                for k in long_keys:
                    self.target_value[k] = self.config.TARGET_VALUE
                    self.status[k] = 1  # Long
                for k in short_keys:
                    self.target_value[k] = -self.config.TARGET_VALUE
                    self.status[k] = -1  # Short
                self.logger.info(f"Top {long_n} long: {long_keys}")
                self.logger.info(f"Bottom {short_n} short: {short_keys}")
                
    async def get_balance(self):
        """Get current positions and balances from OKX (reverted: no fetch_balance call)"""
        try:
            # Fetch positions
            positions = self.exchange.fetch_positions()
            
            for trading_pair in self.config.TRADING_PAIRS:
                # Get current price
                ticker = self.exchange.fetch_ticker(trading_pair)
                current_price = Decimal(str(ticker['last']))
                self.price[trading_pair] = current_price
                
                # Find position for this pair
                position = None
                for pos in positions:
                    if pos['symbol'] == trading_pair:
                        position = pos
                        break
                try:
                    size = position.get('size', 0) if position else 0
                except Exception as e:
                    self.logger.error(f"Position dict for {trading_pair}: {position}", exc_info=True)
                    size = 0
                if position and abs(float(size)) > 0:
                    amount = Decimal(str(size))
                    self.asset_amount[trading_pair] = amount
                    self.asset_value[trading_pair] = amount * current_price
                else:
                    self.asset_amount[trading_pair] = Decimal('0')
                    self.asset_value[trading_pair] = Decimal('0')
                    
            self.logger.info(f"Current positions: {self.asset_value}")
            
        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}", exc_info=True)
            
    async def cancel_all_orders(self):
        """Cancel all open orders on OKX"""
        try:
            open_orders = self.exchange.fetch_open_orders()
            for order in open_orders:
                try:
                    self.exchange.cancel_order(order['id'], order['symbol'])
                    self.logger.info(f"Cancelled order {order['id']} for {order['symbol']}")
                except Exception as e:
                    self.logger.error(f"Error cancelling order {order['id']}: {e}")
            self.logger.info("Cancelled all open orders")
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {e}", exc_info=True)

    def calculate_order_amount(self, trading_pair: str, target_value: float, current_price: float) -> Optional[float]:
        try:
            if trading_pair not in self.market_precision:
                self.logger.error(f"Market precision data not found for {trading_pair}")
                return None

            precision_data = self.market_precision[trading_pair]
            min_amount = precision_data['min_amount']
            amount_precision = precision_data['amount_precision']

            # 获取合约面值
            market = self.exchange.market(trading_pair)
            contract_size = float(market.get('contractSize', 1))

            # 计算张数（U本位永续：order_amount = value / (contract_size * price)）
            order_amount = abs(float(target_value)) / (contract_size * float(current_price))

            # 精度处理
            if isinstance(amount_precision, float):
                precision = int(abs(math.log10(amount_precision)))
                order_amount = round(order_amount, precision)
            else:
                # 有些合约只允许整数张
                order_amount = int(round(order_amount))

            # 检查最小下单量
            if order_amount < min_amount:
                self.logger.warning(f"Order amount {order_amount} for {trading_pair} is less than min amount {min_amount}, skipping order.")
                return None

            return order_amount

        except Exception as e:
            self.logger.error(f"Error calculating order amount for {trading_pair}: {e}", exc_info=True)
            return None

    def set_leverage_and_margin_mode(self, trading_pair: str):
        """Set leverage to 20x and cross margin mode for OKX"""
        try:
            # Set leverage to 20x
            self.exchange.set_leverage(20, trading_pair, {'marginMode': 'cross'})
            self.logger.info(f"Set leverage to 20x for {trading_pair}")
            
            # Set margin mode to cross (if needed)
            try:
                self.exchange.set_margin_mode('cross', trading_pair)
                self.logger.info(f"Set margin mode to cross for {trading_pair}")
            except Exception as e:
                # Cross mode might already be set
                self.logger.debug(f"Margin mode setting for {trading_pair}: {e}")
                
        except Exception as e:
            self.logger.error(f"Error setting leverage/margin for {trading_pair}: {e}", exc_info=True)

    def place_order(self, trading_pair: str, side: str, order_type: str, amount: float, 
                   price: Optional[float] = None, pos_side: Optional[str] = None, 
                   reduce_only: bool = False) -> Optional[Dict]:
        """Place order with proper OKX parameters and error handling"""
        try:
            # Prepare order parameters
            params = {
                'tdMode': 'cross',  # Cross margin mode
                'reduceOnly': reduce_only,
            }
            
            if pos_side:
                params['posSide'] = pos_side
                
            # Place the order
            if order_type == 'market':
                if side == 'buy':
                    order = self.exchange.create_market_buy_order(trading_pair, amount, params)
                else:
                    order = self.exchange.create_market_sell_order(trading_pair, amount, params)
            else:
                order = self.exchange.create_order(trading_pair, order_type, side, amount, price, params)
                
            self.logger.info(f"Successfully placed {side} {order_type} order for {trading_pair}: {amount} @ {price if price else 'market'}")
            return order
            
        except Exception as e:
            self.logger.error(f"Error placing {side} {order_type} order for {trading_pair}: {e}", exc_info=True)
            self.logger.error(f"Order parameters: side={side}, type={order_type}, amount={amount}, price={price}, params={params}")
            return None
            
    async def create_order(self):
        """Create orders based on strategy signals using optimized OKX API"""
        for trading_pair in self.config.TRADING_PAIRS:
            try:
                current_value = self.asset_value.get(trading_pair, Decimal('0'))
                current_status = self.status.get(trading_pair, 0)
                current_price = self.price.get(trading_pair, Decimal('0'))
                target_value = self.target_value.get(trading_pair, 0)
                
                if current_price == 0:
                    self.logger.warning(f"Current price is 0 for {trading_pair}, skipping order")
                    continue
                
                # Calculate order amount with precision and validation
                order_amount = self.calculate_order_amount(trading_pair, target_value, float(current_price))
                if order_amount is None:
                    continue
                
                # Handle long position opening
                if current_status == 1 and current_value == 0:
                    # Set leverage and margin mode before opening position
                    self.set_leverage_and_margin_mode(trading_pair)
                    
                    # Open long position
                    order = self.place_order(
                        trading_pair=trading_pair,
                        side='buy',
                        order_type='market',
                        amount=order_amount,
                        pos_side='long',
                        reduce_only=False
                    )
                    
                    if order:
                        self.logger.info(f"Opened long position for {trading_pair}: {order_amount}")
                    
                # Handle short position opening
                elif current_status == -1 and current_value == 0:
                    # Set leverage and margin mode before opening position
                    self.set_leverage_and_margin_mode(trading_pair)
                    
                    # Open short position
                    order = self.place_order(
                        trading_pair=trading_pair,
                        side='sell',
                        order_type='market',
                        amount=order_amount,
                        pos_side='short',
                        reduce_only=False
                    )
                    
                    if order:
                        self.logger.info(f"Opened short position for {trading_pair}: {order_amount}")
                    
                # Handle long position closing
                elif current_status == 0 and current_value > 0:
                    # Close long position
                    close_amount = float(abs(self.asset_amount[trading_pair]))
                    order = self.place_order(
                        trading_pair=trading_pair,
                        side='sell',
                        order_type='market',
                        amount=close_amount,
                        pos_side='long',
                        reduce_only=True
                    )
                    
                    if order:
                        self.logger.info(f"Closed long position for {trading_pair}: {close_amount}")
                    
                # Handle short position closing
                elif current_status == 0 and current_value < 0:
                    # Close short position
                    close_amount = float(abs(self.asset_amount[trading_pair]))
                    order = self.place_order(
                        trading_pair=trading_pair,
                        side='buy',
                        order_type='market',
                        amount=close_amount,
                        pos_side='short',
                        reduce_only=True
                    )
                    
                    if order:
                        self.logger.info(f"Closed short position for {trading_pair}: {close_amount}")
                    
            except Exception as e:
                self.logger.error(f"Error creating order for {trading_pair}: {e}", exc_info=True)
                
    async def run_strategy(self):
        """Main strategy loop"""
        self.logger.info("Starting OKX momentum strategy...")
        
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
            self.exchange.load_markets()
            self.logger.info("OKX exchange connection successful")
            
            # Start strategy
            await self.run_strategy()
            
        except Exception as e:
            self.logger.error(f"Failed to start strategy: {e}")
            
    async def stop(self):
        """Stop the strategy"""
        self.logger.info("Stopping strategy...")
        # await self.exchange.close()
        self.logger.info("Exchange object does not require close().") 