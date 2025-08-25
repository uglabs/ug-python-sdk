import abc
import asyncio
import contextlib
import logging
from typing import Any, AsyncGenerator, Self

from . import utils


class Channel(abc.ABC):

    @abc.abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def close(self) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def send(self, message: dict[str, Any]) -> None:
        # Implementation notes:
        # - This method should return immediately and not block until the
        #   message is sent, and is thus sync.
        raise NotImplementedError()

    @abc.abstractmethod
    async def recv(self) -> dict[str, Any] | None:
        # Implementation notes:
        # - Receiving None indicates the connection has been closed.
        # - It should be safe to cancel calls to this coroutine without
        #   losing/corrupting data - i.e. it should be atomic.
        raise NotImplementedError()

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.close()

    async def __aiter__(self) -> AsyncGenerator[dict[str, Any], None]:
        while (message := await self.recv()) is not None:
            yield message


class BufferingBaseChannel(Channel):

    def __init__(self, name: str, logger: logging.Logger) -> None:
        super().__init__()
        self._name = name
        self._logger = logger
        self._exit_stack = contextlib.AsyncExitStack()
        self._send_task: asyncio.Task[None] | None = None
        self._send_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    @property
    @abc.abstractmethod
    def is_connected(self) -> bool:
        raise NotImplementedError()

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        await self._exit_stack.enter_async_context(utils.scoped_background_task(self.send_loop()))
        return self

    async def close(self) -> None:
        await self._exit_stack.aclose()

    def send(self, message: dict[str, Any]) -> None:
        if not self.is_connected:
            raise RuntimeError("not connected")
        self._send_queue.put_nowait(message)

    @abc.abstractmethod
    async def _send_impl(self, message: dict[str, Any]) -> None:
        raise NotImplementedError()

    async def send_loop(self) -> None:
        self._logger.info("%s: send loop started", self)
        try:
            while True:
                data = await self._send_queue.get()
                await self._send_impl(data)
        except asyncio.CancelledError:
            return
        except Exception:
            self._logger.exception("%s: send loop failed", self)
            raise
        finally:
            self._logger.info("%s: send loop finished", self)

    def __str__(self) -> str:
        return f"Channel[{self._name}]"

    def __repr__(self) -> str:
        return f"<{self}>"
