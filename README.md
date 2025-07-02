# CCXT Momentum Strategy (OKX Version)

A CCXT-based implementation of a momentum trading strategy that automatically trades cryptocurrency pairs on OKX exchange based on their 24-hour price performance.

## Strategy Overview

This strategy implements a momentum-based trading approach:

1. **Momentum Calculation**: Calculates 24-hour price changes for all configured trading pairs
2. **Position Selection**: 
   - Takes **long positions** in the top 2 performing assets
   - Takes **short positions** in the bottom 2 performing assets
   - Closes positions in middle-performing assets
3. **Risk Management**: Limits to maximum 4 positions (2 long + 2 short) with fixed USD value per position
4. **Execution Frequency**: Rebalances every 4 hours

## Features

- **OKX Integration**: Uses CCXT library for OKX exchange connectivity
- **Async/Await**: Fully asynchronous implementation for better performance
- **Logging**: Comprehensive logging to file and console
- **Error Handling**: Robust error handling and recovery
- **Sandbox Support**: Safe testing with sandbox mode
- **Configurable**: Easy configuration through config file
- **Futures Trading**: Supports OKX perpetual futures trading

## Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd longshort
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Setup environment variables**:
```bash
cp env_example.txt .env
# Edit .env with your API credentials
```

## Configuration

### API Setup

**For OKX:**
1. Create an OKX account and generate API keys
2. Copy `env_example.txt` to `.env`
3. Add your API credentials to `.env`:
```
OKX_API_KEY=your_api_key_here
OKX_SECRET_KEY=your_secret_key_here
OKX_PASSPHRASE=your_passphrase_here
OKX_SANDBOX=true  # Set to false for live trading
```

**For Binance:**
1. Create a Binance account and generate API keys
2. Copy `env_example.txt` to `.env`
3. Add your API credentials to `.env`:
```
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here
BINANCE_SANDBOX=true  # Set to false for live trading
```

### Strategy Parameters

Edit `config.py` to customize strategy parameters:

- `TRADING_PAIRS`: List of trading pairs to monitor
- `TARGET_VALUE`: USD amount per position (default: $200)
- `BUY_INTERVAL`: Rebalancing interval in seconds (default: 4 hours)
- `CANDLE_INTERVAL`: Candle timeframe for calculations (default: 1h)
- `MAX_POSITIONS`: Maximum number of concurrent positions

## Usage

### Running the Strategy

**For Binance:**
```bash
python main.py
```

**For OKX:**
```bash
python okx_main.py
```

### Testing the Strategy

**For Binance:**
```bash
python test_strategy.py
```

**For OKX:**
```bash
python okx_test_strategy.py
```

### Stopping the Strategy

Press `Ctrl+C` to gracefully stop the strategy.

## Strategy Logic

### 1. Momentum Calculation
```python
# Calculate 24h price change
change_24h = (current_price - price_24h_ago) / price_24h_ago
```

### 2. Position Selection
- **Top 2 performers**: Long positions with $200 each
- **Bottom 2 performers**: Short positions with $200 each
- **Middle performers**: Close existing positions

### 3. Order Execution
- **Market orders**: Used for immediate execution
- **Position management**: Automatic position sizing based on current price
- **Order cancellation**: Cancels all open orders before new execution

## File Structure

```
longshort/
├── main.py                 # Main entry point (Binance version)
├── momentum_strategy.py    # Core strategy implementation (Binance)
├── config.py              # Configuration settings (Binance)
├── okx_main.py            # Main entry point (OKX version)
├── okx_momentum_strategy.py # Core strategy implementation (OKX)
├── okx_config.py          # Configuration settings (OKX)
├── requirements.txt       # Python dependencies
├── env_example.txt        # Environment variables template
├── test_strategy.py       # Test script (Binance)
├── okx_test_strategy.py   # Test script (OKX)
├── README.md             # This file
├── momentum_strategy.log  # Strategy logs (Binance)
└── okx_momentum_strategy.log # Strategy logs (OKX)
```

## Safety Features

1. **Sandbox Mode**: Default to sandbox for safe testing
2. **Rate Limiting**: Built-in rate limiting to respect exchange limits
3. **Error Recovery**: Automatic retry and error handling
4. **Graceful Shutdown**: Proper cleanup on exit
5. **Position Limits**: Maximum 4 positions to control risk

## Monitoring

The strategy provides comprehensive logging:

- **File logging**: All logs saved to `momentum_strategy.log`
- **Console output**: Real-time status updates
- **Error tracking**: Detailed error messages and stack traces

## Risk Disclaimer

⚠️ **Trading cryptocurrencies involves substantial risk of loss. This strategy is for educational purposes only. Always test thoroughly in sandbox mode before live trading.**

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is for educational purposes. Use at your own risk. 