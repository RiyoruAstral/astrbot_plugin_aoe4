import asyncio
import json
import re
import time
import xml.etree.ElementTree as ET
import aiohttp
from astrbot.api import logger

AOE4WORLD_API = "https://aoe4world.com/api/v0"
USER_AGENT = "astrbot-plugin-aoe4/1.1.0 (QQ bot plugin; contact: @RiyoruAstral)"

FLARESOLVERR_URL = "http://flaresolverr:8191/v1"

TIMEOUT_DEFAULT = 15
TIMEOUT_LEADERBOARD = 30


class RateLimiter:
    def __init__(self, max_calls: int = 10, period: float = 60.0):
        self.max_calls = max_calls
        self.period = period
        self._calls: list[float] = []

    async def wait(self):
        now = time.monotonic()
        self._calls = [t for t in self._calls if now - t < self.period]
        if len(self._calls) >= self.max_calls:
            sleep_for = self._calls[0] + self.period - now
            if sleep_for > 0:
                logger.info(f"RateLimiter: 达到上限，等待 {sleep_for:.1f}s")
                await asyncio.sleep(sleep_for)
        self._calls.append(time.monotonic())

FALLBACK_PATCHES = [
    {
        "date": "May 21, 2026", "title": "Age of Empires IV – Minor Patch 16.1.10056",
        "description": "晋朝靺鞨部民、长城壁垒加强，战国大名马匹训练、屋台等遭削弱。修复施法模式、崩溃及音频问题。"
    },
    {
        "date": "Apr 30, 2026", "title": "Age of Empires IV – Update 16.1.9737 (Season 13)",
        "description": "岳飞传 DLC 发布与新文明晋朝，排位赛季改为固定3个月周期，大量平衡调整与AI改进。"
    },
    {
        "date": "Mar 18, 2026", "title": "Age of Empires IV – Patch 15.4.8719",
        "description": "赛季12平衡性调整，多个文明改动与Bug修复。"
    },
    {
        "date": "Jan 27, 2026", "title": "Age of Empires IV – Patch 15.2.7380",
        "description": "修复丢失技能点问题，排位地图池调整，Torguud、工人象、治疗象等单位调整。"
    },
    {
        "date": "Nov 12, 2025", "title": "Age of Empires IV – Minor Patch 15.1.7149",
        "description": "工人象无法从不完整建筑中生成，已知问题列表更新。"
    },
]


