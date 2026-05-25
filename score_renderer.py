import asyncio
import os
import sys
import tempfile
from astrbot.api import logger

BROWSER = None
PLAYWRIGHT = None
BROWSER_LOCK = asyncio.Lock()

FONT_CACHE_DIR = os.path.join(tempfile.gettempdir(), "aoe4_font_cache")
FONT_CACHE_PATH = os.path.join(FONT_CACHE_DIR, "notosanssc.woff2")
_FONT_READY = False


def _fmt(v):
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


_FA_MAP = {
    "📊": '<i class="fa-solid fa-chart-simple"></i>',
    "💰": '<i class="fa-solid fa-coins"></i>',
    "⚔️": '<i class="fa-solid fa-shield-halved"></i>',
    "🏗": '<i class="fa-solid fa-hammer"></i>',
    "🎮": '<i class="fa-solid fa-gamepad"></i>',
    "⏱": '<i class="fa-solid fa-clock"></i>',
    "🎙️": '<i class="fa-solid fa-microphone"></i>',
    "🌾": '<i class="fa-solid fa-wheat-awn"></i>',
    "🏠": '<i class="fa-solid fa-house"></i>',
    "💀": '<i class="fa-solid fa-skull"></i>',
    "☁️": '<i class="fa-solid fa-cloud"></i>',
    "🎁": '<i class="fa-solid fa-gift"></i>',
    "🐢": '<i class="fa-solid fa-person-walking"></i>',
    "⚡": '<i class="fa-solid fa-bolt"></i>',
    "🏗️": '<i class="fa-solid fa-hammer"></i>',
    "👊": '<i class="fa-solid fa-hand-fist"></i>',
    "🏘️": '<i class="fa-solid fa-city"></i>',
    "🔬": '<i class="fa-solid fa-flask"></i>',
    "🪓": '<i class="fa-solid fa-hand-fist"></i>',
    "💎": '<i class="fa-solid fa-gem"></i>',
    "⚖️": '<i class="fa-solid fa-scale-balanced"></i>',
    "🏛️": '<i class="fa-solid fa-landmark"></i>',
    "👶": '<i class="fa-solid fa-people-group"></i>',
    "🗡️": '<i class="fa-solid fa-shield-halved"></i>',
    "🤷": '<i class="fa-solid fa-question"></i>',
    "🏆": '<i class="fa-solid fa-trophy"></i>',
    "💬": '<i class="fa-solid fa-comment"></i>',
}


def _fa(text: str) -> str:
    for emoji, fa_icon in _FA_MAP.items():
        text = text.replace(emoji, fa_icon)
    return text


def _fmt_kd(kills, deaths):
    if deaths:
        return f"{kills / deaths:.2f}"
    if kills:
        return "∞"
    return "N/A"


def _player_color(idx: int, total: int, is_winner: bool) -> str:
    if is_winner:
        hues = [210, 170, 250, 30, 190, 140]
        return f"hsl({hues[idx % len(hues)]}, 55%, 50%)"
    else:
        hues = [0, 40, 300, 160, 60, 320, 100, 220]
        return f"hsl({hues[idx % len(hues)]}, 55%, 50%)"


