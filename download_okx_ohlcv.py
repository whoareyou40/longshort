import ccxt
import pandas as pd
import time
from tqdm import tqdm

# 币种池（可扩展到100个）
symbols = [
    'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'BNB/USDT:USDT', 'DOGE/USDT:USDT',
    'XRP/USDT:USDT', 'TON/USDT:USDT', 'ADA/USDT:USDT', 'AVAX/USDT:USDT', 'WLD/USDT:USDT'
    # ... 可继续添加
]
timeframe = '1h'  # 1小时K线
since = ccxt.okx().parse8601('2024-01-01T00:00:00Z')  # 起始时间，可自行调整
limit = 100  # OKX单次最多100根K线

exchange = ccxt.okx({
    'enableRateLimit': True,
})

all_dfs = {}

for symbol in tqdm(symbols):
    all_ohlcv = []
    since_local = since
    print(f"Downloading {symbol} ...")
    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since_local, limit=limit)
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            time.sleep(2)
            continue
        if not ohlcv:
            break
        all_ohlcv += ohlcv
        if len(ohlcv) < limit:
            break
        since_local = ohlcv[-1][0] + 1  # 下一根K线的起点
        time.sleep(exchange.rateLimit / 1000)
    if all_ohlcv:
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('date', inplace=True)
        all_dfs[symbol] = df
        # 可选：保存为单独csv
        df.to_csv(f'okx_{symbol.replace("/", "_").replace(":", "_")}_1h.csv')
    else:
        print(f"No data for {symbol}")

# 合并所有币种的收盘价为一个DataFrame
close_df = pd.DataFrame({symbol: df['close'] for symbol, df in all_dfs.items() if not df.empty})
close_df.to_csv('okx_all_close_1h.csv')
print('所有币种1小时收盘价已保存为 okx_all_close_1h.csv') 