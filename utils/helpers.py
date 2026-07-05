import re
from datetime import datetime, timedelta

def parse_time(time_str):
    """Parse time string like '1h', '30m', '2d' into seconds"""
    time_units = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        'w': 604800
    }
    
    match = re.match(r'(\d+)([smhdw])', time_str.lower())
    if not match:
        return None
    
    amount, unit = match.groups()
    return int(amount) * time_units[unit]

def format_time(seconds):
    """Format seconds into readable time"""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)