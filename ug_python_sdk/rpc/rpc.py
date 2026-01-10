from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import uuid
from collections.abc import Generator
from typing import Any, AsyncIterator, Awaitable, Callable, Self

from . import channel as channel_module
from . import utils as rpc_utils

# Schemas:
#
# Request:
# {
#   "type": "request",
#   "uid": <str> - will be matched by the response
#   "kind": <str> - type of the request
#   ... - parameters of the request (if any)
# }
#
# Response (success):
# {
#   "type": "response",
#   "uid": <str> - matching the request
#   "kind": <str> - type of the response (typically matching the request)
#   ... - parameters of the response (if any)
# }
#
# Response (error):
# {
#   "type": "response",
#   "uid": <str> - matching the request
#   "kind": "error" - indicates that the request failed
#   "error": <str> - error message
# }
#
# Stream messages (symmetrical between client and server):
# {
#   "type": "stream",
#   "uid": <str> - stable throughout the stream lifecycle
#   "kind": <str> - type of the current message
#   ... - parameters of the message (if any)
# }
#
# Stream messages (symmetrical between client and server):
# {
#   "type": "stream",
#   "uid": <str> - stable throughout the stream lifecycle
#   "kind": <str> - type of the current message
#   ... - parameters of the message (if any)
# }
#
# Stream closure (success):
# {
#   "type": "stream",
#   "uid": <str> - matching the stream
#   "kind": "close"
# }
#
# Stream closure (error):
# {
#   "type": "stream"
#   "uid": <str> - matching the stream
#   "stream": "error"
#   ... - error message
# }
#
# Top-level error (interrupt all streams and requests):
# {
#   "type": "error"
#   "error": <str> - error message
#   # Note that this message does not have an "uid" field.
# }
#
# Top-level debug message:
# {
#   "type": "debug"
#   "message": <str> - Debug message sent to the other side
# }


@dataclasses.dataclass(frozen=True)
class ResponseFuture[T]:
    uid: str
    future: asyncio.Future[T]

    def __await__(self) -> Generator[None, None, T]:
        return self.future.__await__()

    def transform[U](self, callback: Callable[[T], U]) -> ResponseFuture[U]:
        new_future: asyncio.Future[U] = asyncio.Future()

        def resolver(f: asyncio.Future[T]) -> None:
            try:
                new_future.set_result(callback(f.result()))
            except Exception as e:
                new_future.set_exception(e)

        self.future.add_done_callback(resolver)
        return ResponseFuture(uid=self.uid, future=new_future)


type RequestHandler = Callable[[str, str, dict[str, Any]], Awaitable[None]]
type NewStreamHandler = Callable[[str, str, dict[str, Any]], Awaitable[None]]


