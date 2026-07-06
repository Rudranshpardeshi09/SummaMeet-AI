import base64
from datetime import datetime
from typing import Any

def encode_cursor(value: Any) -> str:
    """Encode a cursor value to base64."""
    if isinstance(value, datetime):
        value_str = value.isoformat()
    else:
        value_str = str(value)
    return base64.b64encode(value_str.encode()).decode()

def decode_cursor(cursor: str, is_datetime: bool = False) -> Any:
    """Decode a cursor from base64."""
    try:
        decoded_str = base64.b64decode(cursor).decode()
        if is_datetime:
            return datetime.fromisoformat(decoded_str)
        return decoded_str
    except Exception:
        return None
