import asyncio
import contextlib
from typing import Any, AsyncGenerator, Coroutine


@contextlib.asynccontextmanager
async def scoped_background_task(coro: Coroutine[Any, Any, Any]) -> AsyncGenerator[asyncio.Task[Any], None]:
    task: asyncio.Task[Any] | None = None
    try:
        task = asyncio.create_task(coro)
        yield task
    finally:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
