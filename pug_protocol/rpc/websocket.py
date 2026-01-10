import contextlib
import json
import logging
from typing import Any, AsyncGenerator

import websockets
import websockets.asyncio
import websockets.asyncio.connection
import websockets.connection

from . import channel


class WebsocketBaseChannel(channel.BufferingBaseChannel):

    def __init__(self, name: str, logger: logging.Logger) -> None:
        super().__init__(name, logger)
        self.websocket: websockets.asyncio.connection.Connection | None = None

    @property
    def is_connected(self) -> bool:
        return self.websocket is not None

    async def _send_impl(self, message: dict[str, Any]) -> None:
        if self.websocket is None:
            raise RuntimeError("not connected")
        await self.websocket.send(json.dumps(message), text=True)

    async def recv(self) -> dict[str, Any] | None:
        if self.websocket is None:
            raise RuntimeError("not connected")
        try:
            # The underlying recv() method is cancel-safe and will not corrupt
            # data if cancelled.
            message = await self.websocket.recv()
            match message:
                case str(data):
                    return json.loads(data)
                case _:
                    raise RuntimeError("unexpected message type")
        except websockets.exceptions.ConnectionClosedOK:
            return None


class WebsocketClientChannel(WebsocketBaseChannel):

    def __init__(self, url: str, *, name: str, logger: logging.Logger) -> None:
        super().__init__(name, logger)
        self.url = url.replace("http://", "ws://").replace("https://", "wss://")

    async def connect(self) -> None:
        if self.is_connected:
            return
        await self._exit_stack.enter_async_context(self._with_socket())

    @contextlib.asynccontextmanager
    async def _with_socket(
        self,
    ) -> AsyncGenerator[None, None]:
        self._logger.info("%s: connecting to %s", self, self.url)
        # Increase max_size to 10MB to handle large images/messages
        # Default is 1MB (2**20), which is too small for Base64-encoded images
        async with websockets.connect(self.url, max_size=10 * 1024 * 1024) as ws:
            self._logger.info("%s: connected to %s", self, self.url)
            try:
                self.websocket = ws
                yield
            except Exception:
                self._logger.exception("%s: error in websocket context", self)
                raise
            finally:
                self._logger.info("%s: disconnecting from %s", self, self.url)
                self.websocket = None
