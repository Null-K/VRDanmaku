from typing import Callable, Optional
from collections import deque

_log_callback: Optional[Callable] = None
_pending_logs: deque = deque(maxlen=100)


def set_log_callback(callback: Callable):
    global _log_callback
    _log_callback = callback
    
    while _pending_logs:
        msg, level = _pending_logs.popleft()
        try:
            callback(msg, level)
        except:
            pass


def log(msg: str, level: str = 'info'):
    global _log_callback, _pending_logs
    if _log_callback:
        try:
            _log_callback(msg, level)
        except:
            _pending_logs.append((msg, level))
    else:
        _pending_logs.append((msg, level))
