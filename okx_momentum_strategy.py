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
                
                # Reset all status and target values
                for k in sorted_keys:
                    self.target_value[k] = 0
                    self.status[k] = 0
                
                # Set long positions
                for k in long_keys:
                    self.target_value[k] = self.config.TARGET_VALUE
                    self.status[k] = 1  # Long
                
                # Set short positions
                for k in short_keys:
                    self.target_value[k] = -self.config.TARGET_VALUE
                    self.status[k] = -1  # Short
                
                self.logger.info(f"Top {long_n} long: {long_keys}")
                self.logger.info(f"Bottom {short_n} short: {short_keys}")
                
                # Log current positions that should be closed
                current_positions = []
                for pair, value in self.asset_value.items():
                    if value != 0:
                        status = self.status.get(pair, 0)
                        if status == 0:
                            current_positions.append(f"{pair} (should close)")
                        else:
                            current_positions.append(f"{pair} (keep {status})")
                
                if current_positions:
                    self.logger.info(f"Current positions: {current_positions}")
            else:
                self.logger.warning(f"Not enough pairs for strategy: {len(sorted_keys)} < {long_n + short_n}")
        else:
            self.logger.warning("No momentum data available")
                
    async def get_balance(self):
        """Get current positions and balances from OKX using proper position parsing"""
        try:
            # Fetch positions with SWAP filter
            positions = self.exchange.fetch_positions(params={'instType': 'SWAP'})
            
            for trading_pair in self.config.TRADING_PAIRS:
                # Get current price
                ticker = self.exchange.fetch_ticker(trading_pair)
                current_price = Decimal(str(ticker['last']))
                self.price[trading_pair] = current_price
                
                # Find position for this pair using both instId and symbol
                position_found = False
                for pos in positions:
                    info = pos.get('info', {})
                    inst_id = info.get('instId')
                    pos_side = info.get('posSide', '').lower()
                    contracts = float(info.get('pos', 0))
                    symbol = pos.get('symbol')
                    
                    # Match by instId or symbol and check if has position
                    # Convert trading_pair format (e.g., "ETH/USDT:USDT") to instId format (e.g., "ETH-USDT-SWAP")
                    expected_inst_id = trading_pair.replace('/', '-').replace(':USDT', '-SWAP')
                    
                    if ((inst_id == trading_pair or inst_id == expected_inst_id or symbol == trading_pair) and contracts > 0):
                        position_found = True
                        # Handle long position
                        if pos_side == 'long':
                            self.asset_amount[trading_pair] = Decimal(str(contracts))
                            self.asset_value[trading_pair] = Decimal(str(contracts)) * current_price
                            self.logger.debug(f"Found long position for {trading_pair}: {contracts} contracts")
                        # Handle short position
                        elif pos_side == 'short':
                            self.asset_amount[trading_pair] = Decimal(str(-contracts))
                            self.asset_value[trading_pair] = Decimal(str(-contracts)) * current_price
                            self.logger.debug(f"Found short position for {trading_pair}: {contracts} contracts")
                        break
                
                # No position found for this pair
                if not position_found:
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
                
                # Skip opening new positions if already have a position
                if current_value != 0 and (current_status == 1 or current_status == -1):
                    self.logger.info(f"Already have position for {trading_pair}, skipping opening new position.")
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
                
    async def print_positions_to_close(self):
        """打印当前有持仓但不在开仓范围内的币种、方向、张数"""
        try:
            # 获取所有持仓（不查价格）
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
            # 计算当前策略选中的币种
            selected = set()
            # 只保留当前status为1或-1的币种
            for pair, status in self.status.items():
                if status == 1 or status == -1:
                    selected.add(pair)
            # 打印不在开仓范围内的持仓
            to_close = []
            for symbol, pos_info in current_positions.items():
                if symbol not in selected:
                    to_close.append(pos_info)
            if to_close:
                print("\n🚨 当前有持仓但不在开仓范围内的币种:")
                for pos in to_close:
                    print(f"  - {pos['symbol']}: {pos['side']} {pos['contracts']} contracts")
            else:
                print("\n✅ 当前所有持仓都在策略开仓范围内")
        except Exception as e:
            print(f"❌ Error printing positions to close: {e}")
            import traceback
            traceback.print_exc()

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
                    
                    # 打印当前有持仓但不在开仓范围内的币种
                    await self.print_positions_to_close()
                    
                    # Close orphaned positions (not in current strategy)
                    await self.close_orphaned_positions()
                    
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

    async def get_all_positions(self):
        """Get all positions including those not in TRADING_PAIRS list"""
        try:
            print("🔍 get_all_positions 详细流程:")
            print("   📡 调用 fetch_positions(params={'instType': 'SWAP'})...")
            
            # Fetch all positions with SWAP filter
            positions = self.exchange.fetch_positions(params={'instType': 'SWAP'})
            print(f"   📊 原始持仓数据: {len(positions)} 条记录")
            
            # Track all positions found
            all_positions = {}
            
            for i, pos in enumerate(positions):
                print(f"   📋 处理第 {i+1} 条持仓数据:")
                print(f"      symbol: {pos.get('symbol', 'N/A')}")
                print(f"      info: {pos.get('info', {})}")
                
                info = pos.get('info', {})
                inst_id = info.get('instId')
                pos_side = info.get('posSide', '').lower()
                contracts = float(info.get('pos', 0))
                symbol = pos.get('symbol')
                
                print(f"      inst_id: {inst_id}")
                print(f"      pos_side: {pos_side}")
                print(f"      contracts: {contracts}")
                print(f"      symbol: {symbol}")
                
                # Only process positions with actual contracts
                if contracts > 0:
                    print(f"      ✅ 有持仓，获取价格...")
                    # Get current price for this symbol
                    try:
                        ticker = self.exchange.fetch_ticker(symbol)
                        current_price = Decimal(str(ticker['last']))
                        
                        position_info = {
                            'symbol': symbol,
                            'inst_id': inst_id,
                            'side': pos_side,
                            'contracts': contracts,
                            'value': contracts * float(current_price),
                            'price': current_price
                        }
                        all_positions[symbol] = position_info
                        print(f"      ✅ 添加到持仓列表: {symbol} - {pos_side} {contracts} contracts")
                        
                    except Exception as e:
                        print(f"      ❌ 获取价格失败: {symbol} - {e}")
                        self.logger.warning(f"Could not get price for {symbol}: {e}")
                else:
                    print(f"      ❌ 零持仓，跳过")
            
            print(f"   📊 最终持仓数量: {len(all_positions)}")
            return all_positions
            
        except Exception as e:
            print(f"   ❌ get_all_positions 异常: {e}")
            self.logger.error(f"Error fetching all positions: {e}", exc_info=True)
            return {}

    async def close_orphaned_positions(self):
        """Close positions that are not in the current strategy's selected pairs (status 1 or -1)"""
        try:
            print("\n🔍 close_orphaned_positions 详细流程:")
            print("=" * 50)
            
            # Get all current positions
            print("📊 Step 1: 获取所有当前持仓...")
            all_positions = await self.get_all_positions()
            print(f"   找到 {len(all_positions)} 个持仓:")
            for symbol, pos_info in all_positions.items():
                print(f"   - {symbol}: {pos_info['side']} {pos_info['contracts']} contracts")
            
            # Get current strategy selected positions (status 1 or -1)
            print(f"\n📋 Step 2: 获取当前策略选中的币种...")
            selected_positions = set()
            for pair, status in self.status.items():
                if status == 1 or status == -1:
                    selected_positions.add(pair)
                    print(f"   ✅ 策略选中: {pair} (status: {status})")
            
            print(f"   策略选中 {len(selected_positions)} 个币种")
            
            # Find orphaned positions (not in selected strategy positions)
            print(f"\n🔍 Step 3: 查找需要平仓的持仓...")
            orphaned_positions = {}
            for symbol, pos_info in all_positions.items():
                if symbol not in selected_positions:
                    orphaned_positions[symbol] = pos_info
                    print(f"   🚨 需要平仓: {symbol} - {pos_info['side']} {pos_info['contracts']} contracts (不在当前策略选中范围内)")
                else:
                    print(f"   ✅ 保留持仓: {symbol} - {pos_info['side']} {pos_info['contracts']} contracts (在当前策略选中范围内)")
            
            print(f"\n📊 Step 4: 平仓统计...")
            print(f"   总持仓数: {len(all_positions)}")
            print(f"   策略选中持仓数: {len(all_positions) - len(orphaned_positions)}")
            print(f"   需要平仓数: {len(orphaned_positions)}")
            
            if not orphaned_positions:
                print("   ✅ 没有需要平仓的持仓")
                return
            
            # Close orphaned positions
            print(f"\n🔄 Step 5: 开始平仓...")
            closed_count = 0
            failed_count = 0
            
            for symbol, pos_info in orphaned_positions.items():
                try:
                    print(f"\n   📝 正在平仓: {symbol} - {pos_info['side']} {pos_info['contracts']} contracts")
                    
                    # Set leverage and margin mode
                    print(f"   ⚙️ 设置杠杆和保证金模式...")
                    self.set_leverage_and_margin_mode(symbol)
                    
                    # Close position
                    if pos_info['side'] == 'long':
                        print(f"   📤 平仓多头: 卖出 {pos_info['contracts']} 张")
                        order = self.place_order(
                            trading_pair=symbol,
                            side='sell',
                            order_type='market',
                            amount=pos_info['contracts'],
                            pos_side='long',
                            reduce_only=True
                        )
                    elif pos_info['side'] == 'short':
                        print(f"   📤 平仓空头: 买入 {pos_info['contracts']} 张")
                        order = self.place_order(
                            trading_pair=symbol,
                            side='buy',
                            order_type='market',
                            amount=pos_info['contracts'],
                            pos_side='short',
                            reduce_only=True
                        )
                    
                    if order:
                        print(f"   ✅ 成功平仓: {symbol}")
                        closed_count += 1
                    else:
                        print(f"   ❌ 平仓失败: {symbol}")
                        failed_count += 1
                        
                except Exception as e:
                    print(f"   ❌ 平仓异常: {symbol} - {e}")
                    failed_count += 1
                    self.logger.error(f"Error closing orphaned position {symbol}: {e}", exc_info=True)
            
            print(f"\n📊 Step 6: 平仓结果统计...")
            print(f"   成功平仓: {closed_count} 个")
            print(f"   平仓失败: {failed_count} 个")
            print(f"   总计处理: {len(orphaned_positions)} 个持仓")
            
            if orphaned_positions:
                self.logger.info(f"Found and processed {len(orphaned_positions)} orphaned positions")
            else:
                self.logger.debug("No orphaned positions found")
                
        except Exception as e:
            print(f"❌ close_orphaned_positions 整体异常: {e}")
            self.logger.error(f"Error in close_orphaned_positions: {e}", exc_info=True) 