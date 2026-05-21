import asyncio
import aiohttp
from astrbot.api import logger

AOE4WORLD_API = "https://aoe4world.com/api/v0"
USER_AGENT = "AstrByAOE4SearchView/1.0.0 (QQ bot plugin; contact: @RiyoruAstral)"

TIMEOUT_DEFAULT = 15
TIMEOUT_LEADERBOARD = 30


class AoE4WorldClient:
    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": USER_AGENT}
            )
        return self._session

    async def _request(self, path: str, params: dict | None = None, timeout: int = TIMEOUT_DEFAULT) -> dict | None:
        session = await self._get_session()
        try:
            async with session.get(f"{AOE4WORLD_API}{path}", params=params, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    logger.warning(f"AoE4 World API 返回 {resp.status}: {path}")
                    return None
                return await resp.json()
        except asyncio.TimeoutError:
            logger.error(f"AoE4 World API 超时: {path}")
            return None
        except Exception as e:
            logger.error(f"AoE4 World API 请求失败 {path}: {type(e).__name__}: {e}")
            return None

    async def search_player(self, name: str) -> list[dict]:
        data = await self._request("/players/search", {"query": name})
        if not data:
            return []
        return data.get("players", [])

    async def get_player(self, profile_id: int) -> dict | None:
        return await self._request(f"/players/{profile_id}")

    async def get_player_games(self, profile_id: int, limit: int = 5) -> list[dict]:
        data = await self._request(f"/players/{profile_id}/games", {"limit": limit})
        if not data:
            return []
        return data.get("games", [])

    async def get_player_last_game(self, profile_id: int, include_stats: bool = False) -> dict | None:
        params = {"include_stats": "true"} if include_stats else None
        return await self._request(f"/players/{profile_id}/games/last", params)

    async def get_leaderboard(self, leaderboard_key: str = "rm_solo", limit: int = 10) -> list[dict]:
        data = await self._request(f"/leaderboards/{leaderboard_key}", {"limit": limit}, timeout=TIMEOUT_LEADERBOARD)
        if not data:
            return []
        players = data.get("players", [])
        return players[:limit]

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