class AoE4WorldClient:
    def __init__(self):
        self._session: aiohttp.ClientSession | None = None
        self._summary_cache: dict[int, dict | None] = {}
        self._summary_limiter = RateLimiter(max_calls=6, period=60)

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

    async def get_game_by_id(self, game_id: int) -> dict | None:
        return await self._request(f"/games/{game_id}")

    async def get_game_summary_by_id(self, game_id: int, profile_id: int | None = None) -> dict | None:
        if game_id in self._summary_cache:
            logger.debug(f"Game summary 命中缓存: {game_id}")
            cached = self._summary_cache[game_id]
            return dict(cached) if cached is not None else None

        if profile_id is None:
            game = await self.get_game_by_id(game_id)
            if not game or not game.get("teams"):
                self._summary_cache[game_id] = None
                return None
            for team in game["teams"]:
                for p in team:
                    if "profile_id" in p:
                        profile_id = p["profile_id"]
                        break
                if profile_id is not None:
                    break
            if profile_id is None:
                self._summary_cache[game_id] = None
                return None

        await self._summary_limiter.wait()

        url = f"https://aoe4world.com/players/{profile_id}/games/{game_id}/summary?camelize=true"

        data = await self._fetch_summary_via_flaresolverr(url)
        if data is not None:
            if data.get("players"):
                logger.info(f"Game summary 获取成功 (game_id={game_id})")
                self._summary_cache[game_id] = data
                return data
            logger.warning(f"Game summary 通过 FlareSolverr 获取到空数据 (game_id={game_id})")
            self._summary_cache[game_id] = None
            return None

        logger.info(f"FlareSolverr 不可用，放弃获取 summary (game_id={game_id})")
        self._summary_cache[game_id] = None
        return None

    async def _fetch_summary_via_flaresolverr(self, url: str) -> dict | None:
        last_error = None
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "cmd": "request.get",
                        "url": url,
                        "maxTimeout": 60000,
                    }
                    async with session.post(
                        FLARESOLVERR_URL,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=90)
                    ) as resp:
                        if resp.status != 200:
                            logger.warning(f"FlareSolverr({FLARESOLVERR_URL}) 返回 {resp.status} (attempt {attempt + 1})")
                            last_error = f"status {resp.status}"
                            await asyncio.sleep(2 ** attempt * 2)
                            continue
                        result = await resp.json()
                        solution = result.get("solution", {})
                        if solution.get("status") != 200:
                            logger.warning(f"FlareSolverr 目标返回 {solution.get('status')} (attempt {attempt + 1})")
                            last_error = f"target status {solution.get('status')}"
                            await asyncio.sleep(2 ** attempt * 2)
                            continue
                        body = solution.get("response", "")
                        if not body:
                            logger.warning("FlareSolverr 返回空内容")
                            last_error = "empty body"
                            await asyncio.sleep(2 ** attempt * 2)
                            continue
                        try:
                            return json.loads(body)
                        except json.JSONDecodeError:
                            pre_match = re.search(r'<pre>(.*)</pre>', body, re.DOTALL)
                            if pre_match:
                                return json.loads(pre_match.group(1))
                            match = re.search(r'({.*})', body, re.DOTALL)
                            if match:
                                return json.loads(match.group(1))
                            logger.warning("FlareSolverr 响应中未找到 JSON")
                            last_error = "json parse failed"
                            await asyncio.sleep(2 ** attempt * 2)
                            continue
            except (aiohttp.ClientConnectorError, asyncio.TimeoutError) as e:
                logger.warning(f"FlareSolverr({FLARESOLVERR_URL}) 连接失败 (attempt {attempt + 1}/3): {e}")
                last_error = str(e)
                await asyncio.sleep(2 ** attempt * 3)
                continue
            except Exception as e:
                logger.warning(f"FlareSolverr({FLARESOLVERR_URL}) 异常 (attempt {attempt + 1}/3): {type(e).__name__}: {e}")
                last_error = f"{type(e).__name__}: {e}"
                await asyncio.sleep(2 ** attempt * 2)
                continue

        logger.warning(f"FlareSolverr({FLARESOLVERR_URL}) 3次尝试均失败: {last_error}")
        return None

    async def get_leaderboard(self, leaderboard_key: str = "rm_solo", limit: int = 10) -> list[dict]:
        data = await self._request(f"/leaderboards/{leaderboard_key}", {"limit": limit}, timeout=TIMEOUT_LEADERBOARD)
        if not data:
            return []
        players = data.get("players", [])
        return players[:limit]

    async def get_patch_notes(self, limit: int = 5) -> list[dict]:
        session = await self._get_session()
        try:
            async with session.get(
                "https://www.ageofempires.com/news/feed/",
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"RSS feed 返回 {resp.status}")
                    return list(FALLBACK_PATCHES[:limit])
                text = await resp.text()
                patches = self._parse_rss_aoe4(text, limit)
                return patches if patches else list(FALLBACK_PATCHES[:limit])
        except Exception as e:
            logger.error(f"获取 patch notes 失败: {e}")
            return list(FALLBACK_PATCHES[:limit])

    @staticmethod
    def _parse_rss_aoe4(xml_text: str, limit: int) -> list[dict]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        patches = []
        for item in root.findall(".//item"):
            categories = [c.text for c in item.findall("category") if c.text]
            if "Age of Empires IV" not in categories:
                continue
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "")
            desc = re.sub(r'<[^>]+>', '', description)
            desc = re.sub(r'\s+', ' ', desc).strip()
            if len(desc) > 200:
                desc = desc[:197] + "..."
            from datetime import datetime
            try:
                dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
                date_str = dt.strftime("%b %d, %Y")
            except Exception:
                date_str = pub_date
            patches.append({
                "date": date_str,
                "title": title,
                "url": link,
                "description": desc,
            })
            if len(patches) >= limit:
                break
        return patches

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