class RPC:
    def __init__(
        self,
        name: str,
        channel: channel_module.Channel,
        logger: logging.Logger,
        *,
        request_handler: RequestHandler | None = None,
        new_stream_handler: NewStreamHandler | None = None,
    ) -> None:
        self.name = name
        self.channel = channel
        self._logger = logger
        self._exit_stack = contextlib.AsyncExitStack()
        self._incoming_by_stream_uid: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._future_by_uid: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._request_handler = request_handler
        self._new_stream_handler = new_stream_handler

    async def __aenter__(self) -> Self:
        await self._exit_stack.enter_async_context(self.channel)
        await self._exit_stack.enter_async_context(rpc_utils.scoped_background_task(self._recv_loop()))
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self._exit_stack.aclose()

    def _register_stream(self, uid: str) -> asyncio.Queue[dict[str, Any]]:
        result = self._incoming_by_stream_uid[uid] = asyncio.Queue()
        return result

    def _deregister_stream(self, uid: str) -> None:
        self._incoming_by_stream_uid.pop(uid)

    def _register_request(self, uid: str) -> asyncio.Future[dict[str, Any]]:
        result = self._future_by_uid[uid] = asyncio.Future()
        return result

    def _send_message(self, message: dict[str, Any]) -> None:
        self._logger.debug("%s: Sending message %r", self, message)
        self.channel.send(message)

    def _normalize_kind_and_fields(self, kind: str, fields: dict[str, Any] | None) -> dict[str, Any]:
        if fields is None:
            return {"kind": kind}
        if fields.get("kind", kind) != kind:
            raise ValueError(f"Conflicting kind in fields (kind={kind!r}, fields={fields!r})")
        return fields | {"kind": kind}

    def send_response(self, uid: str, kind: str, fields: dict[str, Any] | None = None) -> None:
        self._send_message(
            {
                "type": "response",
                "uid": uid,
            }
            | self._normalize_kind_and_fields(kind, fields)
        )

    def send_error_response(self, uid: str, error: str) -> None:
        self.send_response(uid, kind="error", fields={"error": error})

    def send_request_message(self, uid: str, kind: str, fields: dict[str, Any] | None = None) -> None:
        self._send_message(
            {
                "type": "request",
                "uid": uid,
            }
            | self._normalize_kind_and_fields(kind, fields)
        )

    def send_stream_message(self, uid: str, kind: str, fields: dict[str, Any] | None = None) -> None:
        self._send_message(
            {
                "type": "stream",
                "uid": uid,
            }
            | self._normalize_kind_and_fields(kind, fields)
        )

    def send_stream_error(self, uid: str, error: str | None = None, fields: dict[str, Any] | None = None) -> None:
        fields = (fields or {}) | ({"error": error} if error else {})
        self.send_stream_message(uid, kind="error", fields=fields)

    def send_toplevel_error(self, error: str) -> None:
        self._send_message(
            {
                "type": "error",
                "error": error,
            }
        )

    def send_debug_message(self, message: str) -> None:
        self._send_message(
            {
                "type": "debug",
                "message": message,
            }
        )

    async def fail(self, error: str) -> None:
        self._logger.error("%s: Failed: %s", self, error)
        self.send_toplevel_error(error)
        await self.channel.close()

    async def _on_message(self, message: dict[str, Any]) -> None:
        self._logger.debug("%s: Received message %r", self, message)
        match message:
            case {"type": "request", "uid": str(uid), "kind": str(kind), **fields}:
                await self.on_request(uid, kind, fields)
            case {"type": "response", "uid": str(uid), "kind": str(kind), **fields}:
                await self.on_response(uid, kind, fields)
            case {"type": "stream", "uid": str(uid), "kind": str(kind), **fields}:
                await self.on_stream_message(uid, kind, fields)
            case {"type": "error", "error": str(error)}:
                await self.on_error(error)
            case {"type": "debug", "message": str(debug_message)}:
                self.on_debug(debug_message)
            case _:
                await self.fail(f"Unexpected message format: {message!r}")

    async def _recv_loop(self) -> None:
        try:
            self._logger.info("%s: Starting recv loop", self)
            async for message in self.channel:
                try:
                    await self._on_message(message)
                except asyncio.CancelledError:
                    return
        except asyncio.CancelledError:
            return
        except Exception:
            self._logger.exception("%s: Error in RPC receive loop", self)
        finally:
            self._logger.info("%s: Recv loop exited", self)

    async def on_response(self, uid: str, kind: str, fields: dict[str, Any]) -> None:
        match (kind, fields):
            case ("error", {"error": str(error)}):
                if error == "session is not authenticated":
                    exc: Exception = PermissionError(error)
                else:
                    exc = Exception(error)
                self._future_by_uid[uid].set_exception(exc)
            case _ if kind != "error":
                self._future_by_uid[uid].set_result(dict(kind=kind, **fields))
            case _:
                await self.fail(f"Unexpected response message {kind=} {fields!r}")

    async def on_new_stream(self, uid: str, kind: str, fields: dict[str, Any]) -> None:
        self._logger.debug("%s: Received new stream %r %r", self, uid, kind)
        if self._new_stream_handler is not None:
            await self._new_stream_handler(uid, kind, fields)
        else:
            self.send_stream_error(uid, "Incoming streams are not supported")

    async def on_stream_message(self, uid: str, kind: str, fields: dict[str, Any]) -> None:
        if uid in self._incoming_by_stream_uid:
            self._incoming_by_stream_uid[uid].put_nowait(dict(kind=kind, **fields))
        else:
            await self.on_new_stream(uid, kind, fields)

    async def on_error(self, error: str) -> None:
        self._logger.error("%s: Received error (will close): %s", self, error)
        await self.channel.close()

    def on_debug(self, message: str) -> None:
        self._logger.debug("%s: Debug: %s", self, message)

    class Stream:
        def __init__(self, rpc: RPC, uid: str | None = None) -> None:
            self.rpc = rpc
            self.uid = uid or str(uuid.uuid4())
            self.closed = False

        def _validate_state(self) -> None:
            if self.closed:
                raise RuntimeError("stream is already closed")

        def send(self, kind: str, fields: dict[str, Any] | None = None) -> None:
            self._validate_state()
            self.rpc.send_stream_message(self.uid, kind=kind, fields=fields)

        async def recv(self) -> dict[str, Any] | None:
            self._validate_state()
            queue = self.rpc._incoming_by_stream_uid.get(self.uid)
            if queue is None:
                raise RuntimeError("stream is in an inconsistent state")
            result = await queue.get()
            match result:
                case {"kind": "error", "error": str(error)}:
                    self.rpc._deregister_stream(self.uid)
                    self.closed = True
                    raise Exception(error)
                case {"kind": "error"}:
                    self.rpc._deregister_stream(self.uid)
                    self.closed = True
                    raise Exception("Stream closed with unspecified error")
                case {"kind": "close"}:
                    self.rpc._deregister_stream(self.uid)
                    self.closed = True
                    return None
                case {"kind": str(kind)} if kind not in ("error", "close"):
                    return result
                case _:
                    error = f"Unexpected stream message format: {result!r}"
                    self.fail(error)
                    raise Exception(error)

        def fail(self, error: str | None = None, fields: dict[str, Any] | None = None) -> None:
            self.rpc.send_stream_error(self.uid, error=error, fields=fields)
            self.closed = True
            self.rpc._deregister_stream(self.uid)

        def close(self, fields: dict[str, Any] | None = None) -> None:
            self.rpc.send_stream_message(self.uid, kind="close", fields=fields)
            self.closed = True
            self.rpc._deregister_stream(self.uid)

        def close_silently(self) -> None:
            # Use to close the stream and deregister it without communicating
            # to the other party. This will make subsequent messages on this
            # stream UID appear like new stream requests.
            # Use carefully, this should not be commmonly used.
            self.closed = True
            self.rpc._deregister_stream(self.uid)

        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            if not self.closed:
                self.close()

        async def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
            try:
                while True:
                    if (message := await self.recv()) is not None:
                        yield message
                    else:
                        break
            except Exception:
                self.rpc._logger.exception("%s: Error in stream iterator", self.rpc)
                raise

    def make_request(self, kind: str, fields: dict[str, Any] | None = None) -> ResponseFuture[dict[str, Any]]:
        self._logger.debug("%s: Making request %r", self, kind)
        uid = str(uuid.uuid4())
        result = self._register_request(uid)
        self.send_request_message(uid, kind, fields)
        return ResponseFuture(uid=uid, future=result)

    def open_stream(self) -> Stream:
        stream = self.Stream(self)
        self._register_stream(stream.uid)
        return stream

    def accept_stream(self, uid: str) -> Stream:
        self._logger.debug("%s: Accepting stream %r", self, uid)
        stream = self.Stream(self, uid)
        self._register_stream(uid)
        return stream

    def force_deregister_stream(self, uid: str) -> None:
        # Public API to make all next requests on a stream appear like a public
        self._deregister_stream(uid)

    async def on_request(self, uid: str, kind: str, fields: dict[str, Any]) -> None:
        self._logger.debug("%s: Received request %r %r", self, uid, kind)
        if self._request_handler is not None:
            await self._request_handler(uid, kind, fields)
        else:
            self.send_error_response(uid, error="Incoming requests are not supported")

    def __str__(self) -> str:
        return f"RPC[{self.name}]"

    def __repr__(self) -> str:
        return f"<{self}>"
