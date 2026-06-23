import asyncio
import time
from typing import Optional

class RateLimiter:
    def __init__(self, initial_delay: float = 1.0):
        self.current_delay = initial_delay
        self.consecutive_errors = 0
        self.last_flood_wait = 0
    
    async def handle_flood_wait(self, wait_seconds: int) -> float:
        """Handle FloodWait by sleeping and adjusting delay"""
        self.last_flood_wait = time.time()
        
        # Add 5 seconds buffer
        sleep_time = wait_seconds + 5
        await asyncio.sleep(sleep_time)
        
        # Auto-adjust delay upward
        self.current_delay = min(self.current_delay + 0.5, 10.0)
        self.consecutive_errors += 1
        
        return self.current_delay
    
    async def wait_with_delay(self, delay: float):
        """Wait for specified delay"""
        await asyncio.sleep(delay)
    
    def should_retry(self, error_count: int, max_retries: int) -> bool:
        """Check if should retry based on error count"""
        return error_count < max_retries
    
    def reset_errors(self):
        """Reset consecutive error counter"""
        self.consecutive_errors = 0
    
    def get_delay(self) -> float:
        """Get current delay value"""
        return self.current_delay
    
    def set_delay(self, delay: float):
        """Manually set delay"""
        self.current_delay = max(0.5, min(delay, 10.0))