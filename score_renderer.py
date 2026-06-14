import asyncio
import base64
import math
import os
import random
import sys
import tempfile
from astrbot.api import logger

BROWSER = None
PLAYWRIGHT = None
BROWSER_LOCK = asyncio.Lock()

FONT_CACHE_DIR = os.path.join(tempfile.gettempdir(), "aoe4_font_cache")
FONT_CACHE_PATH = os.path.join(FONT_CACHE_DIR, "notosanssc.woff2")
_FONT_READY = False

TR = None
_CHROMIUM_DOWNLOAD_HOST = ""
_PROFILE_IMAGE_DIR = ""


def set_translator(tr):
    global TR
    TR = tr


def set_chromium_download_host(url: str):
    global _CHROMIUM_DOWNLOAD_HOST
    _CHROMIUM_DOWNLOAD_HOST = url


def set_profile_image_dir(path: str):
    global _PROFILE_IMAGE_DIR
    _PROFILE_IMAGE_DIR = path


def _s(key: str, **kwargs) -> str:
    if TR is not None:
        return TR.score(key, **kwargs)
    return key


def _civ_name(code: str) -> str:
    if not code or TR is None:
        return code
    result = TR.civ(code)
    if result != code:
        return result
    return TR.civ(code.lower())


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
    k = _fmt(kills)
    d = _fmt(deaths)
    if deaths and deaths > 0:
        ratio = kills / deaths
        return f"{k}/{d} ({ratio:.2f})"
    return f"{k}/{d}"


def _player_color(idx: int, total: int, is_winner: bool) -> str:
    if is_winner:
        hues = [210, 200, 190, 180, 170]
        return f"hsl({hues[idx % len(hues)]}, 55%, 50%)"
    else:
        hues = [40, 30, 20, 10, 0]
        return f"hsl({hues[idx % len(hues)]}, 55%, 50%)"


def _generate_radar_svg(normalized: dict, raw: dict, size: int = 200, color: str = "rgba(100,180,255,0.7)") -> str:
    n_axes = 4
    pad = 30
    vb = size + pad * 2
    cx = cy = vb / 2
    r = (vb / 2 - pad) * 0.82
    angles = [(-90 + 90 * i) for i in range(n_axes)]
    keys = ["military", "economy", "technology", "society"]
    labels = [_s("scores_military"), _s("scores_economy"), _s("scores_technology"), _s("scores_society")]

    def _pt(deg, radius):
        rad = math.radians(deg)
        return (cx + radius * math.cos(rad), cy + radius * math.sin(rad))

    parts = []
    for level in range(1, 5):
        pts = " ".join(f"{_pt(a, r * level / 4)[0]},{_pt(a, r * level / 4)[1]}" for a in angles)
        parts.append(f'<polygon points="{pts}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>')
    for a in angles:
        x, y = _pt(a, r)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x}" y2="{y}" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>')
    data_pts = " ".join(f"{_pt(a, r * normalized[k])[0]},{_pt(a, r * normalized[k])[1]}" for a, k in zip(angles, keys))
    hsla = color.replace("hsl(", "hsla(").replace(")", ", 0.15)")
    parts.append(f'<polygon points="{data_pts}" fill="{hsla}" stroke="{color}" stroke-width="2"/>')
    for a, k in zip(angles, keys):
        x, y = _pt(a, r * normalized[k])
        parts.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{color}"/>')
    for i, a in enumerate(angles):
        lx, ly = _pt(a, r + 14)
        parts.append(
            f'<text x="{lx}" y="{ly}" text-anchor="middle" dominant-baseline="middle" '
            f'fill="#aaa" font-size="11" font-family="Noto Sans SC, sans-serif">{labels[i]}</text>'
        )
        pct = normalized[keys[i]] * 100
        pct_str = f"{pct:.0f}%" if pct < 100 else "100%"
        parts.append(
            f'<text x="{lx}" y="{ly + 14}" text-anchor="middle" dominant-baseline="middle" '
            f'fill="#ddd" font-size="12" font-weight="bold" '
            f'font-family="Noto Sans SC, sans-serif">{pct_str}</text>'
        )

    inner = "\n".join(parts)
    return (
        f'<svg viewBox="0 0 {vb} {vb}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:{size}px;height:{size}px;display:block;margin:0 auto;">'
        f'{inner}</svg>'
    )


def generate_radar_html(players: list[dict], title: str, subtitle: str) -> str:
    if not players:
        return _empty_html("暂无玩家数据")
    normalized_list, raw_list = _normalize_radar_scores(players)
    n = len(players)
    cols = 2 if n <= 4 else 3
    radar_size = 200 if n <= 2 else (180 if n <= 4 else 150)
    card_w = f"{100 // cols - 1}%"
    winners = [p for p in players if p.get("result") == "win"]
    losers = [p for p in players if p.get("result") == "loss"]
    has_team_info = bool(winners and losers)
    cards_html = ""
    for i, p in enumerate(players):
        if has_team_info:
            is_winner = p.get("result") == "win"
            team_badge = "win" if is_winner else "loss"
            team_label = _s("team_win") if is_winner else _s("team_loss")
        else:
            is_winner = i < n // 2
            team_badge = "blue" if is_winner else "red"
            team_label = _s("team_blue") if is_winner else _s("team_red")
        color = _player_color(i, n, is_winner)
        name = p.get("name", "?")
        civ = p.get("civilization", "")
        civ_str = f" | {_civ_name(civ)}" if civ else ""
        total = p.get("scores", {}).get("total", 0) or 0
        radar = _generate_radar_svg(normalized_list[i], raw_list[i], size=radar_size, color=color)
        raw_scores_html = "".join(
            f'<div class="rs-item"><span class="rs-lbl">{_s(f"scores_{k}")}</span>'
            f'<span class="rs-val">{_fmt(raw_list[i][k])}</span></div>'
            for k in ["military", "economy", "technology", "society"]
        )
        tags_html = ""
        try:
            tags_list = generate_player_tags([p])
            if tags_list:
                tags_html = "".join(
                    f'<span class="r-tag" style="background:{_tag_color(j)}">{tag}</span>'
                    for j, (tag, _) in enumerate(tags_list[0]["tags"][:2])
                )
        except Exception:
            pass
        cards_html += f"""
        <div class="r-card" style="width:{card_w}">
          <div class="r-card-hdr" style="border-left:4px solid {color}">
            <div class="r-name">{_fmt(name)}</div>
            <div class="r-meta"><span class="r-badge r-badge-{team_badge}">{team_label}</span>{civ_str}</div>
          </div>
          <div class="r-card-body">
            {radar}
            <div class="r-scores-row">{raw_scores_html}</div>
            <div class="r-total-line">{_s('total_score')}: <strong>{_fmt(total)}</strong></div>
            {f'<div class="r-tags-row">{tags_html}</div>' if tags_html else ''}
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
  padding: 20px;
  color: #e0e0e0;
}}
.r-hdr {{
  text-align:center; padding:14px 20px; margin-bottom:16px;
  background:rgba(255,255,255,0.06); border-radius:14px; backdrop-filter:blur(8px);
}}
.r-hdr h1 {{ font-size:18px; color:#fff; margin-bottom:3px; }}
.r-hdr h1 i {{ margin-right:6px; }}
.r-hdr p {{ font-size:12px; color:#999; }}
.r-hdr p i {{ margin-right:4px; }}
.r-cards {{
  display:flex; flex-wrap:wrap; gap:12px; justify-content:center;
}}
.r-card {{
  background:rgba(255,255,255,0.07); border-radius:12px; overflow:hidden;
  backdrop-filter:blur(8px); min-width:240px; flex:1 1 auto;
}}
.r-card-hdr {{
  padding:10px 14px; background:rgba(255,255,255,0.05);
}}
.r-name {{ font-size:15px; font-weight:700; color:#fff; }}
.r-meta {{ font-size:11px; color:#999; margin-top:2px; }}
.r-badge {{ display:inline-block; padding:1px 8px; border-radius:10px; font-size:10px; font-weight:600; color:#fff; margin-right:4px; }}
.r-badge-win {{ background:#2d7d46; }}
.r-badge-loss {{ background:#8b2d2d; }}
.r-badge-blue {{ background:#2d4d8b; }}
.r-badge-red {{ background:#8b3a2d; }}
.r-card-body {{ padding:12px 14px 14px; text-align:center; }}
.r-scores-row {{
  display:flex; flex-wrap:wrap; gap:4px; justify-content:center; margin-top:8px;
}}
.rs-item {{
  background:rgba(255,255,255,0.05); border-radius:6px; padding:4px 8px;
  min-width:54px; text-align:center;
}}
.rs-lbl {{ display:block; font-size:9px; color:#888; }}
.rs-val {{ display:block; font-size:13px; font-weight:700; color:#ddd; }}
.r-total-line {{ font-size:13px; color:#aaa; margin-top:6px; }}
.r-total-line strong {{ color:#ffd93d; font-size:15px; }}
.r-tags-row {{ margin-top:8px; display:flex; flex-wrap:wrap; gap:4px; justify-content:center; }}
.r-tag {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; color:#fff; }}
.r-tag i {{ margin-right:3px; }}
.r-footer {{ text-align:center; margin-top:12px; font-size:10px; color:#444; }}
</style>
</head>
<body>
<div class="r-hdr">
  <h1>{_fa("🎯")} {_fa(_fmt(title))}</h1>
  <p>{_fa(_fmt(subtitle))}</p>
</div>
<div class="r-cards">{cards_html}</div>
<div class="r-footer">{_s('footer')}</div>
</body>
</html>"""


