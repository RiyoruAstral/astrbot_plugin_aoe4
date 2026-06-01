import sys
import os
import asyncio
import uuid
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.api.message_components import At, Image, Node, Nodes, Plain
from api_client import AoE4WorldClient, check_flaresolverr_connection
from data_client import AoE4DataClient, CIV_NAME_TO_CODE, CIV_CODE_TO_NAME
import storage

try:
    from score_renderer import generate_score_html, generate_analysis_html, generate_matchup_html, render_html_to_image, close_browser as close_renderer, set_translator as set_renderer_tr, ensure_browser, set_chromium_download_host
    HAS_RENDERER = True
except ImportError:
    HAS_RENDERER = False
    def set_renderer_tr(tr): pass
    def set_chromium_download_host(url: str): pass

from i18n import Translator


def _parse_display_flags(text: str) -> tuple[str, bool, bool]:
    text, show_gid = (text[:-5].strip(), True) if text.endswith(" -gid") else (text, False)
    text, show_pid = (text[:-4].strip(), True) if text.endswith(" -pid") else (text, False)
    return text, show_gid, show_pid

RANK_LEVEL_MAP = {
    "conqueror_3": "🏆 征服者 III",
    "conqueror_2": "🏆 征服者 II",
    "conqueror_1": "🏆 征服者 I",
    "diamond_3": "💎 钻石 III",
    "diamond_2": "💎 钻石 II",
    "diamond_1": "💎 钻石 I",
    "platinum_3": "🥇 白金 III",
    "platinum_2": "🥇 白金 II",
    "platinum_1": "🥇 白金 I",
    "gold_3": "🥈 黄金 III",
    "gold_2": "🥈 黄金 II",
    "gold_1": "🥈 黄金 I",
    "silver_3": "🥉 白银 III",
    "silver_2": "🥉 白银 II",
    "silver_1": "🥉 白银 I",
    "bronze_3": "🟤 青铜 III",
    "bronze_2": "🟤 青铜 II",
    "bronze_1": "🟤 青铜 I",
    "unranked": "❓ 未定级",
}

COUNTRY_FLAGS = {
    "cn": "🇨🇳", "us": "🇺🇸", "gb": "🇬🇧", "de": "🇩🇪",
    "fr": "🇫🇷", "jp": "🇯🇵", "kr": "🇰🇷", "ru": "🇷🇺",
    "sg": "🇸🇬", "au": "🇦🇺", "ca": "🇨🇦", "nl": "🇳🇱",
}

LEADERBOARD_NAMES = {
    "rm_solo": "1v1 排位",
    "rm_team": "组队排位",
    "rm_2v2": "2v2 排位",
    "rm_3v3": "3v3 排位",
    "rm_4v4": "4v4 排位",
    "qm_1v1": "1v1 快速",
    "qm_2v2": "2v2 快速",
    "qm_3v3": "3v3 快速",
    "qm_4v4": "4v4 快速",
}

LEADERBOARD_KEYS = {
    "solo": "rm_solo", "1v1": "rm_solo",
    "team": "rm_team",
}

CIV_NAMES = {
    "english": "英格兰", "chinese": "中国", "french": "法兰西",
    "holy_roman_empire": "神圣罗马帝国", "mongols": "蒙古",
    "rus": "罗斯", "delhi_sultanate": "德里苏丹国",
    "abbasid_dynasty": "阿巴斯王朝", "ottomans": "奥斯曼",
    "malians": "马里", "byzantines": "拜占庭",
    "japanese": "日本", "ayyubids": "阿尤布",
    "jeanne_darc": "圣女贞德", "order_of_the_dragon": "龙骑士团",
    "zhu_xis_legacy": "朱熹遗产", "variant_french": "法国变体",
    "jin_dynasty": "金朝",
    "golden_horde": "金朝",
    "sengoku_daimyo": "战国大名",
    "knights_templar": "圣殿骑士团",
    "house_of_lancaster": "兰开斯特王朝",
    "macedonian_dynasty": "马其顿王朝",
    "tughlaq_dynasty": "图格鲁克王朝",
    "variant_hre": "神圣罗马帝国变体", "variant_abbasid": "阿巴斯变体",
    "variant_rus": "罗斯变体", "variant_chinese": "中国变体",
    "variant_delhi": "德里变体", "variant_mongols": "蒙古变体",
    "variant_ottomans": "奥斯曼变体", "variant_japanese": "日本变体",
    "variant_byzantines": "拜占庭变体",
}


def _format_rank(rank_level: str | None) -> str:
    if not rank_level:
        return "❓ 未定级"
    return RANK_LEVEL_MAP.get(rank_level, f"❓ {rank_level}")


def _use_civ_name(civ_id: str) -> str:
    return CIV_NAMES.get(civ_id, civ_id)


def _flag(country: str | None) -> str:
    return COUNTRY_FLAGS.get(country, "")


def _civ_name(civ_id: str) -> str:
    return CIV_NAMES.get(civ_id, civ_id)


def _elapsed(started_at: str | None) -> str:
    if not started_at:
        return "未知"
    from datetime import datetime, timezone
    try:
        t = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - t
        days = diff.days
        if days > 365:
            return f"{days // 365}年前"
        if days > 30:
            return f"{days // 30}个月前"
        if days > 0:
            return f"{days}天前"
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours}小时前"
        minutes = diff.seconds // 60
        return f"{minutes}分钟前"
    except Exception:
        return started_at


def _duration_str(seconds: int | None) -> str:
    if not seconds:
        return "0:00"
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def _civs_str_from_code(codes: list[str]) -> str:
    names = [CIV_CODE_TO_NAME.get(c, c) for c in codes]
    return ", ".join(names)


HELP_TEXT = (
    "🎮 AOE4 查询插件 v1.1.0\n"
    "━━━━━━━━━━━━━━━━\n"
    "📌 账号绑定\n"
    "  /aoe4 bind <游戏ID>      通过名字搜索绑定\n"
    "  /aoe4 bindid <ID>        通过Profile ID直接绑定\n"
    "  /aoe4 unbind              解绑账号\n"
    "  /aoe4 me                  查看绑定信息（加 -civ 文明胜率，-gid 最近GID）\n"
    "━━━━━━━━━━━━━━━━\n"
    "📊 战绩查询\n"
    "  /aoe4 profile [ID]  @/-id  查询玩家资料（加 -gid 显示最近GID）\n"
    "  /aoe4 recent [ID] [N] @/-id  最近对局记录（加 -gid/-pid 显示ID）\n"
    "  /aoe4 last [ID] @/-id      上一局详情（加 -n N 指定第N局）\n"
    "                       加 -score 评分图  -force 强制刷新  -gid/-pid 显示ID\n"
    "  /aoe4 compare <A> <B> @/-id  玩家对比\n"
    "  /aoe4 mecompare <A> @/-id  自己 vs 指定玩家\n"
    "━━━━━━━━━━━━━━━━\n"
    "🏆 天梯与搜索\n"
    "  /aoe4 leaderboard [模式]  排行榜（加 me 查自己排名）\n"
    "  /aoe4 search <关键词>     搜索玩家\n"
    "━━━━━━━━━━━━━━━━\n"
    "📖 游戏数据\n"
    "  /aoe4 unit <名称>        查询单位数据\n"
    "  /aoe4 building <名称>    查询建筑数据\n"
    "  /aoe4 tech <名称>        查询科技数据\n"
    "  /aoe4 civ [名称]         文明概览（不填列出所有）\n"
    "  /aoe4 counter <单位>     查询克制关系\n"
    "━━━━━━━━━━━━━━━━\n"
    "📰 版本信息\n"
    "  /aoe4 patch             查看最近版本更新\n"
    "  /aoe4 game <比赛ID>     通过ID查比赛详情\n"
    "                       加 -score 评分图  -force 强制刷新  -gid/-pid 显示ID\n"
    "  /aoe4 matchup [模式]     查询文明对战胜率表\n"
    "  /aoe4 checkfs            测试 FlareSolverr 连接\n"
    "━━━━━━━━━━━━━━━━\n"
    "💡 通用标志:  -gid 显示对局ID  -pid 显示Profile ID"
)

