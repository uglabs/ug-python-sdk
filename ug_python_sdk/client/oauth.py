import asyncio
import os
import socket
from typing import Self

import aiohttp
import aiohttp.web
from pydantic import BaseModel


class GoogleOAuthCallbackDetails(BaseModel):
    code: str
    state: str


class GoogleOAuthCallbackListener:
    def __init__(self) -> None:
        self._app = aiohttp.web.Application()
        self._app.add_routes([aiohttp.web.get("/", self._handle_request)])
        self._runner = aiohttp.web.AppRunner(self._app)
        self._site: aiohttp.web.TCPSite | None = None
        self._future = asyncio.Future[GoogleOAuthCallbackDetails]()

    async def _handle_request(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        self._future.set_result(
            GoogleOAuthCallbackDetails(
                code=request.query["code"],
                state=request.query["state"],
            )
        )
        return aiohttp.web.Response(text="Authentication flow completed, you can close this browser window.")

    async def __aenter__(self) -> Self:
        # When running inside a docker container, we need to bind to traffic
        # from "other hosts" (such as the host machine which forwards traffic
        # into the container in a way that appears as if it's coming from a
        # different host.
        # Enable configuring this and also the binding port (so that can be
        # exposed in Docker) via an environment variable.
        host = os.environ.get("PUG_GOOGLE_OAUTH_CALLBACK_BIND_HOST", "localhost")
        port = int(os.environ.get("PUG_GOOGLE_OAUTH_CALLBACK_PORT", "0"))
        await self._runner.setup()
        self._site = aiohttp.web.TCPSite(self._runner, host, port)
        await self._site.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if self._site:
            await self._site.stop()
            self._site = None
        await self._runner.cleanup()

    @property
    def redirect_uri(self) -> str:
        if not self._site or not self._site._server:
            raise RuntimeError("Listener not started")
        sockets: list[socket.socket] = getattr(self._site._server, "sockets", [])
        if not sockets:
            raise RuntimeError("Failed to start local listener and obtain redirect URI")
        sock = sockets[0]
        port = sock.getsockname()[1]
        # Google OAuth requires listening on 127.0.0.1 or ::1, not localhost. See
        # https://developers.google.com/identity/protocols/oauth2/native-app#step-2:-send-a-request-to-googles-oauth-2.0-server
        if sock.family == socket.AF_INET6:
            return f"http://[::1]:{port}"
        else:
            return f"http://127.0.0.1:{port}"

    async def wait_for_callback(self) -> GoogleOAuthCallbackDetails:
        return await self._future
