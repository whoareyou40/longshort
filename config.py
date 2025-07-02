import os
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Exchange configuration
    EXCHANGE_ID = 'okx'
    API_KEY = os.getenv('OKX_API_KEY', '')
    SECRET_KEY = os.getenv('OKX_SECRET_KEY', '')
    PASSPHRASE = os.getenv('OKX_PASSPHRASE', '')
    SANDBOX = os.getenv('OKX_SANDBOX', 'true').lower() == 'true'
    
    # Strategy parameters
    TRADING_PAIRS = {
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "DOGE/USDT",
        "XRP/USDT", "TON/USDT", "ADA/USDT", "AVAX/USDT", "WLD/USDT"
    }
    
    # Strategy settings
    TARGET_VALUE = Decimal("200")  # USD amount per position
    BUY_INTERVAL = 60 * 60 * 4  # 4 hours in seconds
    CANDLE_INTERVAL = "1h"  # 1 hour candles
    MAX_CANDLES = 200
    
    # Risk management
    MAX_POSITIONS = 4  # Maximum number of positions (2 long + 2 short)
    
    # Logging
    LOG_LEVEL = "INFO" 