def _empty_html(msg: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<style>
body {{
  font-family: "Noto Sans SC", sans-serif;
  background: #1a1a2e; color: #e0e0e0;
  width: 480px; padding: 40px; text-align: center;
}}
</style>
</head>
<body><p>{msg}</p></body>
</html>"""


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
        await page.set_content(html, wait_until="networkidle")
        await page.wait_for_timeout(500)
        dh = await page.evaluate("""() => Math.max(
            document.body.scrollHeight, document.documentElement.scrollHeight,
            document.body.offsetHeight, document.documentElement.offsetHeight
        )""")
        if dh < 600:
            dh = 600
        await page.set_viewport_size({"width": width, "height": dh})
        await page.wait_for_timeout(200)
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


# ─── Player Profile Rendering ─────────────────────────────────

_CIV_EMOJI = {
    "english": "🏴", "chinese": "🇨🇳", "french": "🏴",
    "holy_roman_empire": "🇩🇪", "mongols": "🇲🇳", "rus": "🇷🇺",
    "delhi_sultanate": "🇮🇳", "abbasid_dynasty": "🇸🇦", "ottomans": "🇹🇷",
    "malians": "🇲🇱", "byzantines": "🇧🇾", "japanese": "🇯🇵",
    "ayyubids": "🇸🇦", "jeanne_darc": "🇫🇷", "order_of_the_dragon": "🇷🇴",
    "zhu_xis_legacy": "🇨🇳", "jin_dynasty": "🇨🇳", "golden_horde": "🇰🇿",
    "sengoku_daimyo": "🇯🇵", "knights_templar": "🏰", "house_of_lancaster": "🏴",
    "macedonian_dynasty": "🇬🇷", "tughlaq_dynasty": "🇮🇳",
}

_COUNTRY_FLAG = {
    "cn": "🇨🇳", "us": "🇺🇸", "gb": "🇬🇧", "de": "🇩🇪",
    "fr": "🇫🇷", "jp": "🇯🇵", "kr": "🇰🇷", "ru": "🇷🇺",
    "sg": "🇸🇬", "au": "🇦🇺", "ca": "🇨🇦", "nl": "🇳🇱",
    "br": "🇧🇷", "rs": "🇷🇸",
}

_RANK_EMOJI = {
    "conqueror": "🏆", "diamond": "💎", "platinum": "🥇",
    "gold": "🥈", "silver": "🥉", "bronze": "🟤", "unranked": "❓",
}

_MODE_ORDER = ["rm_solo", "rm_2v2", "rm_3v3", "rm_4v4", "rm_team",
               "qm_1v1", "qm_2v2", "qm_3v3", "qm_4v4"]
_MODE_LABELS = {
    "rm_solo": "1v1 排位", "rm_2v2": "2v2 排位", "rm_3v3": "3v3 排位",
    "rm_4v4": "4v4 排位", "rm_team": "组队排位",
    "qm_1v1": "1v1 快速", "qm_2v2": "2v2 快速",
    "qm_3v3": "3v3 快速", "qm_4v4": "4v4 快速",
}
_MODE_COLORS = {
    "rm_solo": "#5B9BD5", "rm_2v2": "#4CAF50", "rm_3v3": "#FF9800",
    "rm_4v4": "#AB47BC", "rm_team": "#FF6B35",
    "qm_1v1": "#8EA9C1", "qm_2v2": "#8EA9C1", "qm_3v3": "#8EA9C1", "qm_4v4": "#8EA9C1",
}

_LVL_ORDER = ["conqueror_3","conqueror_2","conqueror_1",
              "diamond_3","diamond_2","diamond_1",
              "platinum_3","platinum_2","platinum_1",
              "gold_3","gold_2","gold_1",
              "silver_3","silver_2","silver_1",
              "bronze_3","bronze_2","bronze_1"]

_QUOTES = [
    "「故上兵伐谋，其次伐交，其次伐兵，其下攻城。」—— 孙子《孙子兵法》",
    "「知己知彼，百战不殆。」—— 孙子《孙子兵法》",
    "「天下武功，唯快不破。」—— 火云邪神《功夫》",
    "「军队的威力不在于数量，而在于纪律。」—— 威廉·杜克",
    "「战争是政治的延续。」—— 卡尔·冯·克劳塞维茨",
    "「在绝对的实力面前，一切计谋都是徒劳。」—— 俾斯麦",
    "「想成事，先修路。」—— 经济学的第一课",
    "「打不过就加入。」—— 天梯生存法则",
    "「我可以输，但对面的运营必须乱。」—— 帝国老手箴言",
    "「当你不知道做什么的时候，就去造农民。」—— AoE4 新手圣经",
    "「经济的胜利才是真正的胜利。」—— 种田流的信仰",
    "「一波不行就再来一波。」—— 帝国时代玩家的坚持",
    "「不怕神一样的对手，只怕猪一样的队友。」—— 团队排位的真理",
    "「地图决定打法，版本决定强度。」—— 天梯生态观察",
    "「这就是帝国时代！这就是策略游戏的魅力！」—— 社区名言",
    "「没有垃圾兵种，只有垃圾操作。」—— 高手的谦辞",
    "「活着才有输出，运营才有未来。」—— 帝国生存法则",
    "「我不需要赢在开局，只要赢在终局。」—— 运营流玩家的信条",
]


def _fmt_pct(v):
    if v is None: return "N/A"
    return f"{v:.1f}%"


def _rank_label(level: str | None) -> str:
    if not level or TR is None: return "未定级"
    rank = TR.rank_level(level)
    prefix = ""
    for key, emoji in _RANK_EMOJI.items():
        if level.startswith(key):
            prefix = emoji
            break
    return f"{prefix} {rank}" if prefix else rank


def _elapsed_ago(iso_str: str | None) -> str:
    if not iso_str: return "未知"
    from datetime import datetime, timezone
    try:
        t = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - t
        d = diff.days
        if d > 365: return f"{d // 365}年前"
        if d > 30: return f"{d // 30}个月前"
        if d > 0: return f"{d}天前"
        h = diff.seconds // 3600
        if h > 0: return f"{h}小时前"
        m = diff.seconds // 60
        return f"{m}分钟前" if m > 0 else "刚刚"
    except: return iso_str


def _get_random_profile_image() -> str:
    """Pick a random image from _PROFILE_IMAGE_DIR, return as base64 data URI."""
    d = _PROFILE_IMAGE_DIR
    if not d or not os.path.isdir(d):
        return ""
    exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
    files = [f for f in os.listdir(d) if f.lower().endswith(exts)]
    if not files:
        return ""
    chosen = os.path.join(d, random.choice(files))
    try:
        with open(chosen, "rb") as f:
            data = f.read()
        ext = os.path.splitext(chosen)[1].lower().replace(".", "")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""


async def generate_profile_html(player: dict, games: list[dict], season: str,
                                image_dir: str = "") -> str:
    """Generate profile HTML page from AoE4 player data."""
    global _PROFILE_IMAGE_DIR
    if image_dir:
        _PROFILE_IMAGE_DIR = image_dir

    name = player.get("name", "?")
    country = player.get("country", "")
    flag = _COUNTRY_FLAG.get(country, "")
    pid = player.get("profile_id", "?")
    steam = player.get("steam_id", "")
    modes = player.get("modes", {})

    # ── Core stats ──
    total_games = sum((m.get("games_count", 0) or 0) for m in modes.values())
    total_wins = sum((m.get("wins_count", 0) or 0) for m in modes.values())
    overall_wr = (total_wins / total_games * 100) if total_games else 0
    max_rating = 0
    last_game_at = ""
    for mk, m in modes.items():
        r = m.get("max_rating") or 0
        if r > max_rating:
            max_rating = r
        lg = m.get("last_game_at")
        if lg and (not last_game_at or lg > last_game_at):
            last_game_at = lg

    # ── Header badges ──
    first_mode = None
    for mk in _MODE_ORDER:
        if mk in modes and modes[mk].get("rating"):
            first_mode = modes[mk]
            break
    header_rank = _rank_label(first_mode.get("rank_level")) if first_mode else ""
    header_rating = first_mode.get("rating") if first_mode else None

    # ── Ranked stats ──
    ranked_games = 0
    ranked_wins = 0
    max_streak = 0
    for mk, m in modes.items():
        if not mk.startswith("rm_"):
            continue
        ranked_games += m.get("games_count", 0) or 0
        ranked_wins += m.get("wins_count", 0) or 0
        ms = abs(m.get("streak", 0) or 0)
        if ms > max_streak:
            max_streak = ms
    ranked_wr = (ranked_wins / ranked_games * 100) if ranked_games else 0

    # ── Best rank ──
    best_rank = ""
    for mk, m in modes.items():
        rl = m.get("rank_level", "")
        if rl and rl != "unranked" and rl in _LVL_ORDER:
            if not best_rank or _LVL_ORDER.index(rl) < _LVL_ORDER.index(best_rank):
                best_rank = rl
    best_rank_label = _rank_label(best_rank) if best_rank else "暂无"

    # ── Trend data from games ──
    trend_values = []
    cum = 0
    import aiohttp
    async with aiohttp.ClientSession(headers={"User-Agent": "aoe4-bot/1.0"}) as sess:
        for g in reversed(games[:10]):
            gid = g.get("game_id")
            if not gid:
                continue
            try:
                async with sess.get(f"https://aoe4world.com/api/v0/games/{gid}",
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        continue
                    detail = await resp.json()
            except Exception:
                continue
            for team in detail.get("teams", []):
                for p in team:
                    if p.get("profile_id") == pid:
                        rd = p.get("rating_diff")
                        if rd is not None:
                            cum += rd
                            trend_values.append(cum)
                        break

    # ── Trend SVG ──
    trend_svg = ""
    if len(trend_values) >= 2:
        n = len(trend_values)
        w, h = 180, 24
        min_v = min(trend_values)
        max_v = max(trend_values)
        rng = max_v - min_v if max_v - min_v > 0 else 1
        pts = " ".join(
            f"{(w / (n - 1)) * i:.0f},{h - (v - min_v) / rng * (h - 4) - 2:.0f}"
            for i, v in enumerate(trend_values)
        )
        last = trend_values[-1]
        sign = "+" if last >= 0 else ""
        trend_svg = f"""
      <div class="trend-wrap">
        <span class="trend-lbl">近10场评分变化</span>
        <svg viewBox="0 0 {w} {h}" style="flex:1;height:24px;">
          <polyline points="{pts}" fill="none" stroke="#5B9BD5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span class="trend-label">{sign}{last}</span>
      </div>"""

    # ── Mode cards (left column) ──
    mode_cards = ""
    for mk in _MODE_ORDER:
        m = modes.get(mk)
        if not m:
            continue
        is_ranked = mk.startswith("rm_")
        border_clr = _MODE_COLORS.get(mk, "#5B9BD5") if is_ranked else "#B0C4DE"
        card_cls = "" if is_ranked else ' style="opacity:0.7"'
        rating = m.get("rating")
        rl = m.get("rank_level")
        rl_label = _rank_label(rl) if rl else ""
        games_n = m.get("games_count", 0) or 0
        wr_val = m.get("win_rate")
        wr_str = _fmt_pct(wr_val) if wr_val is not None else "N/A"
        streak = m.get("streak", 0) or 0
        streak_str = ""
        if streak > 0:
            streak_str = f'<span class="stat-orange"><i class="fa-solid fa-fire"></i> {streak}连胜</span>'
        elif streak < 0:
            streak_str = f'<span class="stat-red"><i class="fa-solid fa-arrow-down"></i> {abs(streak)}连败</span>'
        if rating:
            rating_str = _fmt(rating)
            rating_color = f'style="color:{border_clr}"'
            rank_badge = f'<span class="mode-card-rank">{rl_label}</span>' if rl_label else ""
            if mk in ("rm_solo", "rm_team") and max_rating:
                bar_pct = min(rating / max_rating * 100, 100)
                bar_html = f'<div class="mode-bar"><div class="mode-bar-fill" style="width:{bar_pct:.0f}%;background:{border_clr}"></div></div>'
            else:
                bar_html = ""
        else:
            rating_str = "暂无数据"
            rating_color = 'style="color:#B0C4DE"'
            rank_badge = ""
            bar_html = ""
        mode_cards += f"""
      <div class="mode-card"{card_cls} style="border-left-color:{border_clr}">
        <div class="mode-card-label">{_MODE_LABELS.get(mk, mk)}</div>
        <div class="mode-card-row">
          <span class="mode-card-rating" {rating_color}>{rating_str}</span>
          {rank_badge}
        </div>
        <div class="mode-card-stats">
          <span class="stat-green">胜率 {wr_str}</span>
          <span>场次 {games_n}</span>
          {streak_str}
        </div>
        {bar_html}
      </div>"""

    # ── Civ distribution from games ──
    civ_stats = {}
    for g in games:
        for team in g.get("teams", []):
            for p in team:
                pd = p.get("player", p)
                if pd.get("profile_id") == pid:
                    civ = pd.get("civilization", "unknown")
                    result = pd.get("result", "unknown")
                    if civ not in civ_stats:
                        civ_stats[civ] = {"games": 0, "wins": 0}
                    civ_stats[civ]["games"] += 1
                    if result == "win":
                        civ_stats[civ]["wins"] += 1

    # ── Recent performance summary (top of civ section) ──
    recent_wins = sum(s["wins"] for s in civ_stats.values())
    recent_total_g = sum(s["games"] for s in civ_stats.values())
    recent_wr_val = (recent_wins / recent_total_g * 100) if recent_total_g else 0
    recent_losses = recent_total_g - recent_wins
    win_bar_pct = (recent_wins / recent_total_g * 100) if recent_total_g else 0
    perf_summary = ""
    if recent_total_g > 0:
        perf_summary = f"""
      <div class="civ-summary">
        <span class="cs-item"><i class="fa-solid fa-gamepad"></i> 近{recent_total_g}场</span>
        <span class="cs-item cs-win"><i class="fa-solid fa-check"></i> {recent_wins}胜</span>
        <span class="cs-item cs-loss"><i class="fa-solid fa-xmark"></i> {recent_losses}败</span>
        <span class="cs-item cs-wr"><i class="fa-solid fa-chart-line"></i> {_fmt_pct(recent_wr_val)}</span>
        <div class="cs-bar-wrap">
          <div class="cs-bar">
            <div class="cs-bar-win" style="width:{win_bar_pct:.0f}%"></div>
          </div>
        </div>
      </div>"""

    # ── Civ bars ──
    sorted_civs = sorted(civ_stats.items(), key=lambda x: -x[1]["games"])[:6]
    civ_bars = ""
    for civ, st in sorted_civs:
        cname = _civ_name(civ)
        emoji = _CIV_EMOJI.get(civ, "🏛️")
        wr = st["wins"] / st["games"] * 100
        bar_pct = min(wr, 100)
        bar_cls = "civ-bar-fill-high" if wr >= 60 else ("civ-bar-fill-mid" if wr >= 40 else "civ-bar-fill-low")
        civ_bars += f"""
      <div class="civ-bar">
        <span class="civ-bar-name">{emoji} {cname}</span>
        <span class="civ-bar-count">{st['games']}场</span>
        <div class="civ-bar-track">
          <div class="civ-bar-fill {bar_cls}" style="width:{bar_pct:.0f}%"></div>
          <span class="civ-bar-pct">{wr:.0f}%</span>
        </div>
      </div>"""

    # ── Recent games (right column) ──
    recent_items = ""
    for g in games[:3]:
        map_name = g.get("map", "?")
        kind = _MODE_LABELS.get(g.get("kind", ""), g.get("kind", ""))
        started = _elapsed_ago(g.get("started_at", ""))
        my_data = None
        for team in g.get("teams", []):
            for p in team:
                pd = p.get("player", p)
                if pd.get("profile_id") == pid:
                    my_data = pd
                    break
        if not my_data:
            continue
        result = my_data.get("result", "unknown")
        icon = "✅" if result == "win" else "❌"
        civ = _civ_name(my_data.get("civilization", ""))
        rd = my_data.get("rating_diff")
        rd_str = f"+{rd}" if rd and rd > 0 else str(rd) if rd else ""
        rd_cls = "recent-rd-win" if result == "win" else "recent-rd-loss"
        recent_items += f"""
      <div class="recent-item">
        <span class="recent-icon">{icon}</span>
        <div style="flex:1;">
          <div class="recent-map">{map_name}</div>
          <div class="recent-civ">{civ} · {kind}</div>
        </div>
        <span class="recent-rd {rd_cls}">{rd_str}</span>
        <span class="recent-time">{started}</span>
      </div>"""

    # ── Records ──
    rec_max_rating = 0
    rec_max_mode = ""
    rec_max_streak = 0
    rec_max_streak_mode = ""
    rec_7d_rating = 0
    rec_7d_mode = ""
    rec_highest_rank = ""
    rec_highest_mode = ""
    for mk, m in modes.items():
        mr = m.get("max_rating") or 0
        if mr > rec_max_rating:
            rec_max_rating = mr
            rec_max_mode = mk
        ms = abs(m.get("streak", 0) or 0)
        if ms > rec_max_streak:
            rec_max_streak = ms
            rec_max_streak_mode = mk
        r7 = m.get("max_rating_7d") or 0
        if r7 > rec_7d_rating:
            rec_7d_rating = r7
            rec_7d_mode = mk
        rl = m.get("rank_level", "")
        if rl and rl != "unranked" and rl in _LVL_ORDER:
            if not rec_highest_rank or _LVL_ORDER.index(rl) < _LVL_ORDER.index(rec_highest_rank):
                rec_highest_rank = rl
                rec_highest_mode = mk

    records_html = f"""
    <div class="record-item">
      <div class="record-label">最高评分</div>
      <div class="record-value record-value-gold">{_fmt(rec_max_rating)}</div>
      <div class="record-sub">{_MODE_LABELS.get(rec_max_mode, rec_max_mode)}</div>
    </div>
    <div class="record-item">
      <div class="record-label">最长连胜</div>
      <div class="record-value record-value-green"><i class="fa-solid fa-fire"></i> {rec_max_streak}</div>
      <div class="record-sub">{_MODE_LABELS.get(rec_max_streak_mode, rec_max_streak_mode)}</div>
    </div>
    <div class="record-item">
      <div class="record-label">7日最高</div>
      <div class="record-value record-value-blue">{_fmt(rec_7d_rating)}</div>
      <div class="record-sub">{_MODE_LABELS.get(rec_7d_mode, rec_7d_mode)}</div>
    </div>
    <div class="record-item" style="border-right:none;">
      <div class="record-label">最高段位</div>
      <div class="record-value record-value-orange">{_rank_label(rec_highest_rank) if rec_highest_rank else "暂无"}</div>
      <div class="record-sub">{_MODE_LABELS.get(rec_highest_mode, rec_highest_mode)} 赛季 {season}</div>
    </div>"""

    # ── Random quote ──
    quote_html = f'<div class="civ-quote">{random.choice(_QUOTES)}</div>'

    # ── Local image ──
    local_img = _get_random_profile_image()
    if local_img:
        art_icon_html = f'<img class="art-avatar" src="{local_img}" alt="profile illustration"/>'
    else:
        art_icon_html = '<div class="art-icon"><i class="fa-solid fa-shield-halved"></i></div>'

    max_r = max_rating or 1
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<link href="https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-sc@5.2.9/index.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: "Noto Sans SC","WenQuanYi Micro Hei","PingFang SC","Microsoft YaHei",sans-serif;
  background: #F0F6FF; padding: 24px; color: #1E3A5F; min-height: 100vh;
}}
.container {{ max-width: 1280px; margin: 0 auto; }}
.header {{
  background: #FFFFFF; border-radius: 16px; box-shadow: 0 2px 12px rgba(91,155,213,0.10);
  padding: 20px 28px; margin-bottom: 20px; border-left: 4px solid #5B9BD5;
  display: flex; justify-content: space-between; align-items: flex-start;
}}
.header-left {{ display: flex; align-items: center; gap: 14px; }}
.header-flag {{ font-size: 36px; line-height: 1; }}
.header-name {{ font-size: 26px; font-weight: 800; color: #1E3A5F; }}
.header-badges {{ display: flex; gap: 6px; margin-top: 4px; }}
.header-badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 700; }}
.header-badge-gold {{ background: linear-gradient(135deg, #FFD700, #FFB900); color: #fff; }}
.header-badge-blue {{ background: #5B9BD5; color: #fff; }}
.header-meta {{ margin-top: 6px; font-size: 12px; color: #6B7B8D; display: flex; gap: 16px; }}
.header-meta i {{ margin-right: 4px; }}
.header-right {{ text-align: right; }}
.header-id {{ font-size: 13px; color: #5B9BD5; }}
.header-id i {{ margin-right: 4px; }}
.header-mode {{ font-size: 12px; color: #8EA9C1; margin-top: 2px; }}
.columns {{ display: flex; gap: 16px; margin-bottom: 20px; }}
.col-left {{ flex: 0 0 300px; display: flex; flex-direction: column; gap: 14px; }}
.section-title {{
  font-size: 14px; font-weight: 700; color: #2E75B6;
  padding-bottom: 6px; margin-bottom: 10px;
  border-bottom: 2px solid #D6E8F7; display: flex; align-items: center; gap: 6px;
}}
.mode-card {{ background: #FFFFFF; border-radius: 12px; padding: 14px 16px; border-left: 3px solid #5B9BD5; box-shadow: 0 1px 4px rgba(91,155,213,0.08); }}
.mode-card-label {{ font-size: 12px; color: #8EA9C1; margin-bottom: 2px; }}
.mode-card-row {{ display: flex; align-items: baseline; gap: 10px; }}
.mode-card-rating {{ font-size: 28px; font-weight: 800; }}
.mode-card-rank {{ font-size: 12px; padding: 1px 8px; border-radius: 10px; background: #E8F1FA; color: #2E75B6; font-weight: 600; }}
.mode-card-stats {{ font-size: 12px; color: #6B7B8D; margin-top: 4px; display: flex; gap: 12px; }}
.stat-green {{ color: #4CAF50; }} .stat-orange {{ color: #FF9800; }} .stat-red {{ color: #E53935; }}
.mode-bar {{ margin-top: 6px; height: 4px; background: #E8F1FA; border-radius: 2px; overflow: hidden; }}
.mode-bar-fill {{ height: 100%; border-radius: 2px; }}
.col-middle {{ flex: 1; display: flex; flex-direction: column; gap: 14px; min-height: 0; }}
.core-stats-grid {{ background: #FFFFFF; border-radius: 12px; padding: 12px 14px; box-shadow: 0 1px 4px rgba(91,155,213,0.08); min-height: 180px; flex-shrink: 0; }}
.core-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 6px; }}
.core-grid:last-of-type {{ margin-bottom: 0; }}
.cs-card {{ text-align: center; padding: 8px 4px; background: #F8FAFE; border-radius: 10px; }}
.cs-card-value {{ font-size: 20px; font-weight: 800; line-height: 1.2; }}
.cs-clr-blue {{ color: #5B9BD5; }} .cs-clr-green {{ color: #4CAF50; }} .cs-clr-gold {{ color: #FFB900; }} .cs-clr-orange {{ color: #FF9800; }} .cs-clr-rank {{ color: #2E75B6; }}
.cs-card-label {{ font-size: 10px; color: #8EA9C1; margin-top: 2px; }}
.trend-wrap {{ display: flex; align-items: center; gap: 8px; margin-top: 6px; padding: 6px 12px; background: #F8FAFE; border-radius: 10px; }}
.trend-lbl {{ font-size: 11px; color: #8EA9C1; white-space: nowrap; flex-shrink: 0; }}
.trend-label {{ font-size: 16px; font-weight: 800; color: #5B9BD5; white-space: nowrap; flex-shrink: 0; }}
.civ-section {{ background: #FFFFFF; border-radius: 12px; padding: 14px 16px; box-shadow: 0 1px 4px rgba(91,155,213,0.08); flex: 1; display: flex; flex-direction: column; min-height: 0; }}
.civ-section-inner {{ flex: 1; display: flex; flex-direction: column; justify-content: space-around; }}
.civ-quote {{ padding: 8px 4px 0; font-size: 12px; color: #8EA9C1; font-style: italic; text-align: center; line-height: 1.5; border-top: 1px solid #E8F1FA; margin-top: 4px; }}
.civ-bar {{ display: flex; align-items: center; gap: 10px; padding: 6px 0; }}
.civ-bar:not(:last-child) {{ border-bottom: 1px solid #E8F1FA; }}
.civ-bar-name {{ width: 60px; font-size: 13px; font-weight: 600; color: #1E3A5F; }}
.civ-bar-count {{ width: 36px; font-size: 11px; color: #8EA9C1; text-align: right; }}
.civ-bar-track {{ flex: 1; height: 18px; background: #E8F1FA; border-radius: 9px; overflow: hidden; position: relative; }}
.civ-bar-fill {{ height: 100%; border-radius: 9px; }}
.civ-bar-fill-high {{ background: linear-gradient(90deg, #5B9BD5, #7BB3E0); }}
.civ-bar-fill-mid {{ background: linear-gradient(90deg, #8EA9C1, #B0C4DE); }}
.civ-bar-fill-low {{ background: linear-gradient(90deg, #E57373, #EF9A9A); }}
.civ-bar-pct {{ position: absolute; right: 8px; top: 50%; transform: translateY(-50%); font-size: 10px; font-weight: 700; color: #fff; }}
.civ-summary {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 8px 10px; margin-bottom: 8px; background: #F8FAFE; border-radius: 10px; font-size: 12px; }}
.cs-item {{ display: inline-flex; align-items: center; gap: 3px; color: #6B7B8D; }}
.cs-item i {{ font-size: 11px; }}
.cs-win {{ color: #4CAF50; }} .cs-loss {{ color: #E53935; }}
.cs-wr {{ color: #FFB900; font-weight: 700; }}
.cs-bar-wrap {{ flex: 1; min-width: 60px; }}
.cs-bar {{ height: 8px; background: #E8F1FA; border-radius: 4px; overflow: hidden; }}
.cs-bar-win {{ height: 100%; background: linear-gradient(90deg, #4CAF50, #66BB6A); border-radius: 4px; }}
.col-right {{ flex: 0 0 300px; display: flex; flex-direction: column; gap: 14px; }}
.art-panel {{ background: #FFFFFF; border-radius: 12px; overflow: hidden; position: relative; min-height: 200px; box-shadow: 0 1px 4px rgba(91,155,213,0.08); flex: 1; display: flex; flex-direction: column; background-image: radial-gradient(ellipse at 70% 40%, rgba(91,155,213,0.06) 0%, transparent 60%), radial-gradient(ellipse at 30% 60%, rgba(46,117,182,0.04) 0%, transparent 50%); }}
.art-content {{ padding: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 200px; position: relative; flex: 1; overflow: hidden; }}
.art-icon {{ font-size: 72px; color: #D6E8F7; user-select: none; line-height: 1; }}
.art-avatar {{ width: 100%; height: 100%; object-fit: contain; padding: 8px; }}
.art-deco {{ position: absolute; border: 1px solid #D6E8F7; border-radius: 50%; }}
.art-deco-1 {{ width: 120px; height: 120px; top: -30px; right: -20px; }}
.art-deco-2 {{ width: 80px; height: 80px; bottom: -10px; left: -10px; }}
.recent-section {{ background: #FFFFFF; border-radius: 12px; padding: 14px 16px; box-shadow: 0 1px 4px rgba(91,155,213,0.08); }}
.recent-item {{ display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #E8F1FA; }}
.recent-item:last-child {{ border-bottom: none; }}
.recent-icon {{ font-size: 16px; width: 20px; text-align: center; }}
.recent-map {{ font-size: 13px; font-weight: 600; color: #1E3A5F; flex: 1; }}
.recent-civ {{ font-size: 11px; color: #8EA9C1; }}
.recent-rd {{ font-size: 12px; font-weight: 700; width: 44px; text-align: right; }}
.recent-rd-win {{ color: #4CAF50; }} .recent-rd-loss {{ color: #E53935; }}
.recent-time {{ font-size: 11px; color: #B0C4DE; width: 52px; text-align: right; }}
.bottom-records {{ background: #FFFFFF; border-radius: 14px; box-shadow: 0 2px 12px rgba(91,155,213,0.10); padding: 16px 24px; margin-bottom: 14px; border-left: 4px solid #FFB900; }}
.records-title {{ font-size: 14px; font-weight: 700; color: #2E75B6; padding-bottom: 8px; margin-bottom: 10px; border-bottom: 2px solid #D6E8F7; display: flex; align-items: center; gap: 6px; }}
.records-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
.record-item {{ text-align: center; }}
.record-item:not(:last-child) {{ border-right: 1px solid #E8F1FA; }}
.record-label {{ font-size: 11px; color: #8EA9C1; }}
.record-value {{ font-size: 20px; font-weight: 800; margin: 2px 0; }}
.record-value-gold {{ color: #FFB900; }} .record-value-green {{ color: #4CAF50; }}
.record-value-blue {{ color: #5B9BD5; }} .record-value-orange {{ color: #FF9800; }}
.record-sub {{ font-size: 10px; color: #B0C4DE; }}
.footer {{ text-align: center; font-size: 11px; color: #B0C4DE; padding: 8px 0; letter-spacing: 1px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="header-left">
      <div class="header-flag">{flag}</div>
      <div class="header-info">
        <div class="header-name">{name}</div>
        <div class="header-badges">
          {f'<span class="header-badge header-badge-gold">{header_rank}</span>' if header_rank else ""}
          {f'<span class="header-badge header-badge-blue">{_fmt(header_rating)} 分</span>' if header_rating else ""}
        </div>
        <div class="header-meta">
          {f'<span><i class="fa-brands fa-steam"></i> {steam[:20]}...</span>' if steam else ""}
          <span><i class="fa-regular fa-clock"></i> 最后战斗: {_elapsed_ago(last_game_at)}</span>
        </div>
      </div>
    </div>
    <div class="header-right">
      <div class="header-id"><i class="fa-regular fa-id-card"></i> Profile ID: {pid}</div>
      <div class="header-mode"><i class="fa-solid fa-globe"></i> 赛季 {season}</div>
    </div>
  </div>
  <div class="columns">
    <div class="col-left">
      <div>
        <div class="section-title"><i class="fa-solid fa-trophy"></i> 排位模式</div>
        <div style="display:flex;flex-direction:column;gap:8px;">
          {mode_cards if mode_cards else '<div style="color:#8EA9C1;padding:12px;text-align:center;">暂无排位数据</div>'}
        </div>
      </div>
    </div>
    <div class="col-middle">
      <div class="core-stats-grid">
        <div class="core-grid">
          <div class="cs-card"><div class="cs-card-value cs-clr-blue">{_fmt(total_games)}</div><div class="cs-card-label">总对局</div></div>
          <div class="cs-card"><div class="cs-card-value cs-clr-green">{_fmt(total_wins)}</div><div class="cs-card-label">胜利</div></div>
          <div class="cs-card"><div class="cs-card-value cs-clr-gold">{_fmt_pct(overall_wr)}</div><div class="cs-card-label">综合胜率</div></div>
          <div class="cs-card"><div class="cs-card-value cs-clr-blue">{_fmt(max_rating)}</div><div class="cs-card-label">历史最高分</div></div>
        </div>
        <div class="core-grid">
          <div class="cs-card"><div class="cs-card-value cs-clr-green">{_fmt(ranked_games)}</div><div class="cs-card-label">排位场次</div></div>
          <div class="cs-card"><div class="cs-card-value cs-clr-gold">{_fmt_pct(ranked_wr)}</div><div class="cs-card-label">排位胜率</div></div>
          <div class="cs-card"><div class="cs-card-value cs-clr-orange">{_fmt(max_streak)}</div><div class="cs-card-label">最长连胜</div></div>
          <div class="cs-card"><div class="cs-card-value cs-clr-rank" style="font-size:14px;">{best_rank_label}</div><div class="cs-card-label">最高段位</div></div>
        </div>
        {trend_svg}
      </div>
      <div class="civ-section">
        <div class="section-title"><i class="fa-solid fa-flag"></i> 最近文明使用分布</div>
        {perf_summary}
        <div class="civ-section-inner">
          {civ_bars if civ_bars else '<div style="color:#8EA9C1;text-align:center;padding:8px;">暂无对局数据</div>'}
          {quote_html}
        </div>
      </div>
    </div>
    <div class="col-right">
      <div class="art-panel">
        <div class="art-deco art-deco-1"></div>
        <div class="art-deco art-deco-2"></div>
        <div class="art-content">
          {art_icon_html}
        </div>
      </div>
      <div class="recent-section">
        <div class="section-title"><i class="fa-regular fa-calendar"></i> 最近对局</div>
        <div>{recent_items if recent_items else '<div style="color:#8EA9C1;text-align:center;padding:8px;">暂无对局记录</div>'}</div>
      </div>
    </div>
  </div>
  <div class="bottom-records">
    <div class="records-title"><i class="fa-solid fa-trophy"></i> 最高记录</div>
    <div class="records-grid">{records_html}</div>
  </div>
  <div class="footer">Powered by astrbot_plugin_aoe4</div>
</div>
</body>
</html>"""


# ─── Player Profile Rendering ───

_CIV_EMOJI = {
    "english": "🏴", "chinese": "🇨🇳", "french": "🏴",
    "holy_roman_empire": "🇩🇪", "mongols": "🇲🇳", "rus": "🇷🇺",
    "delhi_sultanate": "🇮🇳", "abbasid_dynasty": "🇸🇦", "ottomans": "🇹🇷",
    "malians": "🇲🇱", "byzantines": "🇧🇾", "japanese": "🇯🇵",
    "ayyubids": "🇸🇦", "jeanne_darc": "🇫🇷", "order_of_the_dragon": "🇷🇴",
    "zhu_xis_legacy": "🇨🇳", "jin_dynasty": "🇨🇳", "golden_horde": "🇰🇿",
    "sengoku_daimyo": "🇯🇵", "knights_templar": "🏰", "house_of_lancaster": "🏴",
    "macedonian_dynasty": "🇬🇷", "tughlaq_dynasty": "🇮🇳",
}
_COUNTRY_FLAG = {"cn": "🇨🇳", "us": "🇺🇸", "gb": "🇬🇧", "de": "🇩🇪", "fr": "🇫🇷", "jp": "🇯🇵", "kr": "🇰🇷", "ru": "🇷🇺", "sg": "🇸🇬", "au": "🇦🇺", "ca": "🇨🇦", "nl": "🇳🇱", "br": "🇧🇷", "rs": "🇷🇸"}
_RANK_EMOJI = {"conqueror": "🏆", "diamond": "💎", "platinum": "🥇", "gold": "🥈", "silver": "🥉", "bronze": "🟤", "unranked": "❓"}
_MODE_ORDER = ["rm_solo", "rm_2v2", "rm_3v3", "rm_4v4", "rm_team", "qm_1v1", "qm_2v2", "qm_3v3", "qm_4v4"]
_MODE_LABELS = {"rm_solo": "1v1 排位", "rm_2v2": "2v2 排位", "rm_3v3": "3v3 排位", "rm_4v4": "4v4 排位", "rm_team": "组队排位", "qm_1v1": "1v1 快速", "qm_2v2": "2v2 快速", "qm_3v3": "3v3 快速", "qm_4v4": "4v4 快速"}
_MODE_COLORS = {"rm_solo": "#5B9BD5", "rm_2v2": "#4CAF50", "rm_3v3": "#FF9800", "rm_4v4": "#AB47BC", "rm_team": "#FF6B35", "qm_1v1": "#8EA9C1", "qm_2v2": "#8EA9C1", "qm_3v3": "#8EA9C1", "qm_4v4": "#8EA9C1"}
_LVL_ORDER = ["conqueror_3","conqueror_2","conqueror_1","diamond_3","diamond_2","diamond_1","platinum_3","platinum_2","platinum_1","gold_3","gold_2","gold_1","silver_3","silver_2","silver_1","bronze_3","bronze_2","bronze_1"]
_QUOTES = ["「故上兵伐谋，其次伐交，其次伐兵，其下攻城。」—— 孙子《孙子兵法》","「知己知彼，百战不殆。」—— 孙子《孙子兵法》","「天下武功，唯快不破。」—— 火云邪神《功夫》","「军队的威力不在于数量，而在于纪律。」—— 威廉·杜克","「战争是政治的延续。」—— 卡尔·冯·克劳塞维茨","「在绝对的实力面前，一切计谋都是徒劳。」—— 俾斯麦","「想成事，先修路。」—— 经济学的第一课","「打不过就加入。」—— 天梯生存法则","「我可以输，但对面的运营必须乱。」—— 帝国老手箴言","「当你不知道做什么的时候，就去造农民。」—— AoE4 新手圣经","「经济的胜利才是真正的胜利。」—— 种田流的信仰","「一波不行就再来一波。」—— 帝国时代玩家的坚持","「不怕神一样的对手，只怕猪一样的队友。」—— 团队排位的真理","「地图决定打法，版本决定强度。」—— 天梯生态观察","「这就是帝国时代！这就是策略游戏的魅力！」—— 社区名言","「没有垃圾兵种，只有垃圾操作。」—— 高手的谦辞","「活着才有输出，运营才有未来。」—— 帝国生存法则","「我不需要赢在开局，只要赢在终局。」—— 运营流玩家的信条"]

def _fmt_pct(v):
    if v is None: return "N/A"
    return f"{v:.1f}%"

def _rank_label(level):
    if not level or TR is None: return "未定级"
    rank = TR.rank_level(level)
    prefix = ""
    for k, e in _RANK_EMOJI.items():
        if level.startswith(k): prefix = e; break
    return f"{prefix} {rank}" if prefix else rank

def _elapsed_ago(iso_str):
    if not iso_str: return "未知"
    from datetime import datetime, timezone
    try:
        t = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - t
        d = diff.days
        if d > 365: return f"{d//365}年前"
        if d > 30: return f"{d//30}个月前"
        if d > 0: return f"{d}天前"
        h = diff.seconds // 3600
        if h > 0: return f"{h}小时前"
        m = diff.seconds // 60
        return f"{m}分钟前" if m > 0 else "刚刚"
    except: return iso_str

def _get_random_profile_image():
    d = _PROFILE_IMAGE_DIR
    if not d or not os.path.isdir(d): return ""
    exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
    files = [f for f in os.listdir(d) if f.lower().endswith(exts)]
    if not files: return ""
    try:
        with open(os.path.join(d, random.choice(files)), "rb") as f:
            data = f.read()
        ext = os.path.splitext(files[0])[1][1:].lower()
        mime = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","gif":"image/gif","webp":"image/webp"}.get(ext,"image/png")
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    except: return ""

async def generate_profile_html(player: dict, games: list[dict], season: str, image_dir: str = "") -> str:
    if image_dir:
        global _PROFILE_IMAGE_DIR
        _PROFILE_IMAGE_DIR = image_dir
    name = player.get("name", "?")
    flag = _COUNTRY_FLAG.get(player.get("country", ""), "")
    pid = player.get("profile_id", "?")
    steam = player.get("steam_id", "")
    modes = player.get("modes", {})
    total_games = sum((m.get("games_count",0) or 0) for m in modes.values())
    total_wins = sum((m.get("wins_count",0) or 0) for m in modes.values())
    overall_wr = (total_wins/total_games*100) if total_games else 0
    max_rating = 0; last_game_at = ""
    for mk,m in modes.items():
        r = m.get("max_rating") or 0
        if r > max_rating: max_rating = r
        lg = m.get("last_game_at")
        if lg and (not last_game_at or lg > last_game_at): last_game_at = lg
    first_mode = None
    for mk in _MODE_ORDER:
        if mk in modes and modes[mk].get("rating"): first_mode = modes[mk]; break
    header_rank = _rank_label(first_mode.get("rank_level")) if first_mode else ""
    header_rating = first_mode.get("rating") if first_mode else None
    ranked_games=ranked_wins=max_streak=0
    for mk,m in modes.items():
        if not mk.startswith("rm_"): continue
        ranked_games += m.get("games_count",0) or 0
        ranked_wins += m.get("wins_count",0) or 0
        ms = abs(m.get("streak",0) or 0)
        if ms > max_streak: max_streak = ms
    ranked_wr = (ranked_wins/ranked_games*100) if ranked_games else 0
    best_rank = ""
    for mk,m in modes.items():
        rl = m.get("rank_level","")
        if rl and rl!="unranked" and rl in _LVL_ORDER:
            if not best_rank or _LVL_ORDER.index(rl)<_LVL_ORDER.index(best_rank): best_rank=rl
    best_rank_label = _rank_label(best_rank) if best_rank else "暂无"
    # trend
    trend_values=[];cum=0
    import aiohttp
    async with aiohttp.ClientSession(headers={"User-Agent":"aoe4-bot/1.0"}) as sess:
        for g in reversed(games[:10]):
            gid=g.get("game_id")
            if not gid: continue
            try:
                async with sess.get(f"https://aoe4world.com/api/v0/games/{gid}",timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status!=200: continue
                    detail=await r.json()
            except: continue
            for team in detail.get("teams",[]):
                for p in team:
                    if p.get("profile_id")==pid:
                        rd=p.get("rating_diff")
                        if rd is not None: cum+=rd; trend_values.append(cum)
                        break
    trend_svg=""
    if len(trend_values)>=2:
        n=len(trend_values);w=180;h=24
        mn=min(trend_values);mx=max(trend_values);rg=mx-mn if mx-mn>0 else 1
        pts=" ".join(f"{(w/(n-1))*i:.0f},{h-(v-mn)/rg*(h-4)-2:.0f}" for i,v in enumerate(trend_values))
        last_v=trend_values[-1];sgn="+" if last_v>=0 else ""
        trend_svg=f'<div class="trend-wrap"><span class="trend-lbl">近10场评分变化</span><svg viewBox="0 0 {w} {h}" style="flex:1;height:24px;"><polyline points="{pts}" fill="none" stroke="#5B9BD5" stroke-width="2"/></svg><span class="trend-label">{sgn}{last_v}</span></div>'
    # mode cards
    mode_cards=""
    for mk in _MODE_ORDER:
        m=modes.get(mk)
        if not m: continue
        is_ranked=mk.startswith("rm_")
        bc=_MODE_COLORS.get(mk,"#5B9BD5") if is_ranked else "#B0C4DE"
        cc="" if is_ranked else ' style="opacity:0.7"'
        rating=m.get("rating")
        rl=m.get("rank_level")
        rl_lbl=_rank_label(rl) if rl else ""
        gn=m.get("games_count",0) or 0
        wv=m.get("win_rate")
        ws=_fmt_pct(wv) if wv is not None else "N/A"
        sk=m.get("streak",0) or 0
        ss=""
        if sk>0: ss=f'<span class="stat-orange"><i class="fa-solid fa-fire"></i> {sk}连胜</span>'
        elif sk<0: ss=f'<span class="stat-red"><i class="fa-solid fa-arrow-down"></i> {abs(sk)}连败</span>'
        if rating:
            rs=_fmt(rating)
            rc=f'style="color:{bc}"'
            rb=f'<span class="mode-card-rank">{rl_lbl}</span>' if rl_lbl else ""
            bh=""
            if mk in("rm_solo","rm_team") and max_rating:
                bp=min(rating/max_rating*100,100)
                bh=f'<div class="mode-bar"><div class="mode-bar-fill" style="width:{bp:.0f}%;background:{bc}"></div></div>'
        else:
            rs="暂无数据";rc='style="color:#B0C4DE"';rb="";bh=""
        mode_cards+=f'<div class="mode-card"{cc} style="border-left-color:{bc}"><div class="mode-card-label">{_MODE_LABELS.get(mk,mk)}</div><div class="mode-card-row"><span class="mode-card-rating" {rc}>{rs}</span>{rb}</div><div class="mode-card-stats"><span class="stat-green">胜率 {ws}</span><span>场次 {gn}</span>{ss}</div>{bh}</div>'
    # civ stats
    civ_stats={}
    for g in games:
        for team in g.get("teams",[]):
            for p in team:
                pd=p.get("player",p)
                if pd.get("profile_id")==pid:
                    c=pd.get("civilization","unknown");r=pd.get("result","unknown")
                    if c not in civ_stats: civ_stats[c]={"games":0,"wins":0}
                    civ_stats[c]["games"]+=1
                    if r=="win": civ_stats[c]["wins"]+=1
    rw=sum(s["wins"] for s in civ_stats.values())
    rt=sum(s["games"] for s in civ_stats.values())
    rwv=(rw/rt*100) if rt else 0
    wbp=(rw/rt*100) if rt else 0
    ps=""
    if rt>0:
        ps=f'<div class="civ-summary"><span class="cs-item"><i class="fa-solid fa-gamepad"></i> 近{rt}场</span><span class="cs-item cs-win"><i class="fa-solid fa-check"></i> {rw}胜</span><span class="cs-item cs-loss"><i class="fa-solid fa-xmark"></i> {rt-rw}败</span><span class="cs-item cs-wr"><i class="fa-solid fa-chart-line"></i> {_fmt_pct(rwv)}</span><div class="cs-bar-wrap"><div class="cs-bar"><div class="cs-bar-win" style="width:{wbp:.0f}%"></div></div></div></div>'
    sorted_civs=sorted(civ_stats.items(),key=lambda x:-x[1]["games"])[:6]
    cb=""
    for civ,st in sorted_civs:
        cn=_civ_name(civ);emoji=_CIV_EMOJI.get(civ,"🏛️")
        wr=st["wins"]/st["games"]*100;bp=min(wr,100)
        cl="civ-bar-fill-high" if wr>=60 else ("civ-bar-fill-mid" if wr>=40 else "civ-bar-fill-low")
        cb+=f'<div class="civ-bar"><span class="civ-bar-name">{emoji} {cn}</span><span class="civ-bar-count">{st["games"]}场</span><div class="civ-bar-track"><div class="civ-bar-fill {cl}" style="width:{bp:.0f}%"></div><span class="civ-bar-pct">{wr:.0f}%</span></div></div>'
    # recent items
    ri=""
    for g in games[:3]:
        mn=g.get("map","?");kd=_MODE_LABELS.get(g.get("kind",""),g.get("kind",""));st=_elapsed_ago(g.get("started_at",""))
        md=None
        for team in g.get("teams",[]):
            for p in team:
                pd=p.get("player",p)
                if pd.get("profile_id")==pid: md=pd; break
        if not md: continue
        res=md.get("result","unknown");ic="✅" if res=="win" else "❌"
        cv=_civ_name(md.get("civilization",""));rd=md.get("rating_diff")
        rds=f"+{rd}" if rd and rd>0 else str(rd) if rd else ""
        rdc="recent-rd-win" if res=="win" else "recent-rd-loss"
        ri+=f'<div class="recent-item"><span class="recent-icon">{ic}</span><div style="flex:1;"><div class="recent-map">{mn}</div><div class="recent-civ">{cv} · {kd}</div></div><span class="recent-rd {rdc}">{rds}</span><span class="recent-time">{st}</span></div>'
    # records
    rec={"mr":0,"mm":"","sk":0,"skm":"","r7":0,"r7m":"","hr":"","hrm":""}
    for mk,m in modes.items():
        mr=m.get("max_rating") or 0
        if mr>rec["mr"]: rec["mr"]=mr; rec["mm"]=mk
        ms=abs(m.get("streak",0) or 0)
        if ms>rec["sk"]: rec["sk"]=ms; rec["skm"]=mk
        r7=m.get("max_rating_7d") or 0
        if r7>rec["r7"]: rec["r7"]=r7; rec["r7m"]=mk
        rl=m.get("rank_level","")
        if rl and rl!="unranked" and rl in _LVL_ORDER:
            if not rec["hr"] or _LVL_ORDER.index(rl)<_LVL_ORDER.index(rec["hr"]): rec["hr"]=rl; rec["hrm"]=mk
    rh=f'<div class="record-item"><div class="record-label">最高评分</div><div class="record-value record-value-gold">{_fmt(rec["mr"])}</div><div class="record-sub">{_MODE_LABELS.get(rec["mm"],rec["mm"])}</div></div><div class="record-item"><div class="record-label">最长连胜</div><div class="record-value record-value-green"><i class="fa-solid fa-fire"></i> {rec["sk"]}</div><div class="record-sub">{_MODE_LABELS.get(rec["skm"],rec["skm"])}</div></div><div class="record-item"><div class="record-label">7日最高</div><div class="record-value record-value-blue">{_fmt(rec["r7"])}</div><div class="record-sub">{_MODE_LABELS.get(rec["r7m"],rec["r7m"])}</div></div><div class="record-item" style="border-right:none;"><div class="record-label">最高段位</div><div class="record-value record-value-orange">{_rank_label(rec["hr"]) if rec["hr"] else "暂无"}</div><div class="record-sub">{_MODE_LABELS.get(rec["hrm"],rec["hrm"])} 赛季 {season}</div></div>'
    qh=f'<div class="civ-quote">{random.choice(_QUOTES)}</div>'
    li=_get_random_profile_image()
    ai=f'<img class="art-avatar" src="{li}" alt=""/>' if li else '<div class="art-icon"><i class="fa-solid fa-shield-halved"></i></div>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><link href="https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-sc@5.2.9/index.css" rel="stylesheet"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
<style>
* {{margin:0;padding:0;box-sizing:border-box}}
body {{font-family:"Noto Sans SC","WenQuanYi Micro Hei","PingFang SC","Microsoft YaHei",sans-serif;background:#F0F6FF;padding:24px;color:#1E3A5F}}
.container {{max-width:1280px;margin:0 auto}}
.header {{background:#FFF;border-radius:16px;box-shadow:0 2px 12px rgba(91,155,213,0.10);padding:20px 28px;margin-bottom:20px;border-left:4px solid #5B9BD5;display:flex;justify-content:space-between;align-items:flex-start}}
.header-left {{display:flex;align-items:center;gap:14px}}
.header-flag {{font-size:36px}}
.header-name {{font-size:26px;font-weight:800;color:#1E3A5F}}
.header-badges {{display:flex;gap:6px;margin-top:4px}}
.header-badge {{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700}}
.header-badge-gold {{background:linear-gradient(135deg,#FFD700,#FFB900);color:#fff}}
.header-badge-blue {{background:#5B9BD5;color:#fff}}
.header-meta {{margin-top:6px;font-size:12px;color:#6B7B8D;display:flex;gap:16px}}
.header-right {{text-align:right}}
.header-id {{font-size:13px;color:#5B9BD5}}
.header-mode {{font-size:12px;color:#8EA9C1;margin-top:2px}}
.columns {{display:flex;gap:16px;margin-bottom:20px}}
.col-left {{flex:0 0 300px;display:flex;flex-direction:column;gap:14px}}
.section-title {{font-size:14px;font-weight:700;color:#2E75B6;padding-bottom:6px;margin-bottom:10px;border-bottom:2px solid #D6E8F7;display:flex;align-items:center;gap:6px}}
.mode-card {{background:#FFF;border-radius:12px;padding:14px 16px;border-left:3px solid #5B9BD5;box-shadow:0 1px 4px rgba(91,155,213,0.08)}}
.mode-card-label {{font-size:12px;color:#8EA9C1}}
.mode-card-row {{display:flex;align-items:baseline;gap:10px}}
.mode-card-rating {{font-size:28px;font-weight:800}}
.mode-card-rank {{font-size:12px;padding:1px 8px;border-radius:10px;background:#E8F1FA;color:#2E75B6;font-weight:600}}
.mode-card-stats {{font-size:12px;color:#6B7B8D;margin-top:4px;display:flex;gap:12px}}
.stat-green {{color:#4CAF50}} .stat-orange {{color:#FF9800}} .stat-red {{color:#E53935}}
.mode-bar {{margin-top:6px;height:4px;background:#E8F1FA;border-radius:2px;overflow:hidden}}
.mode-bar-fill {{height:100%;border-radius:2px}}
.col-middle {{flex:1;display:flex;flex-direction:column;gap:14px;min-height:0}}
.core-stats-grid {{background:#FFF;border-radius:12px;padding:12px 14px;box-shadow:0 1px 4px rgba(91,155,213,0.08);min-height:180px;flex-shrink:0}}
.core-grid {{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:6px}}
.cs-card {{text-align:center;padding:8px 4px;background:#F8FAFE;border-radius:10px}}
.cs-card-value {{font-size:20px;font-weight:800}}
.cs-clr-blue {{color:#5B9BD5}} .cs-clr-green {{color:#4CAF50}} .cs-clr-gold {{color:#FFB900}} .cs-clr-orange {{color:#FF9800}} .cs-clr-rank {{color:#2E75B6}}
.cs-card-label {{font-size:10px;color:#8EA9C1}}
.trend-wrap {{display:flex;align-items:center;gap:8px;margin-top:6px;padding:6px 12px;background:#F8FAFE;border-radius:10px}}
.trend-lbl {{font-size:11px;color:#8EA9C1;white-space:nowrap;flex-shrink:0}}
.trend-label {{font-size:16px;font-weight:800;color:#5B9BD5;white-space:nowrap;flex-shrink:0}}
.civ-section {{background:#FFF;border-radius:12px;padding:14px 16px;box-shadow:0 1px 4px rgba(91,155,213,0.08);flex:1;display:flex;flex-direction:column;min-height:0}}
.civ-section-inner {{flex:1;display:flex;flex-direction:column;justify-content:space-around}}
.civ-quote {{padding:8px 4px 0;font-size:12px;color:#8EA9C1;font-style:italic;text-align:center;border-top:1px solid #E8F1FA;margin-top:4px}}
.civ-bar {{display:flex;align-items:center;gap:10px;padding:6px 0}}
.civ-bar:not(:last-child) {{border-bottom:1px solid #E8F1FA}}
.civ-bar-name {{width:60px;font-size:13px;font-weight:600;color:#1E3A5F}}
.civ-bar-count {{width:36px;font-size:11px;color:#8EA9C1;text-align:right}}
.civ-bar-track {{flex:1;height:18px;background:#E8F1FA;border-radius:9px;overflow:hidden;position:relative}}
.civ-bar-fill {{height:100%;border-radius:9px}}
.civ-bar-fill-high {{background:linear-gradient(90deg,#5B9BD5,#7BB3E0)}}
.civ-bar-fill-mid {{background:linear-gradient(90deg,#8EA9C1,#B0C4DE)}}
.civ-bar-fill-low {{background:linear-gradient(90deg,#E57373,#EF9A9A)}}
.civ-bar-pct {{position:absolute;right:8px;top:50%;transform:translateY(-50%);font-size:10px;font-weight:700;color:#fff}}
.civ-summary {{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 10px;margin-bottom:8px;background:#F8FAFE;border-radius:10px;font-size:12px}}
.cs-item {{display:inline-flex;align-items:center;gap:3px;color:#6B7B8D}}
.cs-win {{color:#4CAF50}} .cs-loss {{color:#E53935}} .cs-wr {{color:#FFB900;font-weight:700}}
.cs-bar-wrap {{flex:1;min-width:60px}}
.cs-bar {{height:8px;background:#E8F1FA;border-radius:4px;overflow:hidden}}
.cs-bar-win {{height:100%;background:linear-gradient(90deg,#4CAF50,#66BB6A);border-radius:4px}}
.col-right {{flex:0 0 300px;display:flex;flex-direction:column;gap:14px}}
.art-panel {{background:#FFF;border-radius:12px;overflow:hidden;position:relative;min-height:200px;box-shadow:0 1px 4px rgba(91,155,213,0.08);flex:1;display:flex;flex-direction:column;background-image:radial-gradient(ellipse at 70% 40%,rgba(91,155,213,0.06) 0%,transparent 60%),radial-gradient(ellipse at 30% 60%,rgba(46,117,182,0.04) 0%,transparent 50%)}}
.art-content {{padding:0;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:200px;flex:1;overflow:hidden}}
.art-icon {{font-size:72px;color:#D6E8F7}}
.art-avatar {{width:100%;height:100%;object-fit:contain;padding:8px}}
.art-deco {{position:absolute;border:1px solid #D6E8F7;border-radius:50%}}
.art-deco-1 {{width:120px;height:120px;top:-30px;right:-20px}}
.art-deco-2 {{width:80px;height:80px;bottom:-10px;left:-10px}}
.recent-section {{background:#FFF;border-radius:12px;padding:14px 16px;box-shadow:0 1px 4px rgba(91,155,213,0.08)}}
.recent-item {{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #E8F1FA}}
.recent-item:last-child {{border-bottom:none}}
.recent-icon {{font-size:16px;width:20px;text-align:center}}
.recent-map {{font-size:13px;font-weight:600;color:#1E3A5F;flex:1}}
.recent-civ {{font-size:11px;color:#8EA9C1}}
.recent-rd {{font-size:12px;font-weight:700;width:44px;text-align:right}}
.recent-rd-win {{color:#4CAF50}} .recent-rd-loss {{color:#E53935}}
.recent-time {{font-size:11px;color:#B0C4DE;width:52px;text-align:right}}
.bottom-records {{background:#FFF;border-radius:14px;box-shadow:0 2px 12px rgba(91,155,213,0.10);padding:16px 24px;margin-bottom:14px;border-left:4px solid #FFB900}}
.records-title {{font-size:14px;font-weight:700;color:#2E75B6;padding-bottom:8px;margin-bottom:10px;border-bottom:2px solid #D6E8F7}}
.records-grid {{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.record-item {{text-align:center}}
.record-item:not(:last-child) {{border-right:1px solid #E8F1FA}}
.record-label {{font-size:11px;color:#8EA9C1}}
.record-value {{font-size:20px;font-weight:800;margin:2px 0}}
.record-value-gold {{color:#FFB900}} .record-value-green {{color:#4CAF50}} .record-value-blue {{color:#5B9BD5}} .record-value-orange {{color:#FF9800}}
.record-sub {{font-size:10px;color:#B0C4DE}}
.footer {{text-align:center;font-size:11px;color:#B0C4DE;padding:8px 0}}
</style></head>
<body><div class="container">
<div class="header"><div class="header-left"><div class="header-flag">{flag}</div><div class="header-info"><div class="header-name">{name}</div><div class="header-badges">{f'<span class="header-badge header-badge-gold">{header_rank}</span>' if header_rank else ''}{f'<span class="header-badge header-badge-blue">{_fmt(header_rating)} 分</span>' if header_rating else ''}</div><div class="header-meta">{f'<span><i class="fa-brands fa-steam"></i> {steam[:20]}...</span>' if steam else ''}<span><i class="fa-regular fa-clock"></i> 最后战斗: {_elapsed_ago(last_game_at)}</span></div></div></div><div class="header-right"><div class="header-id"><i class="fa-regular fa-id-card"></i> Profile ID: {pid}</div><div class="header-mode"><i class="fa-solid fa-globe"></i> 赛季 {season}</div></div></div>
<div class="columns">
<div class="col-left"><div class="section-title"><i class="fa-solid fa-trophy"></i> 排位模式</div><div style="display:flex;flex-direction:column;gap:8px;">{mode_cards if mode_cards else '<div style="color:#8EA9C1;padding:12px;text-align:center;">暂无排位数据</div>'}</div></div>
<div class="col-middle">
<div class="core-stats-grid"><div class="core-grid"><div class="cs-card"><div class="cs-card-value cs-clr-blue">{_fmt(total_games)}</div><div class="cs-card-label">总对局</div></div><div class="cs-card"><div class="cs-card-value cs-clr-green">{_fmt(total_wins)}</div><div class="cs-card-label">胜利</div></div><div class="cs-card"><div class="cs-card-value cs-clr-gold">{_fmt_pct(overall_wr)}</div><div class="cs-card-label">综合胜率</div></div><div class="cs-card"><div class="cs-card-value cs-clr-blue">{_fmt(max_rating)}</div><div class="cs-card-label">历史最高分</div></div></div><div class="core-grid"><div class="cs-card"><div class="cs-card-value cs-clr-green">{_fmt(ranked_games)}</div><div class="cs-card-label">排位场次</div></div><div class="cs-card"><div class="cs-card-value cs-clr-gold">{_fmt_pct(ranked_wr)}</div><div class="cs-card-label">排位胜率</div></div><div class="cs-card"><div class="cs-card-value cs-clr-orange">{_fmt(max_streak)}</div><div class="cs-card-label">最长连胜</div></div><div class="cs-card"><div class="cs-card-value cs-clr-rank" style="font-size:14px">{best_rank_label}</div><div class="cs-card-label">最高段位</div></div></div>{trend_svg}</div>
<div class="civ-section"><div class="section-title"><i class="fa-solid fa-flag"></i> 最近文明使用分布</div>{ps}<div class="civ-section-inner">{cb if cb else '<div style="color:#8EA9C1;text-align:center;padding:8px">暂无对局数据</div>'}{qh}</div></div>
</div>
<div class="col-right">
<div class="art-panel"><div class="art-deco art-deco-1"></div><div class="art-deco art-deco-2"></div><div class="art-content">{ai}</div></div>
<div class="recent-section"><div class="section-title"><i class="fa-regular fa-calendar"></i> 最近对局</div><div>{ri if ri else '<div style="color:#8EA9C1;text-align:center;padding:8px">暂无对局记录</div>'}</div></div>
</div>
</div>
<div class="bottom-records"><div class="records-title"><i class="fa-solid fa-trophy"></i> 最高记录</div><div class="records-grid">{rh}</div></div>
<div class="footer">Powered by astrbot_plugin_aoe4</div>
</div></body></html>"""
