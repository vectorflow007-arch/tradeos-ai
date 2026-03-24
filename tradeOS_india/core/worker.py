"""
TradeOS India — Base worker thread with asyncio bridge.

Provides BaseWorker(QThread) that runs an asyncio event loop,
allowing async broker/DB/LLM calls without blocking the Qt main thread.
"""

import asyncio
from typing import Any, Callable, Coroutine, Optional

from PySide6.QtCore import QThread, Signal

from utils.logger import get_logger

log = get_logger("core.worker")


class BaseWorker(QThread):
    """QThread subclass with a built-in asyncio event loop.

    Subclass this and override `async_run()` for your async work.
    Signals:
        finished_signal: emitted when async_run completes (with result).
        error_signal: emitted if async_run raises an exception.
        progress_signal: emitted by subclass to report progress (0–100).
    """

    finished_signal = Signal(object)
    error_signal = Signal(str)
    progress_signal = Signal(int)

    def __init__(self, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = True

    def run(self) -> None:
        """Thread entry point — creates event loop and runs async_run."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            result = self._loop.run_until_complete(self.async_run())
            self.finished_signal.emit(result)
        except Exception as exc:
            log.error(f"Worker error: {exc}")
            self.error_signal.emit(str(exc))
        finally:
            self._loop.close()
            self._loop = None

    async def async_run(self) -> Any:
        """Override this method with your async work.

        Returns:
            Any result to emit via finished_signal.
        """
        raise NotImplementedError("Subclass must implement async_run()")

    def stop(self) -> None:
        """Request the worker to stop gracefully."""
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    @property
    def is_running(self) -> bool:
        """Check if the worker is still supposed to be running."""
        return self._running


class TaskWorker(BaseWorker):
    """Worker that runs a single async callable and emits the result.

    Usage:
        worker = TaskWorker(my_async_func, arg1, arg2, kwarg=val)
        worker.finished_signal.connect(on_done)
        worker.start()
    """

    def __init__(
        self,
        coro_func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self._coro_func = coro_func
        self._args = args
        self._kwargs = kwargs

    async def async_run(self) -> Any:
        """Run the stored coroutine function with its arguments."""
        return await self._coro_func(*self._args, **self._kwargs)


def run_async_in_thread(
    coro_func: Callable[..., Coroutine[Any, Any, Any]],
    *args: Any,
    on_done: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    **kwargs: Any,
) -> TaskWorker:
    """Convenience: run an async function in a QThread, return the worker.

    Args:
        coro_func: Async function to run.
        *args: Positional args for the function.
        on_done: Callback receiving the result.
        on_error: Callback receiving error message string.
        **kwargs: Keyword args for the function.

    Returns:
        The started TaskWorker instance (caller should keep a reference).
    """
    worker = TaskWorker(coro_func, *args, **kwargs)
    if on_done:
        worker.finished_signal.connect(on_done)
    if on_error:
        worker.error_signal.connect(on_error)
    worker.start()
    return worker


__all__ = ["BaseWorker", "TaskWorker", "run_async_in_thread"]