def generate_score_html(
    players: list[dict],
    title: str,
    subtitle: str,
) -> str:
    has_olive = any(p.get("totalResourcesSpent", {}).get("oliveoil", 0) for p in players)
    n = len(players)
    winners = [p for p in players if p.get("result") == "win"]
    losers = [p for p in players if p.get("result") == "loss"]
    has_team_info = bool(winners and losers)
    cols = 4 if n >= 5 else 2
    card_w = f"{100 // cols - 2}%"

    cards_html = ""
    for i, p in enumerate(players):
        name = p.get("name", "?")
        civ = p.get("civilization", "")
        scores = p.get("scores", {})
        res = p.get("totalResourcesSpent", {})
        stats = p.get("_stats", {})
        apm = p.get("apm")

        if has_team_info:
            is_winner = p.get("result") == "win"
            team_label = "胜队" if is_winner else "败队"
            team_badge = "win" if is_winner else "loss"
        else:
            is_winner = i < n // 2
            team_label = "蓝队" if is_winner else "红队"
            team_badge = "blue" if is_winner else "red"
        color = _player_color(i, n, is_winner)

        kd = _fmt_kd(stats.get("ekills", 0), stats.get("edeaths", 0))

        olive_row = ""
        if has_olive:
            olive_row = f"""
              <tr><td class="lbl">橄榄油</td><td class="val">{_fmt(res.get('oliveoil', 0))}</td></tr>"""

        cards_html += f"""
        <div class="card" style="width:{card_w}">
          <div class="card-header" style="border-left:4px solid {color}">
            <div class="player-name">{_fmt(name)}</div>
            <div class="player-civ"><span class="badge badge-{team_badge}">{team_label}</span>{' | ' + _fmt(civ) if civ else ''}</div>
          </div>
          <div class="card-body">
            <div class="total-score" style="color:{color}">{_fmt(scores.get('total', 0))}</div>
            <div class="score-label">总评</div>
            <table class="stats">
              <tr><td class="cat" colspan="2">{_fa("📊")} 评分</td></tr>
              <tr><td class="lbl">军事</td><td class="val">{_fmt(scores.get('military', 0))}</td></tr>
              <tr><td class="lbl">经济</td><td class="val">{_fmt(scores.get('economy', 0))}</td></tr>
              <tr><td class="lbl">科技</td><td class="val">{_fmt(scores.get('technology', 0))}</td></tr>
              <tr><td class="lbl">社会</td><td class="val">{_fmt(scores.get('society', 0))}</td></tr>
              <tr><td class="cat" colspan="2">{_fa("💰")} 资源</td></tr>
              <tr><td class="lbl">总支出</td><td class="val">{_fmt(res.get('total', 0))}</td></tr>
              <tr><td class="lbl">食物</td><td class="val">{_fmt(res.get('food', 0))}</td></tr>
              <tr><td class="lbl">木材</td><td class="val">{_fmt(res.get('wood', 0))}</td></tr>
              <tr><td class="lbl">黄金</td><td class="val">{_fmt(res.get('gold', 0))}</td></tr>
              <tr><td class="lbl">石头</td><td class="val">{_fmt(res.get('stone', 0))}</td></tr>{olive_row}
              <tr><td class="cat" colspan="2">{_fa("⚔️")} 战斗</td></tr>
              <tr><td class="lbl">击杀</td><td class="val">{_fmt(stats.get('ekills', 0))}</td></tr>
              <tr><td class="lbl">阵亡</td><td class="val">{_fmt(stats.get('edeaths', 0))}</td></tr>
              <tr><td class="lbl">K/D</td><td class="val kd">{kd}</td></tr>
              <tr><td class="lbl">摧毁</td><td class="val">{_fmt(stats.get('structdmg', 0))}</td></tr>
              <tr><td class="cat" colspan="2">{_fa("🏗")} 运营</td></tr>
              <tr><td class="lbl">生产</td><td class="val">{_fmt(stats.get('sqprod', 0))}</td></tr>
              <tr><td class="lbl">建筑</td><td class="val">{_fmt(stats.get('bprod', 0))}</td></tr>
              <tr><td class="lbl">科技</td><td class="val">{_fmt(stats.get('upg', 0))}</td></tr>
              <tr><td class="lbl">APM</td><td class="val">{_fmt(apm)}</td></tr>
            </table>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<link href="https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-sc@5.2.9/index.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: "Noto Sans SC", "WenQuanYi Micro Hei", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: linear-gradient(135deg, #0f0c29 0%, #1a1a3e 50%, #24243e 100%);
  padding: 24px;
  color: #e0e0e0;
}}
.header {{
  text-align: center;
  padding: 16px 24px;
  margin-bottom: 20px;
  background: rgba(255,255,255,0.06);
  border-radius: 14px;
  backdrop-filter: blur(10px);
}}
.header h1 {{ font-size: 20px; color: #fff; margin-bottom: 4px; }}
.header h1 i {{ margin-right: 6px; }}
.header p {{ font-size: 13px; color: #aaa; }}
.header p i {{ margin-right: 4px; }}
.cards {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
}}
.card {{
  background: rgba(255,255,255,0.07);
  border-radius: 12px;
  overflow: hidden;
  backdrop-filter: blur(8px);
  min-width: 280px;
  flex: 1 1 auto;
}}
.card-header {{
  padding: 12px 16px;
  background: rgba(255,255,255,0.05);
}}
.player-name {{ font-size: 16px; font-weight: 700; color: #fff; }}
.player-civ {{ font-size: 12px; color: #999; margin-top: 2px; }}
.badge {{ display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; color: #fff; }}
.badge-win {{ background: #2d7d46; }}
.badge-loss {{ background: #8b2d2d; }}
.badge-blue {{ background: #2d4d8b; }}
.badge-red {{ background: #8b3a2d; }}
.card-body {{ padding: 12px 16px 16px; }}
.total-score {{ font-size: 32px; font-weight: 800; text-align: center; }}
.score-label {{ font-size: 11px; color: #888; text-align: center; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 2px; }}
table.stats {{ width:100%; border-collapse: collapse; font-size: 13px; }}
table.stats tr {{ border-bottom: 1px solid rgba(255,255,255,0.04); }}
table.stats tr:last-child {{ border-bottom: none; }}
table.stats td {{ padding: 5px 4px; }}
td.cat {{ font-size: 12px; font-weight: 600; color: #8af; padding-top: 10px !important; padding-bottom: 2px !important; letter-spacing: 1px; }}
td.cat i {{ margin-right: 4px; }}
td.lbl {{ color: #aaa; width: 60%; }}
td.val {{ text-align: right; font-weight: 600; color: #ddd; font-variant-numeric: tabular-nums; }}
td.kd {{ color: #f8a; }}
.footer {{
  text-align: center;
  margin-top: 16px;
  font-size: 11px;
  color: #555;
}}
</style>
</head>
<body>
<div class="header">
  <h1>{_fa(_fmt(title))}</h1>
  <p>{_fa(_fmt(subtitle))}</p>
</div>
<div class="cards">{cards_html}</div>
<div class="footer">Powered by astrbot-plugin-aoe4</div>
</body>
</html>"""


