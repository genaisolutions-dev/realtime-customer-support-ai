"""
Constants for Real-Time Customer Support AI backend

This module defines shared constants for status messages, error codes, and other
configuration values used across the backend.
"""

# Status values (used in WebSocket broadcasts)
STATUS_READY = "ready"
STATUS_LISTENING = "listening"
STATUS_PAUSED = "paused"
STATUS_PROCESSING = "processing"
STATUS_IDLE = "idle"
STATUS_DISCONNECTED = "disconnected"
STATUS_ERROR = "error"
STATUS_SHUTTING_DOWN = "shutting_down"
STATUS_MAX_CALLS_REACHED = "max_calls_reached"

# User-friendly error code mapping
# Maps exception types to user-friendly error codes
ERROR_CODE_MAPPING = {
    OSError: 'device_error',
    IOError: 'device_error',
    'ConnectionClosed': 'connection_lost',
    'ConnectionClosedError': 'connection_lost',
    'ConnectionResetError': 'connection_lost',
    'TimeoutError': 'timeout',
    'JSONDecodeError': 'invalid_json',
    KeyError: 'missing_field',
    ValueError: 'invalid_value',
    TypeError: 'invalid_type',
    'SessionExpired': 'session_expired',
    'InvalidAPIKey': 'invalid_api_key',
}

def get_error_code(exception):
    """
    Get user-friendly error code from exception

    Args:
        exception: Exception instance or exception class name string

    Returns:
        str: User-friendly error code
    """
    if isinstance(exception, str):
        # String exception type name
        return ERROR_CODE_MAPPING.get(exception, 'unknown_error')

    # Try exception type
    exc_type = type(exception)
    if exc_type in ERROR_CODE_MAPPING:
        return ERROR_CODE_MAPPING[exc_type]

    # Try exception class name
    exc_name = exc_type.__name__
    if exc_name in ERROR_CODE_MAPPING:
        return ERROR_CODE_MAPPING[exc_name]

    # Default to unknown
    return 'unknown_error'
