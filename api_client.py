import asyncio
import json
import os
import platform
import re
import shutil
import sys
import tarfile
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET
import aiohttp
from astrbot.api import logger

AOE4WORLD_API = "https://aoe4world.com/api/v0"
USER_AGENT = "astrbot_plugin_aoe4/1.1.0 (QQ bot plugin; contact: @RiyoruAstral)"

FLARESOLVERR_URL = "http://localhost:8191/v1"


def set_flaresolverr_url(host: str, port: int):
    global FLARESOLVERR_URL
    if host:
        FLARESOLVERR_URL = f"http://{host}:{port}/v1"


_FLARESOLVERR_MODE = "once"


def set_flaresolverr_mode(mode: str):
    global _FLARESOLVERR_MODE
    if mode in ("never", "once", "always"):
        _FLARESOLVERR_MODE = mode


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


async def _ensure_nodejs() -> bool:
    code, _ = await _run_cmd("node", "--version", timeout=15)
    if code == 0:
        return True

    logger.info("Node.js 未安装，正在尝试自动安装...")
    system = sys.platform

    if system.startswith("linux"):
        try:
            code, output = await _run_cmd("apt-get", "update", "-qq", timeout=120)
            if code != 0:
                logger.warning(f"apt-get update 失败: {output[:200]}")
                return False
            code, output = await _run_cmd(
                "apt-get", "install", "-y", "-qq", "nodejs", "npm",
                timeout=180,
            )
            if code == 0:
                logger.info("Node.js 通过 apt-get 安装成功")
                return True
            logger.warning(f"apt-get install nodejs 失败: {output[:200]}")
            code, output = await _run_cmd(
                "curl", "-fsSL", "https://deb.nodesource.com/setup_22.x",
                "-o", "/tmp/nodesource_setup.sh",
                timeout=60,
            )
            if code != 0:
                logger.warning("下载 NodeSource 脚本失败")
                return False
            code, _ = await _run_cmd("bash", "/tmp/nodesource_setup.sh", timeout=60)
            if code != 0:
                logger.warning("NodeSource 安装脚本执行失败")
                return False
            code, _ = await _run_cmd("apt-get", "install", "-y", "-qq", "nodejs", timeout=180)
            if code == 0:
                logger.info("Node.js 通过 NodeSource 安装成功")
                return True
            logger.warning("NodeSource 安装后 apt-get install 仍失败")
            return False
        except Exception as e:
            logger.warning(f"Linux 安装 Node.js 失败: {e}")
            return False

    if system == "darwin":
        code, output = await _run_cmd("brew", "--version", timeout=15)
        if code != 0:
            logger.warning("macOS 未检测到 Homebrew，请手动安装 Node.js")
            return False
        code, output = await _run_cmd("brew", "install", "node", timeout=300)
        if code == 0:
            logger.info("Node.js 通过 Homebrew 安装成功")
            return True
        logger.warning(f"Homebrew install node 失败: {output[:200]}")
        return False

    if system == "win32":
        code, output = await _run_cmd("winget", "--version", timeout=15)
        if code == 0:
            code, output = await _run_cmd(
                "winget", "install", "--id", "OpenJS.NodeJS.LTS",
                "--silent", "--accept-package-agreements",
                timeout=300,
            )
            if code == 0:
                logger.info("Node.js 通过 winget 安装成功")
                return True
            logger.warning(f"winget install nodejs 失败: {output[:200]}")
            return False
        code, output = await _run_cmd("choco", "--version", timeout=15)
        if code == 0:
            code, output = await _run_cmd(
                "choco", "install", "nodejs", "-y", "--no-progress",
                timeout=300,
            )
            if code == 0:
                logger.info("Node.js 通过 Chocolatey 安装成功")
                return True
            logger.warning(f"choco install nodejs 失败: {output[:200]}")
            return False
        logger.warning("Windows 未检测到 winget 或 Chocolatey，请手动安装 Node.js")
        return False

    logger.warning(f"不支持的操作系统: {system}")
    return False