def generate_player_tags(players: list[dict]) -> list[dict]:
    tags_list = []
    for p in players:
        name = p.get("name", "?")
        scores = p.get("scores", {})
        res = p.get("totalResourcesSpent", {})
        stats = p.get("_stats", {})
        apm = p.get("apm")
        is_winner = p.get("result") == "win"

        tags = []

        total = scores.get("total", 0) or 0
        mil = scores.get("military", 0) or 0
        eco = scores.get("economy", 0) or 0
        tech = scores.get("technology", 0) or 0
        soc = scores.get("society", 0) or 0

        kills = stats.get("ekills", 0) or 0
        deaths = stats.get("edeaths", 0) or 0
        kd = kills / deaths if deaths else (999 if kills else 0)
        structdmg = stats.get("structdmg", 0) or 0
        sqprod = stats.get("sqprod", 0) or 0
        bprod = stats.get("bprod", 0) or 0
        upg = stats.get("upg", 0) or 0
        food = res.get("food", 0) or 0
        wood = res.get("wood", 0) or 0
        gold = res.get("gold", 0) or 0
        stone = res.get("stone", 0) or 0
        resources = res.get("total", 0) or 0

        if food > 30000 and food > wood + gold + stone:
            tags.append((_fa("🌾") + " 种田王", f"种了 {_fmt(food)} 食物，仿佛开了农场"))
        elif eco > 2000 and eco > mil + tech + soc:
            tags.append((_fa("🏠") + " 经济大师", f"经济分 {_fmt(eco)}，闷声发大财"))

        if kd >= 5 and kills > 50:
            tags.append((_fa("💀") + " 战神下凡", f"KD {kd:.2f}，杀穿全场"))
        elif kd >= 2 and kills > 30:
            tags.append((_fa("⚔️") + " 猛男", f"KD {kd:.2f}，实力碾压"))
        elif kd < 0.5 and deaths > 30:
            tags.append((_fa("☁️") + " 白给王", f"阵亡 {_fmt(deaths)} 次，峡谷先锋"))
        elif deaths > kills * 2 and deaths > 20:
            tags.append((_fa("🎁") + " 送温暖", f"阵亡 {_fmt(deaths)} / 击杀 {_fmt(kills)}，慈善大使"))

        if apm and apm < 60:
            tags.append((_fa("🐢") + " 养生玩家", f"APM {apm:.0f}，慢工出细活"))
        elif apm and apm > 250:
            tags.append((_fa("⚡") + " 手速怪", f"APM {apm:.0f}，单身二十年"))

        if structdmg > 50:
            tags.append((_fa("🏗️") + " 拆迁队长", f"摧毁 {_fmt(structdmg)} 建筑"))
        elif structdmg == 0 and is_winner and kills > 20:
            tags.append((_fa("👊") + " 纯武力", "一个建筑没拆也能赢，把对面人全杀光了"))

        if bprod > 150:
            tags.append((_fa("🏘️") + " 建房狂魔", f"造了 {_fmt(bprod)} 个建筑"))

        if upg > 45:
            tags.append((_fa("🔬") + " 科技宅", f"研究了 {_fmt(upg)} 项科技"))
        elif upg < 20 and (is_winner and mil > 1000):
            tags.append((_fa("🪓") + " 莽夫", "科技是什么？干就完了"))

        if resources > 120000:
            tags.append((_fa("💰") + " 资源大户", f"总支出 {_fmt(resources)} 的石油大王"))
        elif resources < 30000 and is_winner:
            tags.append((_fa("💎") + " 勤俭持家", f"只花 {_fmt(resources)} 资源就赢了"))

        if food > 15000 and wood > 15000 and gold > 15000:
            tags.append((_fa("⚖️") + " 均衡发展", "食物/木材/黄金都过万的三好村民"))

        if soc >= 1200:
            tags.append((_fa("🏛️") + " 交际花", f"社会分 {_fmt(soc)}，帝国的社交达人"))

        if sqprod > 700:
            tags.append((_fa("👶") + " 人口贩子", f"生产了 {_fmt(sqprod)} 个单位"))

        if mil > 3000:
            tags.append((_fa("🗡️") + " 战争狂人", f"军事分 {_fmt(mil)}，眼里只有战争"))

        if not tags:
            tags.append((_fa("🤷") + " 平平无奇", "数据均衡，稳健型玩家"))

        tags_list.append({
            "name": name,
            "tags": tags,
            "is_winner": is_winner,
        })
    return tags_list


