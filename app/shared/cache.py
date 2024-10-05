from datetime import datetime, timedelta
from typing import Dict, Any


class Cache:
    def __init__(self, timeout: int = 3600):
        self.data: Dict[str, Any] = {}
        self.timeout = timeout

    def get(self, key: str):
        if key in self.data:
            value, timestamp = self.data[key]
            if datetime.now() - timestamp < timedelta(seconds=self.timeout):
                return value
        return None

    def set(self, key: str, value: Any):
        self.data[key] = (value, datetime.now())


cache = Cache()
