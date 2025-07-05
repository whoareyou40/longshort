#!/usr/bin/env python3
"""
周末反向策略
在周末（周五晚上8点到周一早上8点）运行反向策略
工作日运行正常动量策略
"""

import asyncio
import ccxt
import pandas as pd
import numpy as np
from decimal import Decimal
from datetime import datetime
import logging
import time
from okx_config import OKXConfig

class WeekendReverseStrategy:
    def __init__(self):
        self.config = OKXConfig()
        self.setup_logging()
        self.setup_exchange()
        
        # Strategy state
        self.last_ordered_ts = 0
        self.price = {}
        self.momentum = {}
        self.asset_value = {}
        self.asset_amount = {}
        self.status = {pair: 0 for pair in self.config.TRADING_PAIRS}
        self.target_value = {pair: 0 for pair in self.config.TRADING_PAIRS}
        
        # Weekend parameters
        self.weekend_start_hour = 20  # 周五晚上8点
        self.weekend_end_hour = 8     # 周一早上8点
        self.is_weekend_mode = False
        
    def setup_logging(self):
        logging.basicConfig(
            level=getattr(logging, self.config.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('weekend_reverse_strategy.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_exchange(self):
        exchange_class = getattr(ccxt, self.config.EXCHANGE_ID)
        self.exchange = exchange_class({
            'apiKey': self.config.API_KEY,
            'secret': self.config.SECRET_KEY,
            'password': self.config.PASSPHRASE,
            'sandbox': self.config.SANDBOX,
            'enableRateLimit': True,
        })
        
        if self.config.SANDBOX:
            self.exchange.set_sandbox_mode(True)
            
        self.logger.info(f"Connected to {self.config.EXCHANGE_ID} {'sandbox' if self.config.SANDBOX else 'live'} mode")
        
    def is_weekend_time(self) -> bool:
        """判断当前是否为周末策略时间"""
        now = datetime.now()
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        hour = now.hour
        
        # 周五晚上8点后
        if weekday == 4 and hour >= self.weekend_start_hour:
            return True
        # 周六全天
        elif weekday == 5:
            return True
        # 周日全天
        elif weekday == 6:
            return True
        # 周一早上8点前
        elif weekday == 0 and hour < self.weekend_end_hour:
            return True
        
        return False
    
    def calculate_momentum(self, df: pd.DataFrame) -> float:
        """计算24小时动量"""
        try:
            if len(df) < 25:
                return 0.0
            
            # 24小时价格变化率
            momentum = (df['close'].iloc[-1] - df['close'].iloc[-25]) / df['close'].iloc[-25]
            return momentum
            
        except Exception as e:
            self.logger.error(f"Error calculating momentum: {e}")
            return 0.0
    
    async def fetch_candles(self, symbol: str, timeframe: str = '1H', limit: int = 200):
        """获取K线数据"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            self.logger.error(f"Error fetching candles for {symbol}: {e}")
            return None
    
    async def get_factor(self):
        """计算动量因子"""
        self.logger.info("Calculating momentum factors...")
        
        # 检查是否为周末模式
        weekend_mode = self.is_weekend_time()
        if weekend_mode != self.is_weekend_mode:
            self.is_weekend_mode = weekend_mode
            if weekend_mode:
                self.logger.info("🔄 切换到周末反向策略模式")
            else:
                self.logger.info("🔄 切换到工作日正常动量策略模式")
        
        for trading_pair in self.config.TRADING_PAIRS:
            try:
                # 获取K线数据
                df = await self.fetch_candles(trading_pair, '1H', 200)
                if df is not None and len(df) >= 25:
                    momentum = self.calculate_momentum(df)
                    self.momentum[trading_pair] = momentum
                    self.status[trading_pair] = 0
                else:
                    self.logger.warning(f"Insufficient data for {trading_pair}")
                    
            except Exception as e:
                self.logger.error(f"Error calculating factor for {trading_pair}: {e}")
        
        # 排序并选择交易对
        if self.momentum:
            sorted_keys = sorted(self.momentum.keys(), key=lambda k: self.momentum[k])
            long_n = getattr(self.config, 'LONG_TOP_N', 2)
            short_n = getattr(self.config, 'SHORT_BOTTOM_N', 2)
            
            if len(sorted_keys) >= long_n + short_n:
                # 关键区别：根据是否为周末模式决定交易方向
                if self.is_weekend_mode:
                    # 周末反向策略：动量最高的做空，动量最低的做多
                    long_keys = sorted_keys[:short_n]  # 动量最低的做多
                    short_keys = sorted_keys[-long_n:]  # 动量最高的做空
                    self.logger.info(f"📅 周末反向策略 - 动量最低的{short_n}个做多: {long_keys}")
                    self.logger.info(f"📅 周末反向策略 - 动量最高的{long_n}个做空: {short_keys}")
                else:
                    # 工作日正常策略：动量最高的做多，动量最低的做空
                    long_keys = sorted_keys[-long_n:]  # 动量最高的做多
                    short_keys = sorted_keys[:short_n]  # 动量最低的做空
                    self.logger.info(f"📅 工作日正常策略 - 动量最高的{long_n}个做多: {long_keys}")
                    self.logger.info(f"📅 工作日正常策略 - 动量最低的{short_n}个做空: {short_keys}")
                
                # 重置所有状态
                for k in sorted_keys:
                    self.target_value[k] = 0
                    self.status[k] = 0
                
                # 设置做多仓位
                for k in long_keys:
                    self.target_value[k] = self.config.TARGET_VALUE
                    self.status[k] = 1
                
                # 设置做空仓位
                for k in short_keys:
                    self.target_value[k] = -self.config.TARGET_VALUE
                    self.status[k] = -1
            else:
                self.logger.warning(f"Not enough pairs for strategy: {len(sorted_keys)} < {long_n + short_n}")
        else:
            self.logger.warning("No momentum data available")
    
    async def get_balance(self):
        """获取当前持仓"""
        try:
            positions = self.exchange.fetch_positions(params={'instType': 'SWAP'})
            
            for trading_pair in self.config.TRADING_PAIRS:
                # 获取当前价格
                ticker = self.exchange.fetch_ticker(trading_pair)
                current_price = Decimal(str(ticker['last']))
                self.price[trading_pair] = current_price
                
                # 查找持仓
                position_found = False
                for pos in positions:
                    info = pos.get('info', {})
                    inst_id = info.get('instId')
                    pos_side = info.get('posSide', '').lower()
                    contracts = float(info.get('pos', 0))
                    symbol = pos.get('symbol')
                    
                    expected_inst_id = trading_pair.replace('/', '-').replace(':USDT', '-SWAP')
                    
                    if ((inst_id == trading_pair or inst_id == expected_inst_id or symbol == trading_pair) and contracts > 0):
                        position_found = True
                        if pos_side == 'long':
                            self.asset_amount[trading_pair] = Decimal(str(contracts))
                            self.asset_value[trading_pair] = Decimal(str(contracts)) * current_price
                        elif pos_side == 'short':
                            self.asset_amount[trading_pair] = Decimal(str(-contracts))
                            self.asset_value[trading_pair] = Decimal(str(-contracts)) * current_price
                        break
                
                if not position_found:
                    self.asset_amount[trading_pair] = Decimal('0')
                    self.asset_value[trading_pair] = Decimal('0')
                    
            self.logger.info(f"Current positions: {self.asset_value}")
            
        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}")
    
    async def cancel_all_orders(self):
        """取消所有订单"""
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
            self.logger.error(f"Error cancelling orders: {e}")
    
    def calculate_order_amount(self, trading_pair: str, target_value: float, current_price: float) -> float:
        """计算订单数量"""
        try:
            # 简化的计算，假设合约面值为1
            order_amount = abs(float(target_value)) / float(current_price)
            return round(order_amount, 4)  # 保留4位小数
        except Exception as e:
            self.logger.error(f"Error calculating order amount for {trading_pair}: {e}")
            return 0.0
    
    def set_leverage_and_margin_mode(self, trading_pair: str):
        """设置杠杆和保证金模式"""
        try:
            self.exchange.set_leverage(20, trading_pair, {'marginMode': 'cross'})
            self.logger.info(f"Set leverage to 20x for {trading_pair}")
        except Exception as e:
            self.logger.error(f"Error setting leverage/margin for {trading_pair}: {e}")
    
    def place_order(self, trading_pair: str, side: str, order_type: str, amount: float, 
                   pos_side: str = None, reduce_only: bool = False):
        """下单"""
        try:
            params = {
                'tdMode': 'cross',
                'reduceOnly': reduce_only,
            }
            
            if pos_side:
                params['posSide'] = pos_side
                
            if order_type == 'market':
                if side == 'buy':
                    order = self.exchange.create_market_buy_order(trading_pair, amount, params)
                else:
                    order = self.exchange.create_market_sell_order(trading_pair, amount, params)
            else:
                order = self.exchange.create_order(trading_pair, order_type, side, amount, None, params)
                
            self.logger.info(f"Successfully placed {side} {order_type} order for {trading_pair}: {amount}")
            return order
            
        except Exception as e:
            self.logger.error(f"Error placing {side} {order_type} order for {trading_pair}: {e}")
            return None
    
    async def create_order(self):
        """创建订单"""
        for trading_pair in self.config.TRADING_PAIRS:
            try:
                current_value = self.asset_value.get(trading_pair, Decimal('0'))
                current_status = self.status.get(trading_pair, 0)
                current_price = self.price.get(trading_pair, Decimal('0'))
                target_value = self.target_value.get(trading_pair, 0)
                
                if current_price == 0:
                    continue
                
                order_amount = self.calculate_order_amount(trading_pair, target_value, float(current_price))
                if order_amount == 0:
                    continue
                
                # 开仓逻辑
                if current_status == 1 and current_value == 0:
                    # 开多头
                    self.set_leverage_and_margin_mode(trading_pair)
                    order = self.place_order(
                        trading_pair=trading_pair,
                        side='buy',
                        order_type='market',
                        amount=order_amount,
                        pos_side='long',
                        reduce_only=False
                    )
                    if order:
                        strategy_type = "周末反向" if self.is_weekend_mode else "工作日正常"
                        self.logger.info(f"[{strategy_type}] 开多头 {trading_pair}: {order_amount}")
                        
                elif current_status == -1 and current_value == 0:
                    # 开空头
                    self.set_leverage_and_margin_mode(trading_pair)
                    order = self.place_order(
                        trading_pair=trading_pair,
                        side='sell',
                        order_type='market',
                        amount=order_amount,
                        pos_side='short',
                        reduce_only=False
                    )
                    if order:
                        strategy_type = "周末反向" if self.is_weekend_mode else "工作日正常"
                        self.logger.info(f"[{strategy_type}] 开空头 {trading_pair}: {order_amount}")
                        
                elif current_status == 0 and current_value > 0:
                    # 平多头
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
                        self.logger.info(f"平多头 {trading_pair}: {close_amount}")
                        
                elif current_status == 0 and current_value < 0:
                    # 平空头
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
                        self.logger.info(f"平空头 {trading_pair}: {close_amount}")
                
            except Exception as e:
                self.logger.error(f"Error creating order for {trading_pair}: {e}")
    
    async def run_strategy(self):
        """主策略循环"""
        self.logger.info("Starting weekend reverse strategy...")
        
        while True:
            try:
                current_time = time.time()
                
                if current_time - self.last_ordered_ts >= self.config.BUY_INTERVAL:
                    self.logger.info("Executing strategy...")
                    
                    await self.get_factor()
                    await self.cancel_all_orders()
                    await self.get_balance()
                    await self.create_order()
                    
                    self.last_ordered_ts = current_time
                    self.logger.info("Strategy execution completed")
                    
                await asyncio.sleep(60)
                
            except Exception as e:
                self.logger.error(f"Error in strategy loop: {e}")
                await asyncio.sleep(60)
    
    async def start(self):
        """启动策略"""
        try:
            self.exchange.load_markets()
            self.logger.info("OKX exchange connection successful")
            await self.run_strategy()
        except Exception as e:
            self.logger.error(f"Failed to start strategy: {e}")

if __name__ == "__main__":
    strategy = WeekendReverseStrategy()
    try:
        asyncio.run(strategy.start())
    except KeyboardInterrupt:
        print("Strategy stopped by user")
    except Exception as e:
        print(f"Strategy error: {e}") 