SUBCOMMAND_HELP = {
    "bind": (
        "📌 /aoe4 bind <游戏ID>\n"
        "通过游戏内昵称搜索并绑定账号。\n\n"
        "参数:\n"
        "  <游戏ID>  游戏内昵称（不区分大小写）\n\n"
        "说明:\n"
        "  匹配唯一玩家时直接绑定；\n"
        "  匹配多人时列出选项，使用 bindid 精确绑定。\n\n"
        "示例:\n"
        "  /aoe4 bind beasty\n"
        "  /aoe4 bind 小满"
    ),
    "bindid": (
        "📌 /aoe4 bindid <Profile ID>\n"
        "通过 Profile ID 直接绑定账号。\n\n"
        "参数:\n"
        "  <Profile ID>  玩家数字ID\n\n"
        "示例:\n"
        "  /aoe4 bindid 17594316"
    ),
    "unbind": (
        "📌 /aoe4 unbind\n"
        "解绑已绑定的游戏账号。\n\n"
        "说明:\n"
        "  无需参数，解绑你的 QQ 绑定的游戏账号。"
    ),
    "me": (
        "📌 /aoe4 me\n"
        "查看当前绑定的账号信息。\n\n"
        "说明:\n"
        "  显示绑定账号的详细排位数据。\n"
        "  加 -civ 查看最近文明胜率分布。\n\n"
        "示例:\n"
        "  /aoe4 me\n"
        "  /aoe4 me -civ"
    ),
    "profile": (
        "📊 /aoe4 profile [游戏ID]\n"
        "查询玩家综合资料。\n\n"
        "参数:\n"
        "  [游戏ID]  可选，不填则查询已绑定账号\n"
        "  支持 @用户 和 -id 标志（数字Profile ID）\n\n"
        "返回:\n"
        "  段位、分数、场次、胜率、连败/连胜\n\n"
        "示例:\n"
        "  /aoe4 profile\n"
        "  /aoe4 profile beasty\n"
        "  /aoe4 profile 17594316 -id\n"
        "  /aoe4 profile @用户"
    ),
    "recent": (
        "📊 /aoe4 recent [游戏ID] [数量]\n"
        "查询最近对局记录。\n\n"
        "参数:\n"
        "  [游戏ID]  可选，不填则查询已绑定账号\n"
        "  [数量]    可选，1~10，默认5\n"
        "  支持 @用户 和 -id 标志（数字Profile ID）\n\n"
        "返回:\n"
        "  地图、模式、时长、文明、得分变化、队友/对手\n\n"
        "示例:\n"
        "  /aoe4 recent\n"
        "  /aoe4 recent 10\n"
        "  /aoe4 recent beasty\n"
        "  /aoe4 recent beasty 5\n"
        "  /aoe4 recent 17594316 -id 10\n"
        "  /aoe4 recent @用户"
    ),
    "last": (
        "📊 /aoe4 last [游戏ID] [-score] [-n N] [-force]\n"
        "查询上一局（或指定第N局）详细数据。\n\n"
        "参数:\n"
        "  [游戏ID]  可选，不填则查询已绑定账号\n"
        "  支持 @用户 和 -id 标志（数字Profile ID）\n"
        "  -score    可选，显示所有玩家的详细评分对比\n"
        "  -n N      可选，指定第N局（1=最近一局），如 -n 3\n"
        "  -force    可选，强制刷新评分缓存\n\n"
        "返回:\n"
        "  基础信息 + 经济/军事/科技评分 + 双方阵容\n"
        "  +score 时额外显示: 评分、资源支出、击杀/阵亡/K/D、建筑、科技、APM\n\n"
        "示例:\n"
        "  /aoe4 last\n"
        "  /aoe4 last beasty\n"
        "  /aoe4 last -score\n"
        "  /aoe4 last -n 3\n"
        "  /aoe4 last beasty -score\n"
        "  /aoe4 last 17594316 -id -score\n"
        "  /aoe4 last @用户 -score\n"
        "  /aoe4 last beasty -score -force\n"
        "  /aoe4 last beasty -n 3 -score"
    ),
    "leaderboard": (
        "🏆 /aoe4 leaderboard [模式] [数量]\n"
        "查看天梯排行榜。\n\n"
        "参数:\n"
        "  [模式]  可选，默认 solo\n"
        "    solo/1v1  |  team\n"
        "  [数量]  可选，5~30，默认10\n\n"
        "特殊用法:\n"
        "  /aoe4 leaderboard me [模式]  查询自己的排名位置\n\n"
        "示例:\n"
        "  /aoe4 leaderboard\n"
        "  /aoe4 leaderboard team 10\n"
        "  /aoe4 leaderboard me\n"
        "  /aoe4 leaderboard me solo"
    ),
    "rank": (
        "🏆 /aoe4 rank [模式] [数量]\n"
        "与 leaderboard 相同，为排行榜别名。"
    ),
    "search": (
        "🏆 /aoe4 search <关键词>\n"
        "搜索玩家。\n\n"
        "参数:\n"
        "  <关键词>  至少3个字符\n\n"
        "返回:\n"
        "  玩家列表（含国家、ID、段位信息）\n\n"
        "示例:\n"
        "  /aoe4 search beasty"
    ),
    "civ": (
        "📖 /aoe4 civ [文明名]\n"
        "查询文明概览。\n\n"
        "参数:\n"
        "  [文明名]  可选，不填列出所有文明\n\n"
        "支持的中文名:\n"
        "  英格兰 | 中国 | 法兰西 | 神圣罗马帝国\n"
        "  蒙古 | 罗斯 | 德里苏丹国 | 阿巴斯王朝\n"
        "  奥斯曼 | 马里 | 拜占庭 | 日本\n"
        "  阿尤布 | 圣女贞德 | 龙骑士团 | 朱熹遗产\n\n"
        "示例:\n"
        "  /aoe4 civ\n"
        "  /aoe4 civ 中国\n"
        "  /aoe4 civ 英格兰"
    ),
    "unit": (
        "📖 /aoe4 unit <单位名>\n"
        "查询单位详细数据。\n\n"
        "参数:\n"
        "  <单位名>  单位名称（支持中/英文/关键词）\n\n"
        "返回:\n"
        "  生命值、造价、伤害、护甲、速度等\n\n"
        "示例:\n"
        "  /aoe4 unit man at arms\n"
        "  /aoe4 unit 武士"
    ),
    "building": (
        "📖 /aoe4 building <建筑名>\n"
        "查询建筑详细数据。\n\n"
        "参数:\n"
        "  <建筑名>  建筑名称（支持中/英文/关键词）\n\n"
        "返回:\n"
        "  生命值、造价、护甲、驻军等\n\n"
        "示例:\n"
        "  /aoe4 building barracks\n"
        "  /aoe4 building 哨塔"
    ),
    "tech": (
        "📖 /aoe4 tech <科技名>\n"
        "查询科技数据。\n\n"
        "参数:\n"
        "  <科技名>  科技名称（支持中/英文/关键词）\n\n"
        "返回:\n"
        "  效果描述、造价、研发建筑等\n\n"
        "示例:\n"
        "  /aoe4 tech bloomery\n"
        "  /aoe4 tech 生物科技"
    ),
    "technology": (
        "📖 /aoe4 technology <科技名>\n"
        "同 /aoe4 tech。"
    ),
    "patch": (
        "📰 /aoe4 patch\n"
        "查看帝国时代4最近的版本更新内容。\n\n"
        "说明:\n"
        "  无需参数，显示最近5个版本更新的日期、标题、简要说明和原文链接。\n"
        "  数据来源: ageofempires.com 官方网站 RSS"
    ),
    "counter": (
        "⚔️ /aoe4 counter <单位名>\n"
        "查询单位的克制关系。\n\n"
        "参数:\n"
        "  <单位名>  单位名称（支持中/英文/关键词）\n\n"
        "返回:\n"
        "  该单位克制哪些类型（额外伤害）\n"
        "  被哪些单位克制\n"
        "  单位描述中的克制提示\n\n"
        "示例:\n"
        "  /aoe4 counter spearman\n"
        "  /aoe4 counter 武士"
    ),
    "compare": (
        "📊 /aoe4 compare <玩家A> <玩家B>\n"
        "对比两名玩家的实力。\n\n"
        "参数:\n"
        "  <玩家A>  第一位玩家的游戏ID\n"
        "  <玩家B>  第二位玩家的游戏ID\n"
        "  支持 @用户 和 -id 标志（数字Profile ID）\n\n"
        "对比维度:\n"
        "  ① 各模式分数对比（solo / team）\n"
        "  ② 段位对比\n"
        "  ③ 胜率对比\n"
        "  ④ 总场次对比\n"
        "  ⑤ 连胜/连败对比\n"
        "  ⑥ 历史最高分\n"
        "  ⑧ 综合能力分析（经济/军事/科技）\n\n"
        "示例:\n"
        "  /aoe4 compare beasty marinelord\n"
        "  /aoe4 compare 12345 67890 -id\n"
        "  /aoe4 compare beasty @用户"
    ),
    "mecompare": (
        "📊 /aoe4 mecompare <玩家A>\n"
        "将你自己（已绑定账号）与指定玩家进行对比。\n\n"
        "参数:\n"
        "  <玩家A>  要对比的玩家游戏ID\n"
        "  支持 @用户 和 -id 标志（数字Profile ID）\n\n"
        "说明:\n"
        "  需先绑定账号。对比维度与 /aoe4 compare 相同。\n\n"
        "示例:\n"
        "  /aoe4 mecompare beasty\n"
        "  /aoe4 mecompare 17594316 -id\n"
        "  /aoe4 mecompare @用户"
    ),
    "game": (
        "📊 /aoe4 game <比赛ID> [-score] [-force]\n"
        "通过比赛ID查询对局数据。\n\n"
        "参数:\n"
        "  <比赛ID>   数字比赛ID（如 234460841）\n"
        "  -score     可选，显示所有玩家的详细评分对比\n"
        "  -force     可选，强制刷新评分缓存\n\n"
        "返回:\n"
        "  对局基础信息（地图、模式、时长等）+ 双方阵容\n"
        "  +score 时额外显示: 评分、资源支出、击杀/K/D、建筑、科技、APM\n\n"
        "示例:\n"
        "  /aoe4 game 234460841\n"
        "  /aoe4 game 234460841 -score\n"
        "  /aoe4 game 234460841 -score -force"
    ),
    "matchup": (
        "📊 /aoe4 matchup [模式]\n"
        "查询各文明之间的对战胜率表，以二维矩阵形式展示。\n\n"
        "参数:\n"
        "  排位:     solo / 1v1 / 2v2 / 3v3 / 4v4 / team（默认 solo）\n"
        "  快速:     qm / quick / qm_1v1 / qm_2v2 / qm_3v3 / qm_4v4\n\n"
        "说明:\n"
        "  行文明 vs 列文明的胜率百分比。绿色=有利，红色=不利。\n"
        "  需要 Playwright 渲染图片，否则以文字表格回退。\n\n"
        "示例:\n"
        "  /aoe4 matchup\n"
        "  /aoe4 matchup 2v2\n"
        "  /aoe4 matchup qm_1v1"
    ),
}


