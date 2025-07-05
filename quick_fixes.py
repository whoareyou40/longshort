#!/usr/bin/env python3
"""
快速修复脚本 - 解决OKX动量策略中最严重的问题
"""

import asyncio
import ccxt
import pandas as pd
import numpy as np
from decimal import Decimal
import logging
import time
from datetime import datetime
from okx_config import OKXConfig

class OKXMomentumStrategyFixed:
    """
    修复版本的OKX动量策略
    主要修复：
    1. 降低杠杆风险
    2. 添加止损机制
    3. 改进错误处理
    4. 添加数据质量检查
    """
    
    def __init__(self):
        self.config = OKXConfig()
        self.setup_logging()
        self.setup_exchange()
        
        # 策略状态
        self.last_ordered_ts = 0
        self.price = {}
        self.rsi = {}
        self.asset_value = {}
        self.asset_amount = {}
        self.status = {pair: 0 for pair in self.config.TRADING_PAIRS}
        self.target_value = {pair: 0 for pair in self.config.TRADING_PAIRS}
        
        # 风险控制参数
        self.max_daily_loss = Decimal("50")  # 最大日亏损50美元
        self.stop_loss_pct = Decimal("0.05")  # 5%止损
        self.max_leverage = 10  # 降低到10倍杠杆
        self.daily_pnl = Decimal("0")
        self.last_reset_date = datetime.now().date()
        
        # 持仓记录
        self.positions = {}
        self.stop_loss_orders = {}
        
        # 数据缓存
        self.candles = {}
        self.setup_candles()
        
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=getattr(logging, self.config.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('okx_momentum_strategy_fixed.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_exchange(self):
        """初始化交易所连接"""
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
            
        self.logger.info(f"连接到 {self.config.EXCHANGE_ID} {'沙盒' if self.config.SANDBOX else '实盘'} 模式")
        
    def setup_candles(self):
        """初始化K线数据结构"""
        for trading_pair in self.config.TRADING_PAIRS:
            self.candles[trading_pair] = {
                'data': [],
                'last_update': 0
            }
    
    def validate_data_quality(self, df):
        """验证数据质量"""
        if df is None or len(df) < 168:  # 至少需要7天数据
            return False
        
        # 检查是否有异常值
        price_changes = df['close'].pct_change().dropna()
        if len(price_changes) > 0 and abs(price_changes).max() > 0.5:  # 单日涨跌幅超过50%
            self.logger.warning("检测到异常价格变动")
            return False
        
        # 检查是否有缺失值
        if df.isnull().any().any():
            self.logger.warning("检测到缺失数据")
            return False
        
        return True
    
    async def fetch_candles_with_retry(self, symbol: str, timeframe: str = '1H', limit: int = 200, max_retries: int = 3):
        """带重试的K线数据获取"""
        for attempt in range(max_retries):
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                if self.validate_data_quality(df):
                    return df
                else:
                    self.logger.warning(f"数据质量检查失败: {symbol}")
                    return None
                    
            except Exception as e:
                self.logger.error(f"获取K线数据失败 (尝试 {attempt + 1}/{max_retries}): {symbol} - {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    return None
    
    async def get_factor(self):
        """计算动量因子（改进版本）"""
        self.logger.info("计算改进的动量因子...")
        
        for trading_pair in self.config.TRADING_PAIRS:
            try:
                # 获取K线数据
                current_time = time.time()
                if current_time - self.candles[trading_pair]['last_update'] > 3600:  # 每小时更新
                    df = await self.fetch_candles_with_retry(trading_pair, self.config.CANDLE_INTERVAL, self.config.MAX_CANDLES)
                    if df is not None:
                        self.candles[trading_pair]['data'] = df
                        self.candles[trading_pair]['last_update'] = current_time
                
                # 计算改进的动量分数
                df = self.candles[trading_pair]['data']
                if len(df) >= 168:  # 至少7天数据
                    close = df['close']
                    
                    # 使用移动平均计算动量
                    ma_short = close.rolling(12).mean()
                    ma_medium = close.rolling(24).mean()
                    ma_long = close.rolling(168).mean()
                    
                    # 计算动量分数
                    momentum_score = (
                        0.5 * (ma_short.iloc[-1] - ma_long.iloc[-1]) / ma_long.iloc[-1] +
                        0.3 * (ma_medium.iloc[-1] - ma_long.iloc[-1]) / ma_long.iloc[-1] +
                        0.2 * (close.iloc[-1] - ma_short.iloc[-1]) / ma_short.iloc[-1]
                    )
                    
                    # 考虑波动率调整
                    volatility = close.rolling(24).std() / close.rolling(24).mean()
                    if not pd.isna(volatility.iloc[-1]) and volatility.iloc[-1] > 0:
                        adjusted_score = momentum_score / (1 + volatility.iloc[-1])
                    else:
                        adjusted_score = momentum_score
                    
                    self.rsi[trading_pair] = adjusted_score
                    self.status[trading_pair] = 0
                    self.logger.debug(f"{trading_pair}: 动量分数={adjusted_score:.4f}")
                else:
                    self.logger.warning(f"数据不足: {trading_pair}")
                    
            except Exception as e:
                self.logger.error(f"计算因子失败: {trading_pair} - {e}")
        
        # 选择最佳和最差表现者
        if self.rsi:
            sorted_keys = sorted(self.rsi.keys(), key=lambda k: self.rsi[k])
            long_n = getattr(self.config, 'LONG_TOP_N', 1)
            short_n = getattr(self.config, 'SHORT_BOTTOM_N', 1)
            
            if len(sorted_keys) >= long_n + short_n:
                long_keys = sorted_keys[-long_n:]
                short_keys = sorted_keys[:short_n]
                
                # 重置所有状态
                for k in sorted_keys:
                    self.target_value[k] = 0
                    self.status[k] = 0
                
                # 设置做多
                for k in long_keys:
                    self.target_value[k] = self.config.TARGET_VALUE
                    self.status[k] = 1
                
                # 设置做空
                for k in short_keys:
                    self.target_value[k] = -self.config.TARGET_VALUE
                    self.status[k] = -1
                
                self.logger.info(f"做多: {long_keys}")
                self.logger.info(f"做空: {short_keys}")
            else:
                self.logger.warning(f"交易对不足: {len(sorted_keys)} < {long_n + short_n}")
        else:
            self.logger.warning("无动量数据")
    
    def check_daily_loss_limit(self):
        """检查日亏损限制"""
        current_date = datetime.now().date()
        
        # 重置日亏损计数
        if current_date != self.last_reset_date:
            self.daily_pnl = Decimal("0")
            self.last_reset_date = current_date
        
        # 检查是否超过日亏损限制
        if self.daily_pnl < -self.max_daily_loss:
            self.logger.warning(f"达到日亏损限制: {self.daily_pnl}")
            return False
        
        return True
    
    def set_leverage_safe(self, trading_pair: str):
        """安全设置杠杆"""
        try:
            # 降低杠杆到安全水平
            self.exchange.set_leverage(self.max_leverage, trading_pair, {'marginMode': 'cross'})
            self.logger.info(f"设置杠杆: {trading_pair} - {self.max_leverage}x")
        except Exception as e:
            self.logger.error(f"设置杠杆失败: {trading_pair} - {e}")
    
    def place_order_safe(self, trading_pair: str, side: str, order_type: str, amount: float, 
                        price: Optional[float] = None, pos_side: Optional[str] = None, 
                        reduce_only: bool = False) -> Optional[Dict]:
        """安全下单"""
        try:
            # 检查日亏损限制
            if not self.check_daily_loss_limit():
                self.logger.warning("超过日亏损限制，跳过下单")
                return None
            
            # 准备订单参数
            params = {
                'tdMode': 'cross',
                'reduceOnly': reduce_only,
            }
            
            if pos_side:
                params['posSide'] = pos_side
            
            # 下单
            if order_type == 'market':
                if side == 'buy':
                    order = self.exchange.create_market_buy_order(trading_pair, amount, params)
                else:
                    order = self.exchange.create_market_sell_order(trading_pair, amount, params)
            else:
                order = self.exchange.create_order(trading_pair, order_type, side, amount, price, params)
            
            self.logger.info(f"下单成功: {side} {order_type} {trading_pair} - {amount}")
            return order
            
        except Exception as e:
            self.logger.error(f"下单失败: {side} {order_type} {trading_pair} - {e}")
            return None
    
    def set_stop_loss(self, trading_pair: str, entry_price: float, side: str, amount: float):
        """设置止损订单"""
        try:
            if side == 'long':
                stop_price = entry_price * (1 - float(self.stop_loss_pct))
                order = self.place_order_safe(
                    trading_pair=trading_pair,
                    side='sell',
                    order_type='stop',
                    amount=amount,
                    price=stop_price,
                    pos_side='long',
                    reduce_only=True
                )
            else:  # short
                stop_price = entry_price * (1 + float(self.stop_loss_pct))
                order = self.place_order_safe(
                    trading_pair=trading_pair,
                    side='buy',
                    order_type='stop',
                    amount=amount,
                    price=stop_price,
                    pos_side='short',
                    reduce_only=True
                )
            
            if order:
                self.stop_loss_orders[trading_pair] = order['id']
                self.logger.info(f"设置止损: {trading_pair} - {stop_price}")
            
        except Exception as e:
            self.logger.error(f"设置止损失败: {trading_pair} - {e}")
    
    async def get_balance(self):
        """获取余额和持仓"""
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
            
            self.logger.info(f"当前持仓: {self.asset_value}")
            
        except Exception as e:
            self.logger.error(f"获取余额失败: {e}")
    
    async def create_order(self):
        """创建订单（改进版本）"""
        for trading_pair in self.config.TRADING_PAIRS:
            try:
                current_value = self.asset_value.get(trading_pair, Decimal('0'))
                current_status = self.status.get(trading_pair, 0)
                current_price = self.price.get(trading_pair, Decimal('0'))
                target_value = self.target_value.get(trading_pair, 0)
                
                if current_price == 0:
                    self.logger.warning(f"价格为零: {trading_pair}")
                    continue
                
                # 计算订单数量
                order_amount = abs(float(target_value)) / float(current_price)
                
                # 基础开仓/平仓逻辑
                if current_status == 1 and current_value == 0:
                    # 开多头
                    self.set_leverage_safe(trading_pair)
                    order = self.place_order_safe(
                        trading_pair=trading_pair,
                        side='buy',
                        order_type='market',
                        amount=order_amount,
                        pos_side='long',
                        reduce_only=False
                    )
                    if order:
                        # 设置止损
                        self.set_stop_loss(trading_pair, float(current_price), 'long', order_amount)
                        self.logger.info(f"开多头: {trading_pair} - {order_amount}")
                        
                elif current_status == -1 and current_value == 0:
                    # 开空头
                    self.set_leverage_safe(trading_pair)
                    order = self.place_order_safe(
                        trading_pair=trading_pair,
                        side='sell',
                        order_type='market',
                        amount=order_amount,
                        pos_side='short',
                        reduce_only=False
                    )
                    if order:
                        # 设置止损
                        self.set_stop_loss(trading_pair, float(current_price), 'short', order_amount)
                        self.logger.info(f"开空头: {trading_pair} - {order_amount}")
                        
                elif current_status == 0 and current_value > 0:
                    # 平多头
                    close_amount = float(abs(self.asset_amount[trading_pair]))
                    order = self.place_order_safe(
                        trading_pair=trading_pair,
                        side='sell',
                        order_type='market',
                        amount=close_amount,
                        pos_side='long',
                        reduce_only=True
                    )
                    if order:
                        self.logger.info(f"平多头: {trading_pair} - {close_amount}")
                        
                elif current_status == 0 and current_value < 0:
                    # 平空头
                    close_amount = float(abs(self.asset_amount[trading_pair]))
                    order = self.place_order_safe(
                        trading_pair=trading_pair,
                        side='buy',
                        order_type='market',
                        amount=close_amount,
                        pos_side='short',
                        reduce_only=True
                    )
                    if order:
                        self.logger.info(f"平空头: {trading_pair} - {close_amount}")
                
            except Exception as e:
                self.logger.error(f"创建订单失败: {trading_pair} - {e}")
    
    async def run_strategy(self):
        """运行策略"""
        self.logger.info("启动改进的OKX动量策略...")
        
        while True:
            try:
                current_time = time.time()
                
                # 检查执行时间
                if current_time - self.last_ordered_ts >= self.config.BUY_INTERVAL:
                    self.logger.info("执行策略...")
                    
                    # 执行策略步骤
                    await self.get_factor()
                    await self.get_balance()
                    await self.create_order()
                    
                    self.last_ordered_ts = current_time
                    self.logger.info("策略执行完成")
                
                # 等待下次检查
                await asyncio.sleep(60)
                
            except Exception as e:
                self.logger.error(f"策略循环错误: {e}")
                await asyncio.sleep(60)
    
    async def start(self):
        """启动策略"""
        try:
            # 测试连接
            self.exchange.load_markets()
            self.logger.info("OKX连接成功")
            
            # 启动策略
            await self.run_strategy()
            
        except Exception as e:
            self.logger.error(f"启动策略失败: {e}")

# 使用示例
if __name__ == "__main__":
    strategy = OKXMomentumStrategyFixed()
    asyncio.run(strategy.start()) 