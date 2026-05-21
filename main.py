import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from api_client import AoE4WorldClient
from data_client import AoE4DataClient, CIV_CODE_TO_NAME, CIV_NAME_TO_CODE, format_unit, format_building, format_technology
import storage

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


def _flag(country: str | None) -> str:
    return COUNTRY_FLAGS.get(country, "")


def _civ_name(civ_id: str) -> str:
    return CIV_NAMES.get(civ_id, civ_id)


def _elapsed(started_at: str) -> str:
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


def _duration_str(seconds: int) -> str:
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def _civs_str_from_code(codes: list[str]) -> str:
    names = [CIV_CODE_TO_NAME.get(c, c) for c in codes]
    return ", ".join(names)


HELP_TEXT = (
    "🎮 AOE4 查询插件 v1.0.0\n"
    "━━━━━━━━━━━━━━━━\n"
    "📌 账号绑定\n"
    "  /aoe4 bind <游戏ID>  绑定游戏账号\n"
    "  /aoe4 unbind          解绑账号\n"
    "  /aoe4 me              查看绑定信息\n"
    "━━━━━━━━━━━━━━━━\n"
    "📊 战绩查询\n"
    "  /aoe4 profile [ID]    查询玩家资料\n"
    "  /aoe4 recent [数量]   最近对局记录\n"
    "  /aoe4 last            上一局详情\n"
    "━━━━━━━━━━━━━━━━\n"
    "🏆 天梯与搜索\n"
    "  /aoe4 leaderboard [模式]  排行榜\n"
    "  /aoe4 search <关键词>     搜索玩家\n"
    "━━━━━━━━━━━━━━━━\n"
    "� 游戏数据\n"
    "  /aoe4 unit <名称>        查询单位数据\n"
    "  /aoe4 building <名称>    查询建筑数据\n"
    "  /aoe4 tech <名称>        查询科技数据\n"
    "  /aoe4 civ [名称]         文明概览（不填列出所有）\n"
    "━━━━━━━━━━━━━━━━\n"
    "💡 支持中/英文名搜索"
)


