from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client import Client


class AdminClient:

    def __init__(self, client: Client):
        self.client = client

    def __str__(self) -> str:
        return f"admin client at {self.client.url!r}"

    def __repr__(self) -> str:
        return f"<{self}>"

    async def get_settings(self) -> dict[str, Any]:
        result = await self.client._get("/api/settings")
        return result["settings"]

    async def list_teams(self) -> list[dict[str, Any]]:
        result = await self.client._get("/api/teams")
        return result["teams"]

    async def create_team(self, name: str) -> dict[str, Any]:
        result = await self.client._post("/api/teams", name=name)
        return result["team"]

    async def get_team(self, team_pk: int) -> dict[str, Any]:
        result = await self.client._get(f"/api/teams/{team_pk}")
        return result["team"]

    async def update_team(self, team_pk: int, name: str | None = None) -> dict[str, Any]:
        result = await self.client._patch(f"/api/teams/{team_pk}", name=name)
        return result["team"]

    async def delete_team(self, team_pk: int) -> None:
        await self.client._delete(f"/api/teams/{team_pk}")

    async def list_users(self) -> list[dict[str, Any]]:
        result = await self.client._get("/api/users")
        return result["users"]

    async def get_user(self, user_pk: int) -> dict[str, Any]:
        result = await self.client._get(f"/api/users/{user_pk}")
        return result["user"]

    async def update_user(self, user_pk: int, name: str | None = None) -> dict[str, Any]:
        result = await self.client._patch(f"/api/users/{user_pk}", name=name)
        return result["user"]

    async def delete_user(self, user_pk: int) -> None:
        await self.client._delete(f"/api/users/{user_pk}")

    async def add_user_to_team(self, user_pk: int, team_pk: int) -> None:
        await self.client._post(f"/api/users/{user_pk}/teams/{team_pk}")

    async def remove_user_from_team(self, user_pk: int, team_pk: int) -> None:
        await self.client._delete(f"/api/users/{user_pk}/teams/{team_pk}")