def generate_analysis_html(
    players: list[dict],
    title: str,
    subtitle: str,
) -> str:
    tags_list = generate_player_tags(players)
    cards_html = ""
    for i, p in enumerate(tags_list):
        is_winner = p["is_winner"]
        color = _player_color(i, len(tags_list), is_winner)
        tags_html = "".join(
            f'<span class="tag" style="background:{_tag_color(j)}">{tag}</span>'
            for j, (tag, _) in enumerate(p["tags"])
        )
        comments_html = "".join(
            f'<div class="comment">{comment}</div>'
            for _, comment in p["tags"]
        )
        cards_html += f"""
        <div class="card">
          <div class="card-header" style="border-left:4px solid {color}">
            <div class="player-name">{_fmt(p['name'])}</div>
          </div>
          <div class="card-body">
            <div class="tags">{tags_html}</div>
            <div class="comments">{comments_html}</div>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<link href="https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-sc@5.2.9/index.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: "Noto Sans SC", "WenQuanYi Micro Hei", sans-serif;
  background: linear-gradient(135deg, #0f0c29 0%, #1a1a3e 50%, #24243e 100%);
  padding: 20px;
  color: #e0e0e0;
}}
.header {{
  text-align: center;
  padding: 14px 20px;
  margin-bottom: 16px;
  background: rgba(255,255,255,0.06);
  border-radius: 14px;
  backdrop-filter: blur(8px);
}}
.header h2 {{ font-size: 18px; color: #fff; margin-bottom: 3px; }}
.header h2 i {{ margin-right: 6px; }}
.header p {{ font-size: 12px; color: #999; }}
.header p i {{ margin-right: 4px; }}
.card {{
  background: rgba(255,255,255,0.07);
  border-radius: 12px;
  overflow: hidden;
  backdrop-filter: blur(8px);
  margin-bottom: 12px;
}}
.card-header {{
  padding: 10px 14px;
  background: rgba(255,255,255,0.05);
}}
.player-name {{ font-size: 15px; font-weight: 700; color: #fff; }}
.card-body {{ padding: 10px 14px 14px; }}
.tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }}
.tag {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 13px; font-weight: 600; color: #fff; }}
.comments {{ }}
.comment {{ font-size: 13px; color: #bbb; line-height: 1.6; padding: 2px 0; }}
.comment::before {{ content: ""; }}
.tag i {{ margin-right: 4px; }}
.footer {{
  text-align: center;
  margin-top: 12px;
  font-size: 11px;
  color: #444;
}}
</style>
</head>
<body>
<div class="header">
  <h2>{_fa("🎙️")} 搞怪锐评</h2>
  <p>{_fa(_fmt(title))} | {_fa(_fmt(subtitle))}</p>
</div>
{cards_html}
<div class="footer">Powered by astrbot-plugin-aoe4</div>
</body>
</html>"""


