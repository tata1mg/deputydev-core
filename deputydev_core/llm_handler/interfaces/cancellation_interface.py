from abc import ABC, abstractmethod

class CancellationCheckerInterface(ABC):
    @abstractmethod
    def is_cancelled(self) -> bool: ...