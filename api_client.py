import asyncio
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
import aiohttp
from astrbot.api import logger

AOE4WORLD_API = "https://aoe4world.com/api/v0"
USER_AGENT = "astrbot_plugin_aoe4/1.1.0 (QQ bot plugin; contact: @RiyoruAstral)"

FLARESOLVERR_URL = "http://localhost:8191/v1"
_FLARESOLVERR_PROCESS: asyncio.subprocess.Process | None = None
_FLARESOLVERR_LOCK = asyncio.Lock()
_FLARESOLVERR_ATTEMPTED = False

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


async def _run_cmd(*args, timeout: int = 180, env: dict | None = None) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="ignore") if stdout else ""
        rc = proc.returncode if proc.returncode is not None else 0
        return rc, output
    except asyncio.TimeoutError:
        return -1, "timeout"
    except Exception as e:
        return -2, str(e)


async def _check_flaresolverr() -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FLARESOLVERR_URL, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
    except Exception:
        return False


async def _install_and_start_flaresolverr() -> bool:
    global _FLARESOLVERR_PROCESS
    try:
        code, output = await _run_cmd("node", "--version", timeout=15)
        if code != 0:
            logger.warning("Node.js 未安装，无法安装 FlareSolverr")
            return False
    except Exception:
        logger.warning("Node.js 未安装，无法安装 FlareSolverr")
        return False

    logger.info("正在通过 npx 安装并启动 FlareSolverr...")
    try:
        _FLARESOLVERR_PROCESS = await asyncio.create_subprocess_exec(
            "npx", "flaresolverr",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "NODE_ENV": "production"},
        )
        logger.info("FlareSolverr 进程已启动，等待服务就绪...")
        for i in range(30):
            await asyncio.sleep(2)
            if await _check_flaresolverr():
                logger.info("FlareSolverr 已就绪")
                return True
            if _FLARESOLVERR_PROCESS.returncode is not None and _FLARESOLVERR_PROCESS.returncode != 0:
                logger.warning(f"FlareSolverr 进程意外退出，code={_FLARESOLVERR_PROCESS.returncode}")
                break
        logger.warning("FlareSolverr 启动超时")
        return False
    except Exception as e:
        logger.warning(f"启动 FlareSolverr 失败: {e}")
        return False


async def ensure_flaresolverr() -> bool:
    global _FLARESOLVERR_ATTEMPTED
    if _FLARESOLVERR_ATTEMPTED:
        return _FLARESOLVERR_PROCESS is not None and _FLARESOLVERR_PROCESS.returncode is None
    async with _FLARESOLVERR_LOCK:
        if _FLARESOLVERR_ATTEMPTED:
            return _FLARESOLVERR_PROCESS is not None and _FLARESOLVERR_PROCESS.returncode is None
        _FLARESOLVERR_ATTEMPTED = True
        if await _check_flaresolverr():
            logger.info("FlareSolverr 已在运行")
            return True
        logger.info("FlareSolverr 未运行，尝试安装并启动...")
        return await _install_and_start_flaresolverr()


class AoE4WorldClient:
    def __init__(self):
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()
        self._summary_limiter = RateLimiter(max_calls=6, period=60.0)
        self._summary_cache: dict[int, dict | None] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_DEFAULT),
            )
        return self._session

    async def _request(self, path: str, params: dict | None = None, timeout: int | None = None) -> dict | None:
        session = await self._get_session()
        try:
            t = aiohttp.ClientTimeout(total=timeout or TIMEOUT_DEFAULT)
            async with session.get(f"{AOE4WORLD_API}{path}", params=params, timeout=t) as resp:
                if resp.status != 200:
                    logger.warning(f"AoE4 World API 返回 {resp.status}: {path}")
                    return None
                return await resp.json()
        except asyncio.TimeoutError:
            logger.warning(f"AoE4 World API 超时: {path}")
            return None
        except Exception as e:
            logger.error(f"AoE4 World API 请求失败 {path}: {e}")
            return None

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_player(self, profile_id: int) -> dict | None:
        return await self._request(f"/players/{profile_id}")

    async def search_player(self, name: str) -> list[dict]:
        data = await self._request("/players/search", {"query": name})
        if not data:
            return []
        return data.get("players", [])

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
            return self._summary_cache[game_id]

        if profile_id is None:
            game = await self.get_game_by_id(game_id)
            if not game:
                self._summary_cache[game_id] = None
                return None
            profile_id = None
            for team in game.get("teams", []):
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
        ok = await ensure_flaresolverr()
        if not ok:
            logger.warning("FlareSolverr 不可用，跳过 summary 请求")
            return None

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

    async def get_matchups(self, mode: str = "rm_solo") -> dict | None:
        session = await self._get_session()
        try:
            async with session.get(
                f"{AOE4WORLD_API}/stats/{mode}/matchups",
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_DEFAULT),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f" matchup查询失败: {resp.status}")
                    return None
                raw = await resp.json()
                return raw
        except Exception as e:
            logger.error(f"matchup查询请求失败: {e}")
            return None

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
            desc = item.findtext("description", "")
            pub_date = item.findtext("pubDate", "")
            if title:
                patches.append({
                    "title": title,
                    "link": link,
                    "description": desc,
                    "pub_date": pub_date,
                    "version": title.split()[0] if title else "",
                })
            if len(patches) >= limit:
                break
        return patches


FALLBACK_PATCHES = [
    {
        "title": "10.1.576 ",
        "link": "https://www.ageofempires.com/news/aoe4-pup-10-1-576/",
        "description": "Season Ten Anniversary Update brings a variety of",
        "pub_date": "Thu, 08 May 2025 00:00:00 GMT",
        "version": "10.1.576",
    },
    {
        "title": "10.0.538 Season 10",
        "link": "https://www.ageofempires.com/news/aoe4-season-10/",
        "description": "Season 10 Anniversary Update! New Civilizations:",
        "pub_date": "Fri, 28 Mar 2025 00:00:00 GMT",
        "version": "10.0.538",
    },
]