FLARESOLVERR_VERSION = "v3.5.0"
_FLARESOLVERR_CACHE_DIR = os.path.join(
    os.path.expanduser("~"), ".cache", "astrbot_plugin_aoe4", "flaresolverr"
)
_FLARESOLVERR_BINARY_DIR = os.path.join(_FLARESOLVERR_CACHE_DIR, FLARESOLVERR_VERSION)


async def _install_and_start_flaresolverr() -> bool:
    global _FLARESOLVERR_PROCESS

    system = sys.platform
    if system.startswith("linux"):
        arch = "linux_x64"
        archive_name = "flaresolverr_linux_x64.tar.gz"
        binary_name = "flaresolverr"
    elif system == "win32":
        arch = "windows_x64"
        archive_name = "flaresolverr_windows_x64.zip"
        binary_name = "flaresolverr.exe"
    elif system == "darwin":
        arch = "darwin_x64"
        archive_name = "flaresolverr_darwin_x64.tar.gz"
        binary_name = "flaresolverr"
    else:
        logger.warning(f"不支持的操作系统: {system}")
        return False

    binary_path = os.path.join(_FLARESOLVERR_BINARY_DIR, binary_name)
    version_file = os.path.join(_FLARESOLVERR_BINARY_DIR, ".version")

    if not os.path.exists(binary_path):
        archive_path = os.path.join(_FLARESOLVERR_CACHE_DIR, archive_name)

        if os.path.exists(archive_path):
            logger.info(f"发现预下载的压缩包: {archive_path}")
        else:
            logger.info(f"正在下载 FlareSolverr {FLARESOLVERR_VERSION} ({arch})...")
            download_urls = [
                f"https://mirrors.tuna.tsinghua.edu.cn/github-release/FlareSolverr/FlareSolverr/{FLARESOLVERR_VERSION}/{archive_name}",
                f"https://ghproxy.com/https://github.com/FlareSolverr/FlareSolverr/releases/download/{FLARESOLVERR_VERSION}/{archive_name}",
                f"https://github.com/FlareSolverr/FlareSolverr/releases/download/{FLARESOLVERR_VERSION}/{archive_name}",
            ]
            os.makedirs(_FLARESOLVERR_CACHE_DIR, exist_ok=True)

            downloaded = False
            for i, dl_url in enumerate(download_urls, 1):
                mirror_name = "清华镜像", "ghproxy.com 代理", "GitHub 直连"
                name = mirror_name[i - 1] if i <= len(mirror_name) else f"镜像 {i}"
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "wget", "-O", archive_path, "-q", "--timeout=300",
                        dl_url,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _, stderr = await proc.communicate()
                    if proc.returncode == 0:
                        logger.info(f"[{name}] 下载完成")
                        downloaded = True
                        break
                    else:
                        err_msg = stderr.decode("utf-8", errors="replace")[:200] if stderr else ""
                        logger.warning(f"[{name}] 下载失败 (返回码 {proc.returncode})")
                        if err_msg:
                            logger.warning(f"[{name}] {err_msg}")
                        continue
                except FileNotFoundError:
                    logger.warning("系统中未找到 wget 命令，请先安装 wget")
                    downloaded = False
                    break
            if not downloaded:
                logger.warning("所有镜像均下载失败")
                return False

        logger.info("正在解压...")
        extract_tmp = tempfile.mkdtemp()
        try:
            if archive_name.endswith(".zip"):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(extract_tmp)
            else:
                with tarfile.open(archive_path, "r:gz") as tf:
                    tf.extractall(extract_tmp)
            items = os.listdir(extract_tmp)
            if items:
                src = os.path.join(extract_tmp, items[0])
            else:
                logger.warning("解压后目录为空")
                return False
            if os.path.isdir(src):
                if os.path.exists(_FLARESOLVERR_BINARY_DIR):
                    shutil.rmtree(_FLARESOLVERR_BINARY_DIR, ignore_errors=True)
                shutil.copytree(src, _FLARESOLVERR_BINARY_DIR)
            else:
                os.makedirs(_FLARESOLVERR_BINARY_DIR, exist_ok=True)
                shutil.copy2(src, binary_path)
            with open(version_file, "w") as f:
                f.write(FLARESOLVERR_VERSION)
            logger.info(f"FlareSolverr 已解压到 {_FLARESOLVERR_BINARY_DIR}")
        finally:
            shutil.rmtree(extract_tmp, ignore_errors=True)

    if not os.path.exists(binary_path):
        logger.warning(f"未找到 FlareSolverr 可执行文件: {binary_path}")
        return False

    if not system == "win32":
        os.chmod(binary_path, 0o755)

    logger.info("正在启动 FlareSolverr...")
    try:
        _FLARESOLVERR_PROCESS = await asyncio.create_subprocess_exec(
            binary_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "LOG_LEVEL": "info", "PORT": "8191"},
            cwd=_FLARESOLVERR_BINARY_DIR,
        )
        logger.info("FlareSolverr 进程已启动，等待服务就绪（最长 60s）...")
        for i in range(60):
            await asyncio.sleep(1)
            if await _check_flaresolverr():
                logger.info("FlareSolverr 已就绪")
                return True
            if _FLARESOLVERR_PROCESS.returncode is not None and _FLARESOLVERR_PROCESS.returncode != 0:
                logger.warning(f"FlareSolverr 进程意外退出，code={_FLARESOLVERR_PROCESS.returncode}")
                break
        logger.warning("FlareSolverr 启动超时")
        if _FLARESOLVERR_PROCESS and _FLARESOLVERR_PROCESS.returncode is None:
            _FLARESOLVERR_PROCESS.kill()
        return False
    except Exception as e:
        logger.warning(f"启动 FlareSolverr 失败: {e}")
        return False


