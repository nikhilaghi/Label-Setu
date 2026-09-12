from abc import ABC, abstractmethod
from typing import List, Optional, Any

class BaseStorage(ABC):
    @abstractmethod
    def save(self, key: str, value: Any) -> None:
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass

    @abstractmethod
    def list(self) -> List[Any]:
        pass