class AstrByAOE4SearchViewPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.client = AoE4WorldClient()
        self.data = AoE4DataClient()
        logger.info("AstrByAOE4SearchViewPlugin 已加载")

    @filter.command("aoe4")
    async def aoe4_router(self, event: AstrMessageEvent):
        content = event.message_str.strip()
        parts = content.split()
        sub = parts[1].lower() if len(parts) >= 2 else ""

        if not sub or sub in ("help", "-h", "--help"):
            yield event.plain_result(HELP_TEXT)
            return

        method_map = {
            "bind": self._handle_bind,
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

    async def _resolve_player(self, sender_id: str, name: str | None):
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
            yield event.plain_result("用法: /aoe4 bind <游戏ID>")
            return
        name = parts[2]
        players = await self.client.search_player(name)
        if not players:
            yield event.plain_result(f"未找到玩家「{name}」，请检查拼写")
            return
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

    async def _handle_unbind(self, event: AstrMessageEvent):
        sender_id = event.get_sender_id()
        if storage.unbind(sender_id):
            yield event.plain_result("✅ 已成功解绑")
        else:
            yield event.plain_result("你还没有绑定账号")

    async def _handle_me(self, event: AstrMessageEvent):
        sender_id = event.get_sender_id()
        bound = storage.get_bound(sender_id)
        if not bound:
            yield event.plain_result("你还没有绑定游戏账号，请使用 /aoe4 bind <游戏ID> 绑定")
            return
        player = await self.client.get_player(bound["profile_id"])
        if not player:
            yield event.plain_result(
                f"绑定的账号: {bound['player_name']} (ID: {bound['profile_id']})\n"
                "数据查询失败，请稍后重试"
            )
            return
        lines = await self._format_profile(player)
        yield event.plain_result("\n".join(lines))

# ─── 玩家资料 ─────────────────────────────────

    async def _handle_profile(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        name = parts[2] if len(parts) >= 3 else None
        sender_id = event.get_sender_id()
        player, err = await self._resolve_player(sender_id, name)
        if err:
            yield event.plain_result(err)
            return
        lines = await self._format_profile(player)
        yield event.plain_result("\n".join(lines))

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
            label = LEADERBOARD_NAMES.get(key, key)
            rating = mode.get("rating")
            rank_level = mode.get("rank_level")
            games = mode.get("games_count", 0)
            wins = mode.get("wins_count", 0)
            losses = mode.get("losses_count", 0)
            win_rate = mode.get("win_rate", 0)
            streak = mode.get("streak", 0)
            rank_display = _format_rank(rank_level)
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
        parts = event.message_str.strip().split()
        limit = 5
        if len(parts) >= 3:
            try:
                limit = max(1, min(10, int(parts[2])))
            except ValueError:
                pass
        sender_id = event.get_sender_id()
        bound = storage.get_bound(sender_id)
        if not bound:
            yield event.plain_result("请先绑定账号: /aoe4 bind <游戏ID>")
            return
        pid = bound["profile_id"]
        games = await self.client.get_player_games(pid, limit)
        if not games:
            yield event.plain_result("最近没有对局记录")
            return
        lines = [f"🎮 {bound['player_name']} 最近 {len(games)} 场对局"]
        for i, g in enumerate(games, 1):
            map_name = g.get("map", "未知地图")
            kind = LEADERBOARD_NAMES.get(g.get("kind", ""), g.get("kind", ""))
            dur = _duration_str(g.get("duration", 0))
            time_ago = _elapsed(g.get("started_at", ""))
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
                civ = _civ_name(my_team_data.get("civilization", ""))
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
                        civ_label = _civ_name(pd.get("civilization", ""))
                        entry = f"{n}({civ_label})"
                        if pd["profile_id"] == pid:
                            continue
                        if idx == my_team_idx:
                            teammates.append(entry)
                        else:
                            opponents.append(entry)
                lines.append(
                    f"{i}. {result_icon} {kind} | {map_name} | {dur}\n"
                    f"   🏛 {civ} {rd_str}  |  {time_ago}"
                )
                if teammates:
                    lines.append(f"   队友: {', '.join(teammates)}")
                if opponents:
                    lines.append(f"   对手: {', '.join(opponents)}")
            else:
                lines.append(f"{i}. {map_name} {kind} - 无法获取详细数据")
        yield event.plain_result("\n".join(lines))

# ─── 上一局详情 ──────────────────────────────

    async def _handle_last(self, event: AstrMessageEvent):
        sender_id = event.get_sender_id()
        bound = storage.get_bound(sender_id)
        if not bound:
            yield event.plain_result("请先绑定账号: /aoe4 bind <游戏ID>")
            return
        pid = bound["profile_id"]
        game = await self.client.get_player_last_game(pid, include_stats=True)
        if not game:
            yield event.plain_result("未找到上一局对局数据")
            return
        map_name = game.get("map", "未知地图")
        kind = LEADERBOARD_NAMES.get(game.get("kind", ""), game.get("kind", "排位"))
        dur = _duration_str(game.get("duration", 0))
        time_ago = _elapsed(game.get("started_at", ""))
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
        civ = _civ_name(my_data.get("civilization", ""))
        rd = my_data.get("rating_diff")
        rd_str = f" ({rd:+.0f})" if rd is not None else ""
        result_icon = "✅" if result == "win" else "❌"
        teams_strs = []
        for ti, team in enumerate(game.get("teams", [])):
            members = []
            for p in team:
                name = p.get("name", "?")
                flag = _flag(p.get("country", ""))
                civ = _civ_name(p.get("civilization", ""))
                members.append(f"{flag}{name}({civ})")
            teams_strs.append(f"  队伍{ti + 1}: {', '.join(members)}")
        player_stats = None
        if "stats" in game:
            for s in game.get("stats", []):
                if s.get("profile_id") == pid:
                    player_stats = s
                    break
        lines = [
            f"🎮 上一局 | {result_icon} {result.upper()}\n"
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
        yield event.plain_result("\n".join(lines))

# ─── 天梯排行榜 ──────────────────────────────

    async def _handle_leaderboard(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split()
        mode_alias = parts[2].lower() if len(parts) >= 3 else "solo"
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
        label = LEADERBOARD_NAMES.get(lb_key, lb_key)
        lines = [f"🏆 {label} 排行榜 TOP {len(players)}"]
        for i, p in enumerate(players, 1):
            name = p.get("name", "?")
            country = _flag(p.get("country", ""))
            rating = p.get("rating", "N/A")
            rank_level = _format_rank(p.get("rank_level"))
            wr = p.get("win_rate", 0)
            streak = p.get("streak", 0)
            streak_str = f" 🔥{streak}" if streak and streak > 0 else (
                f" 💧{abs(streak)}" if streak and streak < 0 else "")
            lines.append(
                f"{i:>2}. {country}{name}\n"
                f"    {rank_level} | {rating}分 | 胜率{wr}%{streak_str}"
            )
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
                        rl = _format_rank(lb.get("rank_level"))
                        rt = lb.get("rating", "N/A")
                        rank_info = f" | {rl} {rt}分"
                        break
            lines.append(f"  {country}{name} (ID: {pid}){rank_info}")
        yield event.plain_result("\n".join(lines))

# ─── 游戏数据查询 ────────────────────────────

    async def _handle_civ(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        query = parts[2].strip().lower() if len(parts) >= 3 else ""
        if not query:
            all_civs = "\n".join(
                f"  {name}" for _code, name in sorted(CIV_CODE_TO_NAME.items(),
                key=lambda x: x[1])
            )
            yield event.plain_result(f"🏛️ 所有文明:\n{all_civs}\n\n使用 /aoe4 civ <文明名> 查看详情")
            return
        code = CIV_NAME_TO_CODE.get(query)
        if not code:
            code = query
        display = CIV_CODE_TO_NAME.get(code, query)
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
            lines.append(f"  ⭐ 特色单位: {' '.join(u['name'] for u in unique_units)}")
        unique_buildings = [b for b in data["buildings"] if b.get("unique")]
        if unique_buildings:
            lines.append(f"  ⭐ 特色建筑: {' '.join(b['name'] for b in unique_buildings)}")
        unique_techs = [t for t in data["technologies"] if t.get("unique")]
        if unique_techs:
            lines.append(f"  ⭐ 特色科技: {' '.join(t['name'] for t in unique_techs)}")
        yield event.plain_result("\n".join(lines))

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
        lines = format_unit(results[0])
        yield event.plain_result("\n".join(lines))

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
        lines = format_building(results[0])
        yield event.plain_result("\n".join(lines))

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
        lines = format_technology(results[0])
        yield event.plain_result("\n".join(lines))

    async def terminate(self):
        await self.client.close()
        await self.data.close()
        logger.info("AstrByAOE4SearchViewPlugin 已卸载")
