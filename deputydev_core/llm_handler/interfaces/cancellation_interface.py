from abc import ABC, abstractmethod


class CancellationCheckerInterface(ABC):
    @abstractmethod
    async def enforce_cancellation_with_cleanup(self) -> None: ...

    @abstractmethod
    def is_cancelled(self) -> bool: ...

    @abstractmethod
    async def stop_monitoring(self) -> None: ...
