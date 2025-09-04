import asyncio
from typing import Optional

from deputydev_core.llm_handler.caches.code_gen_tasks_cache import CodeGenTasksCache


class CancellationChecker:
    """
    Periodic checker that monitors Redis for task cancellation across servers
    """

    def __init__(self, session_id: int, check_interval: float = 1) -> None:
        self.session_id = session_id
        self.check_interval = check_interval
        self.cancelled_event = asyncio.Event()
        self.cancelled_event.clear()
        self._checker_task: Optional[asyncio.Task] = None

    async def start_monitoring(self) -> None:
        """Start the periodic cancellation check"""
        # Reset our local cancelled event
        self.cancelled_event.clear()
        self._checker_task = asyncio.create_task(self.check_cancellation())

    async def stop_monitoring(self) -> None:
        """Stop the periodic cancellation check"""
        if self._checker_task and not self._checker_task.done():
            self._checker_task.cancel()
            try:
                await self._checker_task
            except asyncio.CancelledError:
                pass

    async def check_cancellation(self) -> None:
        """Periodically check Redis for cancellation status"""
        try:
            while True:
                if await CodeGenTasksCache.is_session_cancelled(self.session_id):
                    self.cancelled_event.set()
                    break
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            pass

    def is_cancelled(self) -> bool:
        """Check if cancellation has been detected"""
        return self.cancelled_event.is_set()

    async def __aenter__(self) -> "CancellationChecker":
        await self.start_monitoring()
        return self

    async def __aexit__(
        self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[object]
    ) -> None:
        await self.stop_monitoring()