async def check_flaresolverr_connection() -> tuple[bool, str]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FLARESOLVERR_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    body = await resp.json()
                    msg = body.get("msg", body.get("msg", "ready"))
                    return True, f"已连接 ({msg})"
                return False, f"响应异常: HTTP {resp.status}"
    except aiohttp.ClientConnectorError:
        return False, f"连接失败 ({FLARESOLVERR_URL} 无响应)"
    except asyncio.TimeoutError:
        return False, "连接超时"
    except Exception as e:
        return False, f"错误: {e}"


async def ensure_flaresolverr() -> bool:
    global _FLARESOLVERR_ATTEMPTED

    if _FLARESOLVERR_MODE == "never":
        return False

    if _FLARESOLVERR_MODE == "always":
        _FLARESOLVERR_ATTEMPTED = False

    if _FLARESOLVERR_ATTEMPTED:
        return _FLARESOLVERR_PROCESS is not None and _FLARESOLVERR_PROCESS.returncode is None
    async with _FLARESOLVERR_LOCK:
        if _FLARESOLVERR_ATTEMPTED:
            return _FLARESOLVERR_PROCESS is not None and _FLARESOLVERR_PROCESS.returncode is None
        _FLARESOLVERR_ATTEMPTED = True
        if await _check_flaresolverr():
            logger.info("FlareSolverr 已在运行")
            return True

        if "localhost" not in FLARESOLVERR_URL and "127.0.0.1" not in FLARESOLVERR_URL:
            logger.warning(f"FlareSolverr 指向远程地址({FLARESOLVERR_URL})但未就绪，跳过自动安装")
            return False

        logger.info("FlareSolverr 未运行，尝试安装并启动...")
        return await _install_and_start_flaresolverr()


class AoE4WorldClient:
    def __init__(self, flaresolverr_host: str = "localhost", flaresolverr_port: int = 8191, flaresolverr_mode: str = "once"):
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()
        self._summary_limiter = RateLimiter(max_calls=6, period=60.0)
        self._summary_cache: dict[int, dict | None] = {}
        set_flaresolverr_url(flaresolverr_host, flaresolverr_port)
        set_flaresolverr_mode(flaresolverr_mode)

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