class AstrBotAOE4Plugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}
        self.tr = Translator(self.config.get("language", "zh-CN"))
        self._init_renderer()
        if HAS_RENDERER:
            set_renderer_tr(self.tr)
        self.client = AoE4WorldClient(
            flaresolverr_host=self.config.get("flaresolverr_host", "localhost"),
            flaresolverr_port=self.config.get("flaresolverr_port", 8191),
            flaresolverr_mode=self.config.get("flaresolverr_mode", "once"),
            summary_cache_ttl=self.config.get("summary_cache_ttl", 120),
            timeout_default=self.config.get("api_timeout_default", 15),
            timeout_leaderboard=self.config.get("api_timeout_leaderboard", 30),
        )
        chrom_host = self.config.get("chromium_download_host", "")
        if chrom_host:
            set_chromium_download_host(chrom_host)
        self.data = AoE4DataClient(
            translator=self.tr,
            cache_ttl=self.config.get("data_cache_ttl", 86400),
        )
        self._myciv_games = max(2, min(50, self.config.get("myciv_analysis_games", 5)))
        logger.info(self.tr.t("plugin_loaded"))
        if HAS_RENDERER:
            asyncio.create_task(self._ensure_renderer_ready())

    def _init_renderer(self):
        global HAS_RENDERER
        if HAS_RENDERER:
            return
        import subprocess
        pypi_mirror = self.config.get("pypi_mirror", "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple")
        pip_arg = f"-i {pypi_mirror}" if pypi_mirror else ""
        logger.warning("playwright 未安装，尝试自动安装（跳过依赖检查）...")
        try:
            cmd = [sys.executable, "-m", "pip", "install", "playwright==1.48.0", "--no-deps", "-q"]
            if pip_arg:
                cmd.append(pip_arg)
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            playwright_ok = result.returncode == 0
            deps_ok = False
            if playwright_ok:
                deps_cmd = [sys.executable, "-m", "pip", "install", "pyee", "greenlet", "-q"]
                if pip_arg:
                    deps_cmd.append(pip_arg)
                deps = subprocess.run(deps_cmd, capture_output=True, timeout=120)
                deps_ok = deps.returncode == 0
            if playwright_ok and deps_ok:
                logger.info("playwright 及核心依赖安装成功，重新加载渲染模块...")
                import importlib
                mod = importlib.import_module("score_renderer")
                globals().update(
                    generate_score_html=mod.generate_score_html,
                    generate_analysis_html=mod.generate_analysis_html,
                    generate_matchup_html=mod.generate_matchup_html,
                    render_html_to_image=mod.render_html_to_image,
                    close_renderer=mod.close_browser,
                    set_renderer_tr=mod.set_translator,
                    ensure_browser=mod.ensure_browser,
                    set_chromium_download_host=mod.set_chromium_download_host,
                )
                HAS_RENDERER = True
            else:
                if not playwright_ok:
                    detail = result.stderr.decode(errors="ignore")[:200] if result.stderr else ""
                    logger.warning(f"playwright 安装失败: {detail}")
                if playwright_ok and not deps_ok:
                    detail = deps.stderr.decode(errors="ignore")[:200] if deps.stderr else ""
                    logger.warning(f"核心依赖 (pyee, greenlet) 安装失败: {detail}")
        except Exception as e:
            logger.warning(f"playwright 自动安装异常: {e}")

    async def _ensure_renderer_ready(self):
        try:
            ok = await ensure_browser()
            if ok:
                logger.info("渲染引擎已提前就绪")
            else:
                logger.warning("渲染引擎初始化失败，将在使用时重试")
        except Exception as e:
            logger.warning(f"渲染引擎初始化异常: {e}")

    def _forward_result(self, event: AstrMessageEvent, text: str, threshold: int = 10):
        if text.count("\n") + 1 > threshold:
            return event.chain_result(
                [Nodes(nodes=[Node(name="AOE4 Bot", uin="0", content=[Plain(text)])])]
            )
        return event.plain_result(text)

    def _civ_name(self, civ_id: str) -> str:
        if not civ_id:
            return ""
        result = self.tr.civ(civ_id)
        if result != civ_id:
            return result
        result2 = self.tr.civ(civ_id.lower())
        if result2 != civ_id.lower():
            return result2
        code = CIV_NAME_TO_CODE.get(civ_id.lower())
        if code:
            return self.tr.civ(code)
        return civ_id

    def _fmt_rank(self, rank_level: str | None) -> str:
        if not rank_level:
            return "❓ " + (self.tr.rank_level("unranked") if self.tr else "未定级")
        level = self.tr.rank_level(rank_level)
        return level if level != rank_level else f"❓ {rank_level}"

    def _mode_name(self, mode_key: str) -> str:
        return self.tr.leaderboard_mode(mode_key)

    @filter.command("aoe4")
    async def aoe4_router(self, event: AstrMessageEvent):
        content = event.message_str.strip()
        parts = content.split()
        raw_sub = parts[1].lower() if len(parts) >= 2 else ""
        is_help_request = len(parts) >= 3 and parts[2].lower() in ("-help", "-h", "--help")
        sub = raw_sub.removesuffix("-help") if raw_sub.endswith("-help") else raw_sub

        if not sub or sub in ("help", "-h", "--help"):
            yield self._forward_result(event, self._build_help_text())
            return

        if is_help_request or raw_sub.endswith("-help") and raw_sub != sub:
            help_text = SUBCOMMAND_HELP.get(sub)
            if help_text:
                yield self._forward_result(event, help_text)
            else:
                yield event.plain_result(self.tr.t("err_not_found_cmd", sub=sub))
            return

        method_map = {
            "bind": self._handle_bind,
            "bindid": self._handle_bindid,
            "unbind": self._handle_unbind,
            "me": self._handle_me,
            "profile": self._handle_profile,
            "recent": self._handle_recent,
            "last": self._handle_last,
            "leaderboard": self._handle_leaderboard,
            "rank": self._handle_leaderboard,
            "search": self._handle_search,
            "civ": self._handle_civ,
            "unit": self._handle_unit,
            "building": self._handle_building,
            "tech": self._handle_tech,
            "technology": self._handle_tech,
            "patch": self._handle_patch,
            "counter": self._handle_counter,
            "compare": self._handle_compare,
            "mecompare": self._handle_mecompare,
            "game": self._handle_game,
            "matchup": self._handle_matchup,
            "checkfs": self._handle_checkfs,
        }

        handler = method_map.get(sub)
        if not handler:
            yield event.plain_result(
                f"未知指令: /aoe4 {sub}\n"
                f"使用 /aoe4 查看可用指令列表"
            )
            return

        async for result in handler(event):
            yield result

    async def _resolve_player(self, sender_id: str, name: str | None, at_comps: list[At] | None = None, use_id: bool = False):
        if name == "@" and at_comps:
            if not at_comps:
                return None, "未找到被 @ 的用户"
            at = at_comps.pop(0)
            user_id = str(at.qq)
            bound = storage.get_bound(user_id)
            if not bound:
                return None, f"被 @ 的用户 ({at.name or at.qq}) 未绑定游戏账号"
            player = await self.client.get_player(bound["profile_id"])
            if not player:
                return None, "被 @ 的用户绑定的账号数据查询失败"
            return player, None
        if use_id and name:
            try:
                pid = int(name)
            except ValueError:
                return None, f"Profile ID 必须是数字: {name}"
            player = await self.client.get_player(pid)
            if not player:
                return None, f"未找到 Profile ID 为 {pid} 的玩家"
            return player, None
        if name:
            players = await self.client.search_player(name)
            if not players:
                return None, f"未找到玩家「{name}」，请检查拼写"
            return players[0], None
        bound = storage.get_bound(sender_id)
        if not bound:
            return None, "你还没有绑定游戏账号，请使用 /aoe4 bind <游戏ID> 绑定"
        player = await self.client.get_player(bound["profile_id"])
        if not player:
            return None, "你绑定的账号数据查询失败"
        return player, None