def _tag_color(idx: int) -> str:
    colors = [
        "rgba(66,133,244,0.7)", "rgba(234,67,53,0.7)",
        "rgba(52,168,83,0.7)", "rgba(251,188,4,0.7)",
        "rgba(154,71,220,0.7)", "rgba(255,112,67,0.7)",
        "rgba(3,169,244,0.7)", "rgba(233,30,99,0.7)",
    ]
    return colors[idx % len(colors)]


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


async def _ensure_cjk_fonts() -> bool:
    global _FONT_READY
    if _FONT_READY:
        return True
    try:
        code, output = await _run_cmd(
            "apt-get", "install", "-y", "-qq", "fonts-wqy-microhei", timeout=120,
        )
        fallback = code != 0
        if fallback:
            code, output = await _run_cmd(
                "apt-get", "install", "-y", "-qq", "fonts-noto-cjk", timeout=120,
            )
        if code != 0:
            logger.warning(f"[ScoreRender] CJK字体安装失败")
            return False
        await _run_cmd("fc-cache", "-f", timeout=30)
        logger.info("[ScoreRender] CJK字体已安装，缓存已刷新")
        _FONT_READY = True
        return True
    except Exception as e:
        logger.warning(f"[ScoreRender] 安装CJK字体失败: {e}")
        return False


async def _ensure_system_deps() -> bool:
    try:
        code, output = await _run_cmd("apt-get", "update", "-qq", timeout=60)
        if code != 0:
            logger.warning(f"[ScoreRender] apt-get update 失败(code={code}): {output[-200:]}")
            return False
        code, output = await _run_cmd(
            "apt-get", "install", "-y", "-qq",
            "libnspr4", "libnss3",
            "libatk1.0-0t64", "libatk-bridge2.0-0t64",
            "libcups2t64", "libdrm2", "libxkbcommon0", "libxcomposite1",
            "libxdamage1", "libxfixes3", "libxrandr2", "libgbm1",
            "libpango-1.0-0", "libcairo2", "libasound2t64",
            "fonts-wqy-microhei",
            timeout=120,
        )
        if code == 0:
            logger.info("[ScoreRender] 系统依赖安装完成")
            return True
        code, output = await _run_cmd(
            "apt-get", "install", "-y", "-qq",
            "libnspr4", "libnss3",
            "libatk1.0-0", "libatk-bridge2.0-0",
            "libcups2", "libdrm2", "libxkbcommon0", "libxcomposite1",
            "libxdamage1", "libxfixes3", "libxrandr2", "libgbm1",
            "libpango-1.0-0", "libcairo2", "libasound2",
            "fonts-wqy-microhei",
            timeout=120,
        )
        if code == 0:
            logger.info("[ScoreRender] 系统依赖安装完成 (备用包名)")
            return True
        logger.warning(f"[ScoreRender] apt-get install 失败(code={code}): {output[-200:]}")
        return False
    except Exception as e:
        logger.warning(f"[ScoreRender] 安装系统依赖失败: {e}")
        return False


