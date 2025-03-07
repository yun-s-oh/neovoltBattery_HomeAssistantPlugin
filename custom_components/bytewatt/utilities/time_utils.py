"""Time utilities for the Byte-Watt integration."""
import re
import logging

_LOGGER = logging.getLogger(__name__)


def sanitize_time_format(time_str):
    """
    Sanitize time format to ensure it's in HH:MM format.
    
    Args:
        time_str: Time string to sanitize
        
    Returns:
        Time string in HH:MM format, or None if invalid
    """
    if not time_str:
        return None
        
    # Try different formats
    time_formats = [
        # Standard time formats
        r'^(\d{1,2}):(\d{1,2})$',                # HH:MM
        r'^(\d{1,2}):(\d{1,2}):\d{1,2}$',        # HH:MM:SS
        r'^(\d{1,2}):(\d{1,2}):\d{1,2}\.\d+$',   # HH:MM:SS.ms
        
        # Home Assistant time picker formats
        r'^(\d{1,2}):(\d{1,2}) [APap][Mm]$',     # HH:MM AM/PM
    ]
    
    for pattern in time_formats:
        match = re.match(pattern, time_str)
        if match:
            hours, minutes = match.groups()
            hours = int(hours)
            minutes = int(minutes)
            
            # Validate hours and minutes
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                # Return in HH:MM format
                return f"{hours:02d}:{minutes:02d}"
    
    # Check if it's just the entity_id of a time entity
    if time_str.startswith('input_datetime.') or time_str.startswith('sensor.'):
        _LOGGER.warning(f"Time value appears to be an entity ID: {time_str}. " 
                       f"Please use the actual time value instead.")
        return None
    
    _LOGGER.error(f"Invalid time format: {time_str}. Expected format: HH:MM")
    return None