# ─── 账号绑定 ─────────────────────────────────

    async def _handle_bind(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result(
                "用法:\n"
                "  /aoe4 bind <游戏ID>    通过名字搜索绑定\n"
                "  /aoe4 bindid <ID>      通过Profile ID直接绑定"
            )
            return
        name = parts[2]
        players = await self.client.search_player(name)
        if not players:
            yield event.plain_result(f"未找到玩家「{name}」，请检查拼写")
            return
        if len(players) == 1:
            target = players[0]
            tag = target.get("name", name)
            pid = target["profile_id"]
            sender_id = event.get_sender_id()
            storage.bind(sender_id, pid, tag)
            country = _flag(target.get("country", ""))
            yield event.plain_result(
                f"✅ 绑定成功！{country}{tag}\n"
                f"Profile ID: {pid}\n"
                f"可使用 /aoe4 me 查看详情"
            )
            return
        lines = [f"找到多个「{name}」，请使用 Profile ID 精确绑定:"]
        for p in players[:8]:
            pid = p["profile_id"]
            tag = p.get("name", "?")
            country = _flag(p.get("country", ""))
            lines.append(f"  {country}{tag}  (ID: {pid})")
        lines.append("")
        lines.append("使用 /aoe4 bindid <Profile ID> 绑定")
        yield event.plain_result("\n".join(lines))

    async def _handle_bindid(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("用法: /aoe4 bindid <Profile ID>")
            return
        try:
            pid = int(parts[2])
        except ValueError:
            yield event.plain_result("Profile ID 必须是数字")
            return
        player = await self.client.get_player(pid)
        if not player:
            yield event.plain_result(f"未找到 Profile ID 为 {pid} 的玩家")
            return
        tag = player.get("name", str(pid))
        sender_id = event.get_sender_id()
        storage.bind(sender_id, pid, tag)
        country = _flag(player.get("country", ""))
        yield event.plain_result(
            f"✅ 绑定成功！{country}{tag}\n"
            f"Profile ID: {pid}\n"
            f"可使用 /aoe4 me 查看详情"
        )

    async def _handle_unbind(self, event: AstrMessageEvent):
        sender_id = event.get_sender_id()
        if storage.unbind(sender_id):
            yield event.plain_result("✅ 已成功解绑")
        else:
            yield event.plain_result("你还没有绑定账号")

    async def _handle_me(self, event: AstrMessageEvent):
        text = event.message_str.strip()
        text, show_gid, _ = _parse_display_flags(text)
        use_civ = text.endswith(" -civ") or text.endswith(" --civ")
        if use_civ:
            text = text.rsplit(" -civ", 1)[0].rsplit(" --civ", 1)[0].strip()
        sender_id = event.get_sender_id()
        bound = storage.get_bound(sender_id)
        if not bound:
            yield event.plain_result("你还没有绑定游戏账号，请使用 /aoe4 bind <游戏ID> 绑定")
            return
        pid = bound["profile_id"]

        if use_civ:
            games = await self.client.get_player_games(pid, self._myciv_games)
            if not games:
                yield event.plain_result("最近没有对局数据，无法分析文明胜率")
                return
            civ_stats: dict[str, dict] = {}
            for g in games:
                for team in g.get("teams", []):
                    for p in team:
                        pd = p.get("player", p)
                        if pd.get("profile_id") == pid:
                            civ_key = pd.get("civilization", "unknown")
                            result = pd.get("result", "unknown")
                            rd = pd.get("rating_diff", 0)
                            if civ_key not in civ_stats:
                                civ_stats[civ_key] = {"wins": 0, "games": 0, "total_rd": 0}
                            civ_stats[civ_key]["games"] += 1
                            if result == "win":
                                civ_stats[civ_key]["wins"] += 1
                            civ_stats[civ_key]["total_rd"] += rd or 0
                            break
            if not civ_stats:
                yield event.plain_result("最近对局中未找到你的数据")
                return
            sorted_civs = sorted(civ_stats.items(), key=lambda x: -x[1]["games"])
            lines = [f"📊 {bound['player_name']} 最近 {self._myciv_games} 场文明胜率"]
            lines.append("")
            for civ_key, stats in sorted_civs:
                civ_name = self._civ_name(civ_key)
                wr = stats["wins"] / stats["games"] * 100 if stats["games"] else 0
                avg_rd = stats["total_rd"] / stats["games"] if stats["games"] else 0
                bar_len = max(1, int(wr / 10))
                bar = "█" * bar_len + "░" * (10 - bar_len)
                rd_str = f" | 均分差 {avg_rd:+.1f}" if avg_rd != 0 else ""
                lines.append(
                    f"  {civ_name}\n"
                    f"    {bar} {stats['wins']}/{stats['games']} "
                    f"({wr:.0f}%){rd_str}"
                )
            yield self._forward_result(event, "\n".join(lines))
            return

        player = await self.client.get_player(pid)
        if not player:
            yield event.plain_result(
                f"绑定的账号: {bound['player_name']} (ID: {pid})\n"
                "数据查询失败，请稍后重试"
            )
            return
        lines = await self._format_profile(player)
        if show_gid:
            gid_lines = await self._append_recent_gids(player["profile_id"])
            lines.extend(gid_lines)
        yield self._forward_result(event, "\n".join(lines))

# ─── 玩家资料 ─────────────────────────────────

    async def _handle_profile(self, event: AstrMessageEvent):
        text = event.message_str.strip()
        text, show_gid, _ = _parse_display_flags(text)
        use_id = text.endswith(" -id") or text.endswith(" --id")
        if use_id:
            text = text.rsplit(" -id", 1)[0].rsplit(" --id", 1)[0].strip()
        at_comps = self._get_at_mentions(event)
        parts = text.split(maxsplit=2)
        raw_name = parts[2] if len(parts) >= 3 else None
        if raw_name and raw_name.startswith("@") and at_comps:
            raw_name = "@"
        sender_id = event.get_sender_id()
        player, err = await self._resolve_player(sender_id, raw_name, at_comps, use_id)
        if err:
            yield event.plain_result(err)
            return
        lines = await self._format_profile(player)
        if show_gid:
            gid_lines = await self._append_recent_gids(player["profile_id"])
            lines.extend(gid_lines)
        yield self._forward_result(event, "\n".join(lines))

    async def _format_profile(self, player: dict) -> list[str]:
        name = player["name"]
        pid = player["profile_id"]
        country = _flag(player.get("country", ""))
        lines = [f"📋 {country}{name}  |  ID: {pid}"]
        lines.append("")
        modes = player.get("modes", {})
        if not modes:
            lines.append("暂无排位数据")
            return lines
        ordered = ["rm_solo", "rm_2v2", "rm_3v3", "rm_4v4", "rm_team",
                    "qm_1v1", "qm_2v2", "qm_3v3", "qm_4v4"]
        added = 0
        for key in ordered:
            mode = modes.get(key)
            if not mode:
                continue
            label = self._mode_name(key)
            rating = mode.get("rating")
            rank_level = mode.get("rank_level")
            games = mode.get("games_count", 0)
            wins = mode.get("wins_count", 0)
            losses = mode.get("losses_count", 0)
            win_rate = mode.get("win_rate", 0)
            streak = mode.get("streak", 0)
            rank_display = self._fmt_rank(rank_level)
            rating_str = f"{rating}" if rating else "N/A"
            streak_str = f"🔥 {streak}" if streak and streak > 0 else (
                f"💧 {abs(streak)}" if streak and streak < 0 else "")
            lines.append(
                f"▸ {label}  |  {rank_display}\n"
                f"  分数: {rating_str}  |  场次: {games}  "
                f"胜: {wins} 负: {losses}  "
                f"胜率: {win_rate}%{f'  {streak_str}' if streak_str else ''}"
            )
            added += 1
        if not added:
            lines.append("暂无排位数据")
        return lines

# ─── 最近对局 ─────────────────────────────────

    async def _handle_recent(self, event: AstrMessageEvent):
        text = event.message_str.strip()
        use_id = " -id " in text or text.endswith(" -id") or text.endswith(" --id")
        text, show_gid, show_pid = _parse_display_flags(text)
        if use_id:
            text = text.replace(" -id ", " ").replace(" --id ", " ").strip()
            text = text.removesuffix(" -id").removesuffix(" --id").strip()
        at_comps = self._get_at_mentions(event)
        parts = text.split()
        raw_args = parts[2:] if len(parts) >= 2 else []

        player_spec = None
        limit = 5
        for arg in raw_args:
            if arg.startswith("@") and at_comps:
                player_spec = "@"
                continue
            if use_id:
                if player_spec is None:
                    player_spec = arg
                else:
                    try:
                        limit = max(1, min(10, int(arg)))
                    except ValueError:
                        pass
            else:
                if player_spec is None:
                    try:
                        limit = max(1, min(10, int(arg)))
                    except ValueError:
                        player_spec = arg
                else:
                    try:
                        limit = max(1, min(10, int(arg)))
                    except ValueError:
                        pass

        if player_spec is None and at_comps:
            player_spec = "@"

        sender_id = event.get_sender_id()
        player, err = await self._resolve_player(sender_id, player_spec, at_comps, use_id)
        if err:
            yield event.plain_result(err)
            return

        pid = player["profile_id"]
        player_name = player.get("name", str(pid))
        games = await self.client.get_player_games(pid, limit)
        if not games:
            yield event.plain_result(f"{player_name} 最近没有对局记录")
            return
        lines = [f"🎮 {player_name} 最近 {len(games)} 场对局"]
        for i, g in enumerate(games, 1):
            map_name = g.get("map", "未知地图")
            kind = self._mode_name(g.get("kind", ""))
            dur = _duration_str(g.get("duration", 0))
            time_ago = _elapsed(g.get("started_at", ""))
            game_id = g.get("game_id")
            id_suffix = self._build_id_suffix(show_gid, show_pid, game_id, pid)
            my_team = None
            my_team_data = None
            for team in g.get("teams", []):
                for p in team:
                    if p["player"]["profile_id"] == pid:
                        my_team_data = p["player"]
                        my_team = team
                        break
                if my_team is not None:
                    break
            if my_team_data:
                result = my_team_data.get("result", "unknown")
                civ = self._civ_name(my_team_data.get("civilization", ""))
                rd = my_team_data.get("rating_diff")
                rd_str = f" ({rd:+.0f})" if rd is not None else ""
                result_icon = "✅" if result == "win" else "❌"
                teams = g.get("teams", [])
                my_team_idx = None
                for idx, team in enumerate(teams):
                    for p in team:
                        if p["player"]["profile_id"] == pid:
                            my_team_idx = idx
                            break
                    if my_team_idx is not None:
                        break
                teammates = []
                opponents = []
                for idx, team in enumerate(teams):
                    for p in team:
                        pd = p["player"]
                        n = f"{_flag(pd.get('country',''))}{pd.get('name','?')}"
                        civ_label = self._civ_name(pd.get("civilization", ""))
                        pid_suffix = f" [PID:{pd['profile_id']}]" if show_pid and pd.get('profile_id') else ""
                        entry = f"{n}({civ_label}){pid_suffix}"
                        if pd["profile_id"] == pid:
                            continue
                        if idx == my_team_idx:
                            teammates.append(entry)
                        else:
                            opponents.append(entry)
                lines.append(
                    f"{i}. {result_icon} {kind} | {map_name} | {dur}{id_suffix}\n"
                    f"   🏛 {civ} {rd_str}  |  {time_ago}"
                )
                if teammates:
                    lines.append(f"   队友: {', '.join(teammates)}")
                if opponents:
                    lines.append(f"   对手: {', '.join(opponents)}")
            else:
                lines.append(f"{i}. {map_name} {kind} - 无法获取详细数据")
        yield self._forward_result(event, "\n".join(lines))

# ─── 上一局详情 ──────────────────────────────

    async def _handle_last(self, event: AstrMessageEvent):
        text = event.message_str.strip()
        text, show_gid, show_pid = _parse_display_flags(text)
        use_score = text.endswith(" -score") or text.endswith(" --score")
        if use_score:
            text = text.rsplit(" -score", 1)[0].rsplit(" --score", 1)[0].strip()
        use_id = text.endswith(" -id") or text.endswith(" --id")
        if use_id:
            text = text.rsplit(" -id", 1)[0].rsplit(" --id", 1)[0].strip()
        use_force = text.endswith(" -force") or text.endswith(" --force")
        if use_force:
            text = text.rsplit(" -force", 1)[0].rsplit(" --force", 1)[0].strip()
        import re as _re
        m = _re.search(r'\s+-n(\d+)$', text)
        if not m:
            m = _re.search(r'\s+-n\s+(\d+)\s*$', text)
        game_index = 1
        if m:
            game_index = max(1, int(m.group(1)))
            text = text[:m.start()].strip()
        at_comps = self._get_at_mentions(event)
        parts = text.split(maxsplit=2)
        raw_name = parts[2] if len(parts) >= 3 else None
        if raw_name and raw_name.startswith("@") and at_comps:
            raw_name = "@"
        sender_id = event.get_sender_id()
        player, err = await self._resolve_player(sender_id, raw_name, at_comps, use_id)
        if err:
            yield event.plain_result(err)
            return
        pid = player["profile_id"]

        if game_index > 1:
            games = await self.client.get_player_games(pid, game_index)
            if not games or len(games) < game_index:
                yield event.plain_result(f"未找到第 {game_index} 局对局数据（最近只有 {len(games) if games else 0} 局）")
                return
            game = games[-1]
            game = await self.client.get_game_by_id(game["game_id"])
            if not game:
                yield event.plain_result(f"第 {game_index} 局详情获取失败")
                return
        else:
            game = await self.client.get_player_last_game(pid, include_stats=True)
            if not game:
                yield event.plain_result("未找到上一局对局数据")
                return

        game_id = game.get("game_id")
        map_name = game.get("map", "未知地图")
        kind = self._mode_name(game.get("kind", ""))
        dur = _duration_str(game.get("duration", 0))
        time_ago = _elapsed(game.get("started_at", ""))
        id_suffix = self._build_id_suffix(show_gid, show_pid, game_id, pid)

        if use_score:
            summary = await self.client.get_game_summary_by_id(game_id, profile_id=pid, force=use_force)
            if summary and summary.get("players"):
                img_result = await self._render_score_image(event, summary["players"], map_name, kind, dur, time_ago)
                if img_result:
                    yield img_result
                    return
                score_lines = self._format_score_comparison(summary["players"], map_name, kind, dur, time_ago)
                yield self._forward_result(event, "\n".join(score_lines))
            else:
                yield self._forward_result(event, self._format_game_fallback(game, map_name, kind, dur, time_ago, id_suffix))
            return

        my_data = None
        for team in game.get("teams", []):
            for p in team:
                if p["profile_id"] == pid:
                    my_data = p
                    break
            if my_data:
                break
        if not my_data:
            yield event.plain_result("无法获取本局你的数据")
            return
        result = my_data.get("result", "unknown")
        civ = self._civ_name(my_data.get("civilization", ""))
        rd = my_data.get("rating_diff")
        rd_str = f" ({rd:+.0f})" if rd is not None else ""
        result_icon = "✅" if result == "win" else "❌"
        teams_strs = []
        for ti, team in enumerate(game.get("teams", [])):
            members = []
            for p in team:
                name = p.get("name", "?")
                flag = _flag(p.get("country", ""))
                civ_name = self._civ_name(p.get("civilization", ""))
                members.append(f"{flag}{name}({civ_name})")
            teams_strs.append(f"  队伍{ti + 1}: {', '.join(members)}")
        player_stats = None
        if "stats" in game:
            for s in game.get("stats", []):
                if s.get("profile_id") == pid:
                    player_stats = s
                    break
        lines = [
            f"🎮 上一局 | {result_icon} {result.upper()}{id_suffix}\n"
            f"  {kind} | {map_name} | {dur} | {time_ago}",
            f"  🏛 {civ} {rd_str}",
        ]
        if player_stats:
            eco = player_stats.get("economy_score", 0)
            mil = player_stats.get("military_score", 0)
            tech = player_stats.get("technology_score", 0)
            lines.append(f"  📊 经济: {eco}  军事: {mil}  科技: {tech}")
        lines.append("")
        lines.extend(teams_strs)
        yield self._forward_result(event, "\n".join(lines))

    @staticmethod
    def _format_score_comparison(players: list[dict], map_name: str, kind: str, dur: str, time_ago: str) -> list[str]:
        def fmt(val):
            if val is None:
                return "N/A"
            if isinstance(val, float):
                return f"{val:.2f}"
            if isinstance(val, int):
                return f"{val:,}"
            return str(val)

        def fmt_kd(kills, deaths):
            if deaths:
                return f"{kills / deaths:.2f}"
            if kills:
                return "∞"
            return "N/A"

        rows = []

        rows.append(("🏆 总评", [fmt(p.get("scores", {}).get("total", 0)) for p in players]))
        rows.append(("  军事", [fmt(p.get("scores", {}).get("military", 0)) for p in players]))
        rows.append(("  经济", [fmt(p.get("scores", {}).get("economy", 0)) for p in players]))
        rows.append(("  科技", [fmt(p.get("scores", {}).get("technology", 0)) for p in players]))
        rows.append(("  社会", [fmt(p.get("scores", {}).get("society", 0)) for p in players]))

        rows.append(("💰 资源", [fmt(p.get("totalResourcesSpent", {}).get("total", 0)) for p in players]))
        rows.append(("  食物", [fmt(p.get("totalResourcesSpent", {}).get("food", 0)) for p in players]))
        rows.append(("  木材", [fmt(p.get("totalResourcesSpent", {}).get("wood", 0)) for p in players]))
        rows.append(("  黄金", [fmt(p.get("totalResourcesSpent", {}).get("gold", 0)) for p in players]))
        rows.append(("  石头", [fmt(p.get("totalResourcesSpent", {}).get("stone", 0)) for p in players]))
        has_olive = any(p.get("totalResourcesSpent", {}).get("oliveoil", 0) for p in players)
        if has_olive:
            rows.append(("  橄榄油", [fmt(p.get("totalResourcesSpent", {}).get("oliveoil", 0)) for p in players]))

        rows.append(("⚔️ 击杀", [fmt(p.get("_stats", {}).get("ekills", 0)) for p in players]))
        rows.append(("  阵亡", [fmt(p.get("_stats", {}).get("edeaths", 0)) for p in players]))
        kd_vals = []
        for p in players:
            s = p.get("_stats", {})
            kd_vals.append(fmt_kd(s.get("ekills", 0), s.get("edeaths", 0)))
        rows.append(("  K/D", kd_vals))
        rows.append(("  摧毁", [fmt(p.get("_stats", {}).get("structdmg", 0)) for p in players]))

        rows.append(("🏗 生产", [fmt(p.get("_stats", {}).get("sqprod", 0)) for p in players]))
        rows.append(("  建筑", [fmt(p.get("_stats", {}).get("bprod", 0)) for p in players]))
        rows.append(("🔬 科技", [fmt(p.get("_stats", {}).get("upg", 0)) for p in players]))
        rows.append(("⚡ APM", [fmt(p.get("apm")) for p in players]))

        label_w = max(len(r[0]) for r in rows)
        name_widths = []
        for i, p in enumerate(players):
            name_w = len(p.get("name", "?"))
            vals_w = max(len(r[1][i]) for r in rows)
            name_widths.append(max(name_w, vals_w) + 2)

        lines = [
            f"🎮 上一局 | {kind} | {map_name} | {dur} | {time_ago}",
            "📊 评分 Comparison",
        ]

        hdr = f"  {'指标':>{label_w}}"
        for i, p in enumerate(players):
            hdr += f"  {p.get('name', '?'):>{name_widths[i]}}"
        lines.append(hdr)
        sep_w = label_w + 3 + sum(name_widths) + len(name_widths) - 1
        lines.append(f"  {'─' * sep_w}")

        for label, vals in rows:
            row = f"  {label:>{label_w}}"
            for i, v in enumerate(vals):
                row += f"  {v:>{name_widths[i]}}"
            lines.append(row)

        return lines

    async def _render_score_image(self, event: AstrMessageEvent, players: list[dict], map_name: str, kind: str, dur: str, time_ago: str):
        if not HAS_RENDERER:
            return None
        try:
            title = f"🎮 {kind} | {map_name} | {dur}"
            subtitle = f"⏱ {time_ago}"
            cache_dir = os.path.join(tempfile.gettempdir(), "aoe4_score_cache")
            os.makedirs(cache_dir, exist_ok=True)

            html = generate_score_html(players, title, subtitle)
            img_path = os.path.join(cache_dir, f"score_{uuid.uuid4().hex}.jpg")
            ok = await render_html_to_image(html, img_path)
            if not ok or not os.path.exists(img_path):
                return None

            analysis_html = generate_analysis_html(players, title, subtitle)
            analysis_path = os.path.join(cache_dir, f"analysis_{uuid.uuid4().hex}.jpg")
            analysis_ok = await render_html_to_image(analysis_html, analysis_path, width=540)
            if analysis_ok and os.path.exists(analysis_path):
                chain = [Image(file=img_path), Image(file=analysis_path)]
            else:
                chain = [Image(file=img_path)]

            logger.info(f"评分图片已生成: {img_path}, 分析图片: {analysis_ok}")
            return event.chain_result(chain)
        except Exception as e:
            logger.error(f"评分图片渲染失败: {e}")
            return None

# ─── 按比赛ID查询 ────────────────────────────

    async def _handle_game(self, event: AstrMessageEvent):
        text = event.message_str.strip()
        text, show_gid, show_pid = _parse_display_flags(text)
        use_score = text.endswith(" -score") or text.endswith(" --score")
        if use_score:
            text = text.rsplit(" -score", 1)[0].rsplit(" --score", 1)[0].strip()
        use_force = text.endswith(" -force") or text.endswith(" --force")
        if use_force:
            text = text.rsplit(" -force", 1)[0].rsplit(" --force", 1)[0].strip()
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("用法: /aoe4 game <比赛ID> [-score] [-gid] [-pid]")
            return
        try:
            game_id = int(parts[2])
        except ValueError:
            yield event.plain_result("比赛ID必须是数字")
            return
        game = await self.client.get_game_by_id(game_id)
        if not game:
            yield event.plain_result(f"未找到比赛 {game_id}")
            return
        map_name = game.get("map", "未知地图")
        kind = self._mode_name(game.get("kind", ""))
        dur = _duration_str(game.get("duration"))
        time_ago = _elapsed(game.get("started_at", ""))

        if use_score:
            any_pid = None
            for team in game.get("teams", []):
                for p in team:
                    if "profile_id" in p:
                        any_pid = p["profile_id"]
                        break
                if any_pid is not None:
                    break
            summary = await self.client.get_game_summary_by_id(game_id, profile_id=any_pid, force=use_force)
            if summary and summary.get("players"):
                img_result = await self._render_score_image(event, summary["players"], map_name, kind, dur, time_ago)
                if img_result:
                    yield img_result
                    return
                score_lines = self._format_score_comparison(summary["players"], map_name, kind, dur, time_ago)
                yield self._forward_result(event, "\n".join(score_lines))
            else:
                fallback = self._format_game_fallback(game, map_name, kind, dur, time_ago)
                yield self._forward_result(event, fallback)
            return

        id_suffix = self._build_id_suffix(show_gid, show_pid, game_id, None)
        lines = [f"🎮 比赛 #{game_id} | {kind} | {map_name} | {dur} | {time_ago}{id_suffix}"]
        for ti, team in enumerate(game.get("teams", [])):
            members = []
            for p in team:
                name = p.get("name", "?")
                flag = _flag(p.get("country", ""))
                civ = self._civ_name(p.get("civilization", ""))
                result = p.get("result", "")
                rd = p.get("rating_diff")
                rd_str = f" {rd:+.0f}" if rd is not None else ""
                icon = "✅" if result == "win" else ("❌" if result == "loss" else "➖")
                pid_str = ""
                if show_pid:
                    pid_val = p.get("profile_id")
                    if pid_val:
                        pid_str = f" [PID:{pid_val}]"
                members.append(f"{icon}{flag}{name}({civ}){rd_str}{pid_str}")
            lines.append(f"  队伍{ti + 1}: {' | '.join(members)}")
        yield self._forward_result(event, "\n".join(lines))

    @staticmethod
    def _build_id_suffix(show_gid: bool, show_pid: bool, game_id: int | None = None, profile_id: int | None = None) -> str:
        parts = []
        if show_gid and game_id is not None:
            parts.append(f"GID:{game_id}")
        if show_pid and profile_id is not None:
            parts.append(f"PID:{profile_id}")
        return f" [{'] ['.join(parts)}]" if parts else ""

    def _build_help_text(self) -> str:
        t = self.tr.t
        if self.tr.get_lang() == "en":
            return (
                f"{t('help_title')}\n"
                "━━━━━━━━━━━━━━━━\n"
                f"{t('section_bind')}\n"
                f"  {t('help_bind')}\n"
                f"  {t('help_bindid')}\n"
                f"  {t('help_unbind')}\n"
                f"  {t('help_me')}\n"
                "━━━━━━━━━━━━━━━━\n"
                f"{t('section_stats')}\n"
                f"  {t('help_profile')}\n"
                f"  {t('help_recent')}\n"
                f"  {t('help_last')}\n"
                f"  {t('help_compare')}\n"
                f"  {t('help_mecompare')}\n"
                "━━━━━━━━━━━━━━━━\n"
                f"{t('section_leaderboard')}\n"
                f"  {t('help_leaderboard')}\n"
                f"  {t('help_search')}\n"
                "━━━━━━━━━━━━━━━━\n"
                f"{t('section_data')}\n"
                f"  {t('help_unit')}\n"
                f"  {t('help_building')}\n"
                f"  {t('help_tech')}\n"
                f"  {t('help_civ')}\n"
                f"  {t('help_counter')}\n"
                "━━━━━━━━━━━━━━━━\n"
                f"{t('section_patch')}\n"
                f"  {t('help_patch')}\n"
                f"  {t('help_game')}\n"
                f"  {t('help_matchup')}\n"
                f"  {t('help_checkfs')}\n"
                "━━━━━━━━━━━━━━━━\n"
                f"{t('help_general_hint')}"
            )
        return HELP_TEXT

    async def _append_recent_gids(self, profile_id: int) -> list[str]:
        games = await self.client.get_player_games(profile_id, limit=5)
        if not games:
            return []
        lines = ["", "📋 最近对局 GID:"]
        for g in games:
            gid = g.get("game_id", "?")
            map_name = g.get("map", "?")
            time_ago = _elapsed(g.get("started_at", ""))
            lines.append(f"  {gid} | {map_name} | {time_ago}")
        return lines

    async def _handle_matchup(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        mode = parts[2].strip().lower() if len(parts) >= 3 else "rm_solo"

        MODE_MAP = {
            "solo": "rm_solo", "1v1": "rm_solo", "rm_solo": "rm_solo",
            "2v2": "rm_2v2", "rm_2v2": "rm_2v2",
            "3v3": "rm_3v3", "rm_3v3": "rm_3v3",
            "4v4": "rm_4v4", "rm_4v4": "rm_4v4",
            "team": "rm_team", "rm_team": "rm_team",
            "qm": "qm_1v1", "quick": "qm_1v1", "快速": "qm_1v1",
            "qm_1v1": "qm_1v1", "qm1v1": "qm_1v1",
            "qm_2v2": "qm_2v2", "qm2v2": "qm_2v2",
            "qm_3v3": "qm_3v3", "qm3v3": "qm_3v3",
            "qm_4v4": "qm_4v4", "qm4v4": "qm_4v4",
        }
        mode = MODE_MAP.get(mode, mode)

        raw = await self.client.get_matchups(mode)
        if not raw:
            yield event.plain_result("未能获取 matchup 数据，请稍后重试")
            return

        data = raw.get("data", [])
        if not data:
            yield event.plain_result("该模式暂无 matchup 数据")
            return

        patch = raw.get("patch", "?")
        if not HAS_RENDERER:
            mode_label = self._mode_name(mode)
            lines = [f"📊 {mode_label} Matchups ({patch})"]
            civs: dict[str, dict[str, float]] = {}
            for entry in data:
                c1 = entry["civilization"]
                c2 = entry["other_civilization"]
                wr = entry["win_rate"]
                if c1 not in civs:
                    civs[c1] = {}
                civs[c1][c2] = wr
            ordered = sorted(civs.keys())
            for c1 in ordered:
                row_parts = [self._civ_name(c1)]
                for c2 in ordered:
                    wr = civs.get(c1, {}).get(c2)
                    if c1 == c2:
                        row_parts.append("—")
                    elif wr is not None:
                        row_parts.append(f"{wr:.1f}%")
                    else:
                        row_parts.append("·")
                lines.append("  " + " | ".join(row_parts))
            yield self._forward_result(event, "\n".join(lines))
            return

        html = generate_matchup_html(data, mode, patch)
        cache_dir = os.path.join(tempfile.gettempdir(), "aoe4_matchup_cache")
        os.makedirs(cache_dir, exist_ok=True)
        img_path = os.path.join(cache_dir, f"matchup_{uuid.uuid4().hex}.jpg")
        ok = await render_html_to_image(html, img_path, width=min(400 + len(data) * 20, 1200), scale=2)
        if ok and os.path.exists(img_path):
            yield event.chain_result([Image(file=img_path)])
        else:
            yield event.plain_result("图片渲染失败，请稍后重试")

    def _format_game_fallback(self, game: dict, map_name: str, kind: str, dur: str, time_ago: str, id_suffix: str = "") -> str:
        lines = [f"🎮 比赛 | {kind} | {map_name} | {dur} | {time_ago}{id_suffix}", "📊 评分数据暂不可用，显示阵容:"]
        for ti, team in enumerate(game.get("teams", [])):
            members = []
            for p in team:
                name = p.get("name", "?")
                flag = _flag(p.get("country", ""))
                civ = self._civ_name(p.get("civilization", ""))
                result = p.get("result", "")
                rd = p.get("rating_diff")
                rd_str = f" {rd:+.0f}" if rd is not None else ""
                icon = "✅" if result == "win" else ("❌" if result == "loss" else "➖")
                members.append(f"{icon}{flag}{name}({civ}){rd_str}")
            lines.append(f"  队伍{ti + 1}: {' | '.join(members)}")
        return "\n".join(lines)

# ─── 天梯排行榜 ──────────────────────────────

    async def _handle_leaderboard(self, event: AstrMessageEvent):
        text = event.message_str.strip()
        text, show_pid = (text[:-4].strip(), True) if text.endswith(" -pid") else (text, False)
        parts = text.split()
        raw_arg = parts[2].lower() if len(parts) >= 3 else "solo"

        if raw_arg == "me":
            sender_id = event.get_sender_id()
            bound = storage.get_bound(sender_id)
            if not bound:
                yield event.plain_result("请先绑定账号: /aoe4 bind <游戏ID>")
                return
            mode_alias = parts[3].lower() if len(parts) >= 4 else "solo"
            if mode_alias not in LEADERBOARD_KEYS:
                yield event.plain_result(f"不支持的模式: {mode_alias}\n支持 solo/1v1 或 team")
                return
            lb_key = LEADERBOARD_KEYS[mode_alias]
            player_data = await self.client.get_player(bound["profile_id"])
            if not player_data:
                yield event.plain_result("你的数据查询失败")
                return
            mode_info = player_data.get("modes", {}).get(lb_key, {})
            my_rating = mode_info.get("rating")
            if not my_rating:
                yield event.plain_result(f"你在 {self._mode_name(lb_key)} 模式暂无排位分数")
                return
            rank = 0
            page = 1
            found = False
            while page < 50:
                batch = await self.client.get_leaderboard(lb_key, 200, page=page)
                if not batch:
                    break
                for i, p in enumerate(batch, 1):
                    if p.get("profile_id") == bound["profile_id"]:
                        rank = (page - 1) * 200 + i
                        found = True
                        break
                if found:
                    break
                page += 1
            label = self._mode_name(lb_key)
            rank_display = self._fmt_rank(mode_info.get("rank_level"))
            wr = mode_info.get("win_rate", 0)
            games = mode_info.get("games_count", 0)
            if found:
                prefix = f"🏆 {label} | 你排名第 {rank}"
                context_start = max(0, rank - 3)
                context_count = min(page * 200, context_start + 7) - context_start
                context_batch = await self.client.get_leaderboard(lb_key, context_count, offset=context_start)
                lines = [prefix, f"  {rank_display} | {my_rating}分 | 胜率{wr}% | {games}场"]
                if context_batch:
                    lines.append("")
                    lines.append(f"  附近排名:")
                    for i, cp in enumerate(context_batch, context_start + 1):
                        marker = "← 你" if cp.get("profile_id") == bound["profile_id"] else ""
                        lines.append(
                            f"  #{i} {_flag(cp.get('country',''))}{cp.get('name','?')} "
                            f"| {cp.get('rating','N/A')}分{marker}"
                        )
            else:
                lines = [
                    f"🏆 {label} | 未在前 10000 名中找到你",
                    f"  {rank_display} | {my_rating}分 | 胜率{wr}% | {games}场",
                ]
            yield self._forward_result(event, "\n".join(lines))
            return

        mode_alias = raw_arg
        if mode_alias not in LEADERBOARD_KEYS:
            yield event.plain_result(
                f"不支持的模式: {mode_alias}\n"
                f"支持 solo/1v1 或 team"
            )
            return
        lb_key = LEADERBOARD_KEYS[mode_alias]
        limit = 10
        if len(parts) >= 4:
            try:
                limit = max(5, min(30, int(parts[3])))
            except ValueError:
                pass
        logger.info(f"请求排行榜: key={lb_key}, limit={limit}")
        players = await self.client.get_leaderboard(lb_key, limit)
        if not players:
            logger.warning(f"排行榜数据为空: key={lb_key}, limit={limit}")
            yield event.plain_result("排行榜数据获取失败")
            return
        label = self._mode_name(lb_key)
        lines = [f"🏆 {label} 排行榜 TOP {len(players)}"]
        for i, p in enumerate(players, 1):
            name = p.get("name", "?")
            country = _flag(p.get("country", ""))
            rating = p.get("rating", "N/A")
            rank_level = self._fmt_rank(p.get("rank_level"))
            wr = p.get("win_rate", 0)
            streak = p.get("streak", 0)
            streak_str = f" 🔥{streak}" if streak and streak > 0 else (
                f" 💧{abs(streak)}" if streak and streak < 0 else "")
            pid_suffix = f" [PID:{p['profile_id']}]" if show_pid and p.get('profile_id') else ""
            lines.append(
                f"{i:>2}. {country}{name}{pid_suffix}\n"
                f"    {rank_level} | {rating}分 | 胜率{wr}%{streak_str}"
            )
        yield self._forward_result(event, "\n".join(lines))

    async def _handle_checkfs(self, event: AstrMessageEvent):
        ok, msg = await check_flaresolverr_connection()
        icon = "✅" if ok else "❌"
        host = self.config.get("flaresolverr_host", "localhost")
        port = self.config.get("flaresolverr_port", 8191)
        mode = self.config.get("flaresolverr_mode", "once")
        lines = [
            f"{icon} FlareSolverr 连接测试",
            f"  地址: {host}:{port}",
            f"  模式: {mode}",
            f"  结果: {msg}",
        ]
        yield event.plain_result("\n".join(lines))

# ─── 玩家搜索 ────────────────────────────────

    async def _handle_search(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("用法: /aoe4 search <关键词>")
            return
        query = parts[2]
        if len(query) < 3:
            yield event.plain_result("关键词至少需要3个字符")
            return
        players = await self.client.search_player(query)
        if not players:
            yield event.plain_result(f"未找到匹配「{query}」的玩家")
            return
        lines = [f"🔍 搜索「{query}」结果 ({len(players)} 个)"]
        for p in players[:15]:
            name = p.get("name", "?")
            pid = p["profile_id"]
            country = _flag(p.get("country", ""))
            rank_info = ""
            lbs = p.get("leaderboards", {})
            if lbs:
                for key in ("rm_solo", "rm_team"):
                    lb = lbs.get(key)
                    if lb and lb.get("games_count", 0) > 0:
                        rl = self._fmt_rank(lb.get("rank_level"))
                        rt = lb.get("rating", "N/A")
                        rank_info = f" | {rl} {rt}分"
                        break
            lines.append(f"  {country}{name} (ID: {pid}){rank_info}")
        yield self._forward_result(event, "\n".join(lines))

# ─── 游戏数据查询 ────────────────────────────

    async def _handle_civ(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        query = parts[2].strip().lower() if len(parts) >= 3 else ""
        if not query:
            seen = set()
            civ_lines = []
            for code in sorted(self.tr.all_civs().keys()):
                name = self._civ_name(code)
                if name not in seen:
                    seen.add(name)
                    civ_lines.append(f"  {name}")
            yield self._forward_result(event, f"🏛️ 所有文明:\n" + "\n".join(civ_lines) + "\n\n使用 /aoe4 civ <文明名> 查看详情")
            return
        code = CIV_NAME_TO_CODE.get(query)
        if not code:
            code = query
        display = self._civ_name(code)
        data = await self.data.get_civ_data(code)
        if not data:
            yield event.plain_result(f"未找到文明「{query}」的数据")
            return
        unique_units = [u for u in data["units"] if u.get("unique")]
        all_units_base = set(u["baseId"] for u in data["units"])
        lines = [f"🏛️ {display} 文明概览"]
        lines.append(f"  单位种类: {len(all_units_base)}")
        lines.append(f"  建筑: {len(data['buildings'])}")
        lines.append(f"  科技: {len(data['technologies'])}")
        if unique_units:
            lines.append(f"  ⭐ 特色单位: {' | '.join(self.tr.unit(u['name']) for u in unique_units)}")
        unique_buildings = [b for b in data["buildings"] if b.get("unique")]
        if unique_buildings:
            lines.append(f"  ⭐ 特色建筑: {' | '.join(self.tr.building(b['name']) for b in unique_buildings)}")
        unique_techs = [t for t in data["technologies"] if t.get("unique")]
        if unique_techs:
            lines.append(f"  ⭐ 特色科技: {' | '.join(self.tr.tech(t['name']) for t in unique_techs)}")
        yield self._forward_result(event, "\n".join(lines))

    async def _handle_unit(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("用法: /aoe4 unit <单位名>")
            return
        query = parts[2]
        results = await self.data.search_units(query)
        if not results:
            yield event.plain_result(f"未找到单位「{query}」")
            return
        if len(results) > 1:
            names = "\n".join(f"  {i+1}. {u['name']} ({_civs_str_from_code(u.get('civs',[]))})" for i, u in enumerate(results[:5]))
            yield event.plain_result(f"找到多个匹配，请精确搜索:\n{names}")
            return
        lines = self.data.format_unit(results[0])
        yield self._forward_result(event, "\n".join(lines))

    async def _handle_building(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("用法: /aoe4 building <建筑名>")
            return
        query = parts[2]
        results = await self.data.search_buildings(query)
        if not results:
            yield event.plain_result(f"未找到建筑「{query}」")
            return
        if len(results) > 1:
            names = "\n".join(f"  {i+1}. {b['name']} ({_civs_str_from_code(b.get('civs',[]))})" for i, b in enumerate(results[:5]))
            yield event.plain_result(f"找到多个匹配，请精确搜索:\n{names}")
            return
        lines = self.data.format_building(results[0])
        yield self._forward_result(event, "\n".join(lines))

    async def _handle_tech(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("用法: /aoe4 tech <科技名>")
            return
        query = parts[2]
        results = await self.data.search_technologies(query)
        if not results:
            yield event.plain_result(f"未找到科技「{query}」")
            return
        if len(results) > 1:
            names = "\n".join(f"  {i+1}. {t['name']} ({_civs_str_from_code(t.get('civs',[]))})" for i, t in enumerate(results[:5]))
            yield event.plain_result(f"找到多个匹配，请精确搜索:\n{names}")
            return
        lines = self.data.format_technology(results[0])
        yield self._forward_result(event, "\n".join(lines))

# ─── 版本更新 ─────────────────────────────────

    async def _handle_patch(self, event: AstrMessageEvent):
        patches = await self.client.get_patch_notes(5)
        if not patches:
            yield event.plain_result("版本更新数据获取失败")
            return
        lines = ["📰 AoE4 最近版本更新\n━━━━━━━━━━━━━━━━"]
        for p in patches:
            date_val = p.get('date', '')
            if date_val:
                lines.append(f"\n📅 {date_val} ({_elapsed(f'{date_val}T00:00:00+00:00')})")
            else:
                lines.append(f"\n📅 {p.get('pub_date', '?')}")
            lines.append(f"  {p.get('title', '?')}")
            if p.get('description'):
                lines.append(f"  {p.get('description')}")
            if p.get('url') or p.get('link'):
                lines.append(f"  🔗 {p.get('url') or p.get('link')}")
        yield self._forward_result(event, "\n".join(lines))

    async def _handle_counter(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("用法: /aoe4 counter <单位名>")
            return
        query = parts[2]
        image_data = await self.data.get_counter_image_data(query)
        if not image_data or not image_data.get("variants"):
            yield event.plain_result(f"未找到单位「{query}」")
            return

        if HAS_RENDERER:
            try:
                img_result = await self._render_counter_image(event, image_data)
                if img_result:
                    yield img_result
                    return
            except Exception as e:
                logger.error(f"克制图渲染失败: {e}")

        first = image_data["variants"][0]
        text = self.data.format_counter_info({
            "unit": first["_raw"],
            "counters": first["counters"],
            "countered_by": first["countered_by"],
        })
        yield self._forward_result(event, "\n".join(text))

    async def _render_counter_image(self, event: AstrMessageEvent, unit_data: dict):
        from score_renderer import generate_counter_html, render_html_to_image
        variants = unit_data.get("variants", [])
        logger.info(f"渲染克制图: {unit_data.get('unit_name', '?')}, {len(variants)} 个时代变体")
        html = generate_counter_html(unit_data)
        cache_dir = os.path.join(tempfile.gettempdir(), "aoe4_counter_cache")
        os.makedirs(cache_dir, exist_ok=True)
        img_path = os.path.join(cache_dir, f"counter_{uuid.uuid4().hex}.jpg")
        ok = await render_html_to_image(html, img_path, width=480)
        if ok and os.path.exists(img_path):
            logger.info(f"克制图渲染成功: {img_path}")
            return event.chain_result([Image(file=img_path)])
        logger.warning(f"克制图渲染失败或文件不存在")
        return None

# ─── 玩家对比 ─────────────────────────────────

    @staticmethod
    def _get_at_mentions(event: AstrMessageEvent) -> list[At]:
        return [c for c in event.get_messages() if isinstance(c, At) and c.qq != "all"]

    async def _resolve_compare_target(self, spec: str, at_comps: list[At], use_id: bool) -> tuple[dict | None, str | None]:
        """解析对比目标。spec 可能为玩家名、数字ID（use_id时）、或 @占位符。"""
        if spec == "@":
            if not at_comps:
                return None, "未找到被 @ 的用户"
            at = at_comps.pop(0)
            user_id = str(at.qq)
            bound = storage.get_bound(user_id)
            if not bound:
                return None, f"被 @ 的用户 ({at.name or at.qq}) 未绑定游戏账号"
            player = await self.client.get_player(bound["profile_id"])
            if not player:
                return None, "被 @ 的用户绑定的账号数据查询失败"
            return player, None
        if use_id:
            try:
                pid = int(spec)
            except ValueError:
                return None, f"Profile ID 必须是数字: {spec}"
            player = await self.client.get_player(pid)
            if not player:
                return None, f"未找到 Profile ID 为 {pid} 的玩家"
            return player, None
        players = await self.client.search_player(spec)
        if not players:
            return None, f"未找到玩家「{spec}」"
        pid = players[0]["profile_id"]
        player = await self.client.get_player(pid)
        if not player:
            return None, f"「{spec}」的数据查询失败"
        return player, None

    async def _handle_compare(self, event: AstrMessageEvent):
        text = event.message_str.strip()
        use_id = text.endswith(" -id") or text.endswith(" --id")
        if use_id:
            text = text.rsplit(" -id", 1)[0].rsplit(" --id", 1)[0].strip()
        at_comps = self._get_at_mentions(event)
        parts = text.split()
        raw_args = parts[2:] if len(parts) >= 2 else []
        specs = []
        at_idx = 0
        for arg in raw_args:
            if arg.startswith("@") and at_idx < len(at_comps):
                specs.append("@")
                at_idx += 1
            else:
                specs.append(arg)
        while at_idx < len(at_comps) and len(specs) < 2:
            specs.append("@")
            at_idx += 1
        if len(specs) < 2:
            yield event.plain_result(
                "用法:\n"
                "  /aoe4 compare <玩家A> <玩家B>      按名称对比\n"
                "  /aoe4 compare <ID_A> <ID_B> -id   按Profile ID对比\n"
                "  /aoe4 compare <玩家> @用户         与 @ 用户对比\n"
                "  /aoe4 mecompare <玩家>             与自己对比"
            )
            return
        res_a = await self._resolve_compare_target(specs[0], at_comps, use_id)
        if res_a[1]:
            yield event.plain_result(res_a[1])
            return
        res_b = await self._resolve_compare_target(specs[1], at_comps, use_id)
        if res_b[1]:
            yield event.plain_result(res_b[1])
            return
        player_a, player_b = res_a[0], res_b[0]
        lines = await self._build_compare_result(player_a, player_b)
        yield self._forward_result(event, "\n".join(lines))

    async def _handle_mecompare(self, event: AstrMessageEvent):
        sender_id = event.get_sender_id()
        bound = storage.get_bound(sender_id)
        if not bound:
            yield event.plain_result("请先绑定账号: /aoe4 bind <游戏ID>")
            return
        my_player = await self.client.get_player(bound["profile_id"])
        if not my_player:
            yield event.plain_result("你绑定账号的数据查询失败")
            return
        text = event.message_str.strip()
        use_id = text.endswith(" -id") or text.endswith(" --id")
        if use_id:
            text = text.rsplit(" -id", 1)[0].rsplit(" --id", 1)[0].strip()
        at_comps = self._get_at_mentions(event)
        parts = text.split()
        raw_args = parts[2:] if len(parts) >= 2 else []
        spec = None
        at_used = False
        for arg in raw_args:
            if arg.startswith("@") and not at_used and at_comps:
                spec = "@"
                at_used = True
            elif not spec:
                spec = arg
        if not spec and at_comps and not at_used:
            spec = "@"
            at_used = True
        if not spec:
            yield event.plain_result(
                "用法:\n"
                "  /aoe4 mecompare <玩家>      与指定玩家对比\n"
                "  /aoe4 mecompare @用户        与 @ 用户对比"
            )
            return
        target_player, err = await self._resolve_compare_target(spec, at_comps, use_id)
        if err:
            yield event.plain_result(err)
            return
        lines = await self._build_compare_result(my_player, target_player)
        yield self._forward_result(event, "\n".join(lines))

    async def _build_compare_result(self, player_a: dict, player_b: dict) -> list[str]:
        name_a = player_a["name"]
        name_b = player_b["name"]
        flag_a = _flag(player_a.get("country", ""))
        flag_b = _flag(player_b.get("country", ""))
        modes_a = player_a.get("modes", {})
        modes_b = player_b.get("modes", {})

        lines = [f"📊 玩家实力对比\n━━━━━━━━━━━━━━━━\n{flag_a}{name_a}  vs  {flag_b}{name_b}"]
        wins_a = 0
        wins_b = 0

        lines.append("\n═══ 1v1 排位 ═══")
        solo_lines, wa, wb = self._cmp_mode(modes_a.get("rm_solo", {}), modes_b.get("rm_solo", {}), name_a, name_b)
        lines.extend(solo_lines)
        wins_a += wa; wins_b += wb

        lines.append("\n═══ 组队排位 ═══")
        team_lines, wa2, wb2 = self._cmp_mode(modes_a.get("rm_team", {}), modes_b.get("rm_team", {}), name_a, name_b)
        lines.extend(team_lines)
        wins_a += wa2; wins_b += wb2

        lines.append("\n═══ 综合能力 ═══")
        d8_lines = self._analyze_dim8(modes_a, modes_b, name_a, name_b)
        lines.extend(d8_lines)

        wa3, wb3 = self._count_dim8_wins(modes_a, modes_b)
        wins_a += wa3; wins_b += wb3

        lines.append(f"\n📝 {self._funny_summary(wins_a, wins_b, name_a, name_b)}")
        return lines

    def _count_dim8_wins(self, modes_a: dict, modes_b: dict) -> tuple[int, int]:
        def _mode_list(mode_dict: dict) -> list:
            return [v for v in mode_dict.values()
                    if isinstance(v, dict) and "games_count" in v and not isinstance(v.get("games_count"), dict)]

        ma, mb = _mode_list(modes_a), _mode_list(modes_b)
        wa = wb = 0

        ta = sum(m.get("games_count", 0) for m in ma)
        tb = sum(m.get("games_count", 0) for m in mb)
        if ta > tb: wa += 1
        elif tb > ta: wb += 1

        def wwr(modes):
            tg = sum(m.get("games_count", 0) for m in modes)
            tw = sum(m.get("wins_count", 0) for m in modes)
            return tw / tg if tg else 0
        if wwr(ma) > wwr(mb): wa += 1
        elif wwr(mb) > wwr(ma): wb += 1

        mca = sum(1 for m in ma if m.get("games_count", 0) > 0)
        mcb = sum(1 for m in mb if m.get("games_count", 0) > 0)
        if mca > mcb: wa += 1
        elif mcb > mca: wb += 1

        return wa, wb

    def _analyze_dim8(self, modes_a: dict, modes_b: dict, name_a: str, name_b: str) -> list[str]:
        def _mode_list(mode_dict: dict) -> list:
            return [v for v in mode_dict.values()
                    if isinstance(v, dict) and "games_count" in v and not isinstance(v.get("games_count"), dict)]

        ma, mb = _mode_list(modes_a), _mode_list(modes_b)
        ta = sum(m.get("games_count", 0) for m in ma)
        tb = sum(m.get("games_count", 0) for m in mb)
        twa = sum(m.get("wins_count", 0) for m in ma)
        twb = sum(m.get("wins_count", 0) for m in mb)

        def wwr(modes):
            tg = sum(m.get("games_count", 0) for m in modes)
            tw = sum(m.get("wins_count", 0) for m in modes)
            return round(tw / tg * 100, 1) if tg else 0

        def _arrow(v_a, v_b):
            if v_a > v_b: return f"← {name_a}"
            elif v_b > v_a: return f"← {name_b}"
            return "→ 平手"

        lines = []
        lines.append(f"  总场次: {ta} / {tb}  {_arrow(ta, tb)}")
        lines.append(f"  总胜局: {twa} / {twb}  {_arrow(twa, twb)}")
        lines.append(f"  综合胜率: {wwr(ma)}% / {wwr(mb)}%  {_arrow(wwr(ma), wwr(mb))}")

        mca = sum(1 for m in ma if m.get("games_count", 0) > 0)
        mcb = sum(1 for m in mb if m.get("games_count", 0) > 0)
        lines.append(f"  涉及模式: {mca}种 / {mcb}种  {_arrow(mca, mcb)}")

        lines.append(f"  💡 {self._player_style_desc(ma, name_a)}")
        lines.append(f"  💡 {self._player_style_desc(mb, name_b)}")
        return lines

    def _player_style_desc(self, modes_list: list, name: str) -> str:
        total = sum(m.get("games_count", 0) for m in modes_list)
        wins = sum(m.get("wins_count", 0) for m in modes_list)
        wr = wins / total * 100 if total else 0
        best = max((m.get("max_rating", 0) or 0) for m in modes_list)
        mod_cnt = sum(1 for m in modes_list if m.get("games_count", 0) > 0)

        if total == 0:
            return f"{name}: 还没打过排位，是个云玩家吧"

        tags = []
        if total > 1000: tags.append("老油条")
        elif total > 500: tags.append("肝帝")
        elif total > 100: tags.append("有点东西")
        else: tags.append("萌新")

        if wr > 60: tags.append("战神附体")
        elif wr > 55: tags.append("实力不俗")
        elif wr > 50: tags.append("中规中矩")
        else: tags.append("需要加油")

        if mod_cnt >= 5: tags.append("全能王")
        elif mod_cnt >= 3: tags.append("多面手")
        else: tags.append("专精玩家")

        if best >= 2000: tags.append("高分段大佬")
        elif best >= 1500: tags.append("中分段选手")
        elif best >= 1000: tags.append("低分段挣扎")

        desc = f"{name}: {'，'.join(tags)}"
        if wr < 45:
            desc = f"{name}: 😭 {'，'.join(tags)}，菜就多练"
        elif wr > 65 and total > 200:
            desc = f"{name}: 🤯 {'，'.join(tags)}，这就是大佬的世界吗"
        return desc

    def _funny_summary(self, a_wins: int, b_wins: int, name_a: str, name_b: str) -> str:
        diff = a_wins - b_wins
        if diff >= 5:
            return f"{name_a} 全方位碾压 {name_b}，{name_b} 拉完了！！！"
        if diff == 4:
            return f"{name_a} 除了脸皮什么都比 {name_b} 强，{name_b} 赶紧跑路吧"
        if diff == 3:
            return f"{name_a} 明显强于 {name_b}，{name_b} 还是回去练练吧"
        if diff == 2:
            return f"{name_a} 全面占优，{name_b} 还需要努力啊"
        if diff == 1:
            return f"{name_a} 略胜一筹，{name_b} 差距不大，下次加油"
        if diff == 0:
            return f"半斤八两，棋逢对手！建议你俩打一架，赢的叫爸爸"
        if diff == -1:
            return f"{name_b} 略胜一筹，{name_a} 再接再厉，你可以的"
        if diff == -2:
            return f"{name_b} 全面占优，{name_a} 还需要努力啊"
        if diff == -3:
            return f"{name_b} 明显强于 {name_a}，{name_a} 还是回去练练吧"
        if diff == -4:
            return f"{name_b} 除了脸皮什么都比 {name_a} 强，{name_a} 赶紧跑路吧"
        return f"{name_b} 全方位碾压 {name_a}，{name_a} 拉完了！！！"

    def _cmp_mode(self, mode_a: dict, mode_b: dict, name_a: str, name_b: str) -> tuple[list[str], int, int]:
        lines = []
        wins_a = 0
        wins_b = 0

        def _arrow(v_a, v_b, higher_better=True):
            if v_a is None and v_b is None:
                return "", 0, 0
            if v_a is None:
                if higher_better:
                    return f"← {name_b}", 0, 1
                return "", 0, 0
            if v_b is None:
                if higher_better:
                    return f"← {name_a}", 1, 0
                return "", 0, 0
            if higher_better:
                if v_a > v_b:
                    return f"← {name_a}", 1, 0
                elif v_b > v_a:
                    return f"← {name_b}", 0, 1
                return "→ 平手", 0, 0
            else:
                if v_a < v_b:
                    return f"← {name_a}", 1, 0
                elif v_b < v_a:
                    return f"← {name_b}", 0, 1
                return "→ 平手", 0, 0

        has_data = False

        rt_a = mode_a.get("rating")
        rt_b = mode_b.get("rating")
        if rt_a is not None or rt_b is not None:
            has_data = True
            rt_a_str = f"{rt_a}" if rt_a is not None else "N/A"
            rt_b_str = f"{rt_b}" if rt_b is not None else "N/A"
            arrow_str, wa, wb = _arrow(rt_a, rt_b)
            wins_a += wa; wins_b += wb
            lines.append(f"  分数: {rt_a_str} / {rt_b_str}  {arrow_str}")

        rl_a = mode_a.get("rank_level")
        rl_b = mode_b.get("rank_level")
        if rl_a is not None or rl_b is not None:
            has_data = True
            rl_a_str = self._fmt_rank(rl_a)
            rl_b_str = self._fmt_rank(rl_b)
            rank_order = ["conqueror_3","conqueror_2","conqueror_1",
                          "diamond_3","diamond_2","diamond_1",
                          "platinum_3","platinum_2","platinum_1",
                          "gold_3","gold_2","gold_1",
                          "silver_3","silver_2","silver_1",
                          "bronze_3","bronze_2","bronze_1","unranked"]
            rl_score_a = rank_order.index(rl_a) if rl_a in rank_order else 99
            rl_score_b = rank_order.index(rl_b) if rl_b in rank_order else 99
            arrow_str, wa, wb = _arrow(rl_score_a, rl_score_b, higher_better=False)
            wins_a += wa; wins_b += wb
            lines.append(f"  段位: {rl_a_str} / {rl_b_str}  {arrow_str}")

        wr_a = mode_a.get("win_rate")
        wr_b = mode_b.get("win_rate")
        if wr_a is not None or wr_b is not None:
            has_data = True
            wr_a_str = f"{wr_a}%" if wr_a is not None else "N/A"
            wr_b_str = f"{wr_b}%" if wr_b is not None else "N/A"
            arrow_str, wa, wb = _arrow(wr_a, wr_b)
            wins_a += wa; wins_b += wb
            lines.append(f"  胜率: {wr_a_str} / {wr_b_str}  {arrow_str}")

        gc_a = mode_a.get("games_count", 0)
        gc_b = mode_b.get("games_count", 0)
        if gc_a or gc_b:
            has_data = True
            arrow_str, wa, wb = _arrow(gc_a, gc_b)
            wins_a += wa; wins_b += wb
            lines.append(f"  场次: {gc_a} / {gc_b}  {arrow_str}")

        sk_a = mode_a.get("streak", 0)
        sk_b = mode_b.get("streak", 0)
        if sk_a or sk_b:
            has_data = True
            sk_a_str = f"🔥{sk_a}" if sk_a and sk_a > 0 else (f"💧{abs(sk_a)}" if sk_a and sk_a < 0 else "–")
            sk_b_str = f"🔥{sk_b}" if sk_b and sk_b > 0 else (f"💧{abs(sk_b)}" if sk_b and sk_b < 0 else "–")
            arrow_str, wa, wb = _arrow(sk_a, sk_b)
            wins_a += wa; wins_b += wb
            lines.append(f"  连胜: {sk_a_str} / {sk_b_str}  {arrow_str}")

        hr_a = mode_a.get("rating_max") or mode_a.get("highest_rating") or mode_a.get("rating")
        hr_b = mode_b.get("rating_max") or mode_b.get("highest_rating") or mode_b.get("rating")
        if hr_a is not None or hr_b is not None:
            has_data = True
            hr_a_str = f"{hr_a}" if hr_a is not None else "N/A"
            hr_b_str = f"{hr_b}" if hr_b is not None else "N/A"
            arrow_str, wa, wb = _arrow(hr_a, hr_b)
            wins_a += wa; wins_b += wb
            lines.append(f"  历史最高: {hr_a_str} / {hr_b_str}  {arrow_str}")

        if not has_data:
            lines.append("  (无排位数据)")
        return lines, wins_a, wins_b

    async def terminate(self):
        await self.client.close()
        await self.data.close()
        if HAS_RENDERER:
            await close_renderer()
        logger.info(self.tr.t("plugin_unloaded"))