async def _install_chromium() -> bool:
    cache_dir = os.path.expanduser("~/.cache/ms-playwright")
    lock_path = os.path.join(cache_dir, "__dirlock")
    if os.path.exists(lock_path):
        try:
            os.remove(lock_path)
            logger.info("[ScoreRender] 已清除残留的 Playwright 锁文件")
        except Exception as e:
            logger.warning(f"[ScoreRender] 清除锁文件失败: {e}")

    incomplete = [d for d in (os.listdir(cache_dir) if os.path.isdir(cache_dir) else [])
                  if d.startswith("chromium") and not d.endswith(".zip")]
    for d in incomplete:
        dp = os.path.join(cache_dir, d)
        if os.path.isdir(dp):
            try:
                import shutil
                shutil.rmtree(dp)
                logger.info(f"[ScoreRender] 已清理残留目录: {d}")
            except Exception as e:
                logger.warning(f"[ScoreRender] 清理目录失败: {d}: {e}")

    env = os.environ.copy()
    for mirror in [
        "https://cdn.npmmirror.com/binaries/playwright",
        None,
    ]:
        if mirror:
            env["PLAYWRIGHT_DOWNLOAD_HOST"] = mirror
            label = f"镜像源 {mirror}"
        else:
            env.pop("PLAYWRIGHT_DOWNLOAD_HOST", None)
            label = "默认源"
        logger.info(f"[ScoreRender] 尝试 {label} 下载 Chromium...")
        code, output = await _run_cmd(
            sys.executable, "-m", "playwright", "install", "chromium",
            timeout=180, env=env,
        )
        if code == 0:
            logger.info("[ScoreRender] Chromium 下载成功")
            return True
        logger.warning(f"[ScoreRender] {label} 下载失败 (code={code}): {output[-300:]}")
    return False


async def ensure_browser():
    global BROWSER, PLAYWRIGHT
    async with BROWSER_LOCK:
        if BROWSER is not None and BROWSER.is_connected():
            return True

        for attempt in range(2):
            try:
                from playwright.async_api import async_playwright
                if PLAYWRIGHT is None:
                    PLAYWRIGHT = await async_playwright().start()
                BROWSER = await PLAYWRIGHT.chromium.launch()
                logger.info("[ScoreRender] Playwright 浏览器已启动")
                return True
            except Exception as e:
                err_str = str(e).lower()
                if attempt > 0:
                    logger.warning(f"[ScoreRender] Playwright 浏览器不可用: {e}")
                    return False

                is_missing_browser = any(k in err_str for k in ("executable", "not found", "chromium", "browser"))
                is_missing_lib = any(k in err_str for k in ("libnspr4", "cannot open shared object", "error while loading"))

                if is_missing_lib:
                    logger.info("[ScoreRender] 检测到缺少系统库，尝试安装系统依赖...")
                    await _ensure_system_deps()

                if is_missing_browser or is_missing_lib:
                    logger.info("[ScoreRender] 尝试安装/修复 Chromium 浏览器...")
                    installed = await _install_chromium()
                    if installed:
                        logger.info("[ScoreRender] Chromium 处理完成，重试启动...")
                        continue

                logger.warning(f"[ScoreRender] Playwright 浏览器不可用: {e}")
                return False

        return False


async def close_browser():
    global BROWSER, PLAYWRIGHT
    async with BROWSER_LOCK:
        if BROWSER:
            try:
                await BROWSER.close()
            except Exception:
                pass
            BROWSER = None
        if PLAYWRIGHT:
            try:
                await PLAYWRIGHT.stop()
            except Exception:
                pass
            PLAYWRIGHT = None
        logger.info("[ScoreRender] 浏览器已关闭")


async def render_html_to_image(html: str, output_path: str, width: int = 680, scale: int = 2) -> bool:
    if not _FONT_READY:
        fonts_ok = await _ensure_cjk_fonts()
        if fonts_ok:
            global BROWSER
            if BROWSER is not None:
                try:
                    await BROWSER.close()
                except Exception:
                    pass
                BROWSER = None
                logger.info("[ScoreRender] 已关闭浏览器以重新加载字体")

    ok = await ensure_browser()
    if not ok:
        return False
    page = None
    context = None
    try:
        context = await BROWSER.new_context(
            device_scale_factor=scale,
            viewport={"width": width, "height": 600},
        )
        page = await context.new_page()
        await page.set_content(html, wait_until="domcontentloaded")
        await page.wait_for_timeout(300)

        doc_height = await page.evaluate(
            """() => {
                const body = document.body;
                const html = document.documentElement;
                return Math.max(
                    body.scrollHeight, body.offsetHeight,
                    html.scrollHeight, html.offsetHeight
                );
            }"""
        )
        await page.set_viewport_size({"width": width, "height": max(int(doc_height), 600)})
        await page.wait_for_timeout(100)

        await page.screenshot(path=output_path, full_page=True, type="jpeg", quality=92)
        return True
    except Exception as e:
        logger.error(f"[ScoreRender] 渲染失败: {e}")
        return False
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass
