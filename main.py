#!/usr/bin/env python3
"""
Main entry point for the CCXT Momentum Strategy
"""

import asyncio
import signal
import sys
from momentum_strategy import MomentumStrategy

class StrategyRunner:
    def __init__(self):
        self.strategy = None
        self.running = False
        
    async def start(self):
        """Start the strategy"""
        try:
            self.strategy = MomentumStrategy()
            self.running = True
            
            # Setup signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            print("Starting CCXT Momentum Strategy...")
            print("Press Ctrl+C to stop")
            
            await self.strategy.start()
            
        except Exception as e:
            print(f"Error starting strategy: {e}")
            sys.exit(1)
            
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}. Shutting down gracefully...")
        self.running = False
        
    async def stop(self):
        """Stop the strategy"""
        if self.strategy:
            await self.strategy.stop()
        self.running = False

async def main():
    """Main function"""
    runner = StrategyRunner()
    
    try:
        await runner.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await runner.stop()
        print("Strategy stopped")

if __name__ == "__main__":
    asyncio.run(main()) 