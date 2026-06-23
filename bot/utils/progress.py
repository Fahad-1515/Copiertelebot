import time
from typing import Tuple

def calculate_progress(forwarded: int, total: int, bar_length: int = 20) -> str:
    """Generate progress bar"""
    if total == 0:
        return "[" + "░" * bar_length + "]"
    
    percent = forwarded / total
    filled = int(bar_length * percent)
    bar = "█" * filled + "░" * (bar_length - filled)
    return f"[{bar}] {int(percent * 100)}%"

def calculate_eta(start_time: float, forwarded: int, total: int) -> str:
    """Calculate estimated time remaining"""
    if forwarded == 0:
        return "calculating..."
    
    elapsed = time.time() - start_time
    rate = forwarded / elapsed
    if rate == 0:
        return "unknown"
    
    remaining = (total - forwarded) / rate
    return format_time(remaining)

def format_time(seconds: float) -> str:
    """Format seconds into readable time"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

def calculate_speed(forwarded: int, elapsed: float) -> float:
    """Calculate messages per second"""
    if elapsed == 0:
        return 0
    return forwarded / elapsed