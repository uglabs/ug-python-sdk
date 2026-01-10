import asyncio
import json
import logging
import webbrowser
from typing import Any, Literal

import httpx

from .admin_client import AdminClient
from .oauth import GoogleOAuthCallbackListener
from .session import Session


class Client:

    def __init__(self, url: str, logger: logging.Logger) -> None:
        self.url = url.rstrip("/")
        self.admin = AdminClient(self)
        self.access_token: str | None = None
        self.logger = logger

    def __str__(self) -> str:
        return f"client at {self.url!r}"

    def __repr__(self) -> str:
        return f"<{self}>"

    async def check_health(self) -> bool:
        try:
            await self._get("/api/health")
            return True
        except Exception:
            return False

    async def login(
        self,
        api_key: str,
        team_name: str | None = None,
        federated_id: str | None = None,
    ) -> None:
        result = await self._post(
            "/api/auth/login",
            api_key=api_key,
            team_name=team_name,
            federated_id=federated_id,
        )
        self.access_token = result["access_token"]

    async def login_with_google(self) -> None:
        async with GoogleOAuthCallbackListener() as listener:
            redirect_result = await self._post(
                "/api/auth/login/google/app",
                redirect_uri=listener.redirect_uri,
            )
            auth_url = redirect_result["authorization_url"]

            print(f"If your browser doesn't open automatically, please navigate to: {auth_url}")
            # Opening the browser sometimes hangs, so make sure to run this in a
            # separate thread.
            task = asyncio.create_task(asyncio.to_thread(webbrowser.open, auth_url))

            callback_details = await listener.wait_for_callback()
            # If we got the browser callback from the user manually opening
            # their browser, cancel the browser task. If the task already
            # completed, this will have no effect.
            task.cancel()

        result = await self._post(
            "/api/auth/login/google/authorize",
            code=callback_details.code,
            state=callback_details.state,
        )
        self.access_token = result["access_token"]

    def logout(self) -> None:
        self.access_token = None

    async def list_teams(self) -> list[dict[str, Any]]:
        result = await self._get("/api/teams")
        return result["teams"]

    async def list_policies(self) -> list[dict[str, Any]]:
        result = await self._get("/api/policies")
        return result["policies"]

    async def get_service_accounts(self) -> dict[str, Any]:
        result = await self._get("/api/users/service_accounts")
        return result

    async def get_me(self) -> dict[str, Any]:
        result = await self._get("/api/users/me")
        return result

    async def update_me(self, name: str | None = None) -> dict[str, Any]:
        result = await self._patch("/api/users/me", name=name)
        return result

    async def delete_me(self) -> None:
        await self._delete("/api/users/me")

    async def create_user(
        self,
        name: str,
        email: str | None = None,
        user_type: Literal["playerLogin", "playerCreate", "user"] = "user",
    ) -> dict[str, Any]:
        result = await self._post("/api/users", name=name, email=email, user_type=user_type)
        return result

    async def list_players(self) -> list[dict[str, Any]]:
        result = await self._get("/api/players")
        return result["players"]

    async def create_player(self, external_id: str) -> dict[str, Any]:
        result = await self._post("/api/players", external_id=external_id)
        return result

    async def get_player(self, player_pk: int) -> dict[str, Any]:
        result = await self._get(f"/api/players/{player_pk}")
        return result

    async def delete_player(self, player_pk: int) -> None:
        await self._delete(f"/api/players/{player_pk}")

    def session(self) -> Session:
        return Session.from_client(self, logger=self.logger)

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, **json: Any) -> dict[str, Any]:
        return await self._request("POST", path, json=json)

    async def _patch(self, path: str, **json: Any) -> dict[str, Any]:
        return await self._request("PATCH", path, json=json)

    async def _delete(self, path: str) -> None:
        await self._request("DELETE", path)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            url = f"{self.url}{path}"
            headers: dict[str, str] = {}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            response = await client.request(method, url, headers=headers, params=params, json=json)
            if not 200 <= response.status_code <= 299:
                raise self._error(method, path, response)
            if response.status_code == 204:  # No content response code
                return {}
            data = response.json()
            return data

    def _error(self, method: str, path: str, response: httpx.Response) -> Exception:
        try:
            data = response.json()
            if "error" in data:
                message = data["error"]
                if "traceback" in data:
                    message += "\n" + data["traceback"]
            elif "detail" in data:
                message = data["detail"]
            else:
                message = json.dumps(data, indent=4)
        except json.JSONDecodeError:
            message = response.text
        error_class: type[Exception]
        if response.status_code in (400, 404):
            error_class = ValueError
        elif response.status_code in (401, 403):
            error_class = PermissionError
        else:
            error_class = RuntimeError
        return error_class(f"{method} {path} failed with {response.status_code}: {message}")
