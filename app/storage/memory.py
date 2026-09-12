from typing import Dict, List, Optional, Any
from .base import BaseStorage

class MemoryStorage(BaseStorage):
    def __init__(self):
        self._data: Dict[str, Any] = {}

    def save(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str) -> Optional[Any]:
        return self._data.get(key)

    def delete(self, key: str) -> None:
        if key in self._data:
            del self._data[key]

    def list(self) -> List[Any]:
        return list(self._data.values())

    def clear(self) -> None:
        self._data.clear()
