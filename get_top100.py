import ccxt

def get_top100_okx_perpetuals_by_volume():
    exchange = ccxt.okx()
    markets = exchange.load_markets()
    # Collect all USDT perpetual swap markets with their 24h volume
    swap_markets = []
    for m in markets.values():
        if m.get('type') == 'swap' and m['symbol'].endswith('/USDT:USDT'):
            # Use volCcy24h (24h volume in USDT) from market['info'] if available, else 0
            try:
                vol = float(m['info'].get('volCcy24h', 0))
            except Exception:
                vol = 0
            swap_markets.append((m['symbol'], vol))
    # Sort by volume descending and take top 100
    swap_markets.sort(key=lambda x: x[1], reverse=True)
    top100 = [symbol for symbol, _ in swap_markets[:100]]
    return top100

if __name__ == "__main__":
    print(get_top100_okx_perpetuals_by_volume())