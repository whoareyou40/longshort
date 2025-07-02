import asyncio
import signal
import sys
from okx_momentum_strategy import OKXMomentumStrategy

class OKXStrategyRunner:
    def __init__(self):
        self.strategy = None
        self.running = False
        self.shutdown_event = asyncio.Event()
        
    async def start(self):
        try:
            self.strategy = OKXMomentumStrategy()
            self.running = True
            print("Starting OKX Momentum Strategy...")
            print("Press Ctrl+C to stop")
            await self.strategy.start()
        except Exception as e:
            print(f"Error starting OKX strategy: {e}")
            sys.exit(1)
        
    async def stop(self):
        if self.strategy:
            await self.strategy.stop()
        self.running = False
        self.shutdown_event.set()
        sys.exit(0)

def setup_signal_handlers(runner):
    loop = asyncio.get_event_loop()
    def _signal_handler():
        print("\nReceived exit signal. Shutting down gracefully...")
        asyncio.create_task(runner.stop())
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

async def main():
    runner = OKXStrategyRunner()
    setup_signal_handlers(runner)
    try:
        await runner.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await runner.shutdown_event.wait()
        print("OKX Strategy stopped")

if __name__ == "__main__":
    asyncio.run(main())