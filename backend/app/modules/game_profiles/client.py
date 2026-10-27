import re
import uuid
from urllib.parse import quote, urlparse

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings


class Player(BaseModel):
    faceit_player_id: uuid.UUID
    nickname: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    steam_id64: str | None = Field(default=None, pattern=r"^[0-9]{17}$")
    profile_url: str
    avatar_url: str | None = None
    elo: int | None = Field(default=None, ge=0)
    skill_level: int | None = Field(default=None, ge=1, le=10)


def parse_player(data: object) -> Player:
    if not isinstance(data, dict):
        raise HTTPException(502, "Invalid FACEIT response")
    try:
        games = data.get("games") or {}
        cs2 = games.get("cs2", {}) if isinstance(games, dict) else {}
        if not isinstance(cs2, dict):
            raise TypeError("Invalid games")
        steam = data.get("steam_id_64") or None
        if steam is not None and (not isinstance(steam, str) or not re.fullmatch(r"[0-9]{17}", steam)):
            steam = None
        avatar = data.get("avatar") or None
        if (not isinstance(avatar, str) or len(avatar) > 1024
                or urlparse(avatar).scheme != "https" or not urlparse(avatar).hostname
                or urlparse(avatar).username is not None or urlparse(avatar).password is not None):
            avatar = None
        nickname = data.get("nickname")
        if not isinstance(nickname, str):
            raise TypeError("Invalid nickname")
        return Player(faceit_player_id=data.get("player_id"), nickname=nickname,
                      steam_id64=steam, avatar_url=avatar,
                      profile_url=f"https://www.faceit.com/en/players/{quote(nickname, safe='')}",
                      elo=cs2.get("faceit_elo"), skill_level=cs2.get("skill_level"))
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(502, "Invalid FACEIT response") from None


class FaceitClient:
    def __init__(self, api_key: str | None = None, transport: httpx.BaseTransport | None = None):
        self.api_key = api_key if api_key is not None else get_settings().faceit_api_key
        self.transport = transport

    def _get(self, path: str, params: dict[str, str] | None = None) -> Player:
        if not self.api_key:
            raise HTTPException(503, "FACEIT integration is not configured")
        try:
            with httpx.Client(base_url="https://open.faceit.com/data/v4/", timeout=8.0,
                              follow_redirects=False, transport=self.transport,
                              headers={"Authorization": f"Bearer {self.api_key}"}) as client:
                response = client.get(path, params=params)
        except httpx.RequestError:
            raise HTTPException(502, "FACEIT service unavailable") from None
        if response.status_code == 404:
            raise HTTPException(404, "FACEIT player not found")
        if response.status_code in (401, 403):
            raise HTTPException(503, "FACEIT integration authorization failed")
        if response.status_code == 429:
            raise HTTPException(429, "FACEIT rate limit reached")
        if response.status_code != 200:
            raise HTTPException(502, "FACEIT service unavailable")
        try:
            payload = response.json()
        except ValueError:
            raise HTTPException(502, "Invalid FACEIT response") from None
        return parse_player(payload)

    def search(self, nickname: str) -> Player:
        return self._get("players", {"nickname": nickname})

    def get_player(self, player_id: uuid.UUID) -> Player:
        player = self._get(f"players/{player_id}")
        if player.faceit_player_id != player_id:
            raise HTTPException(502, "Invalid FACEIT response")
        return player


def get_faceit_client() -> FaceitClient:
    return FaceitClient()
