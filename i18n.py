class Translator:
    def __init__(self, lang: str = "zh-CN"):
        self.lang = lang if lang in _TABLE else "zh-CN"
        self._table = _TABLE[self.lang]

    def t(self, key: str, **kwargs) -> str:
        text = self._table.get(key, key)
        if kwargs:
            text = text.format(**kwargs)
        return text

    def get_lang(self) -> str:
        return self.lang


_TABLE: dict[str, dict[str, str]] = {
    "zh-CN": {
        # ─── 插件信息 ───
        "plugin_loaded": "astrbot-plugin-aoe4 已加载",
        "plugin_unloaded": "astrbot-plugin-aoe4 已卸载",
        "help_title": "🎮 AOE4 查询插件 v1.1.0",
        "help_general_hint": "💡 通用标志:  -gid 显示对局ID  -pid 显示Profile ID",

        # ─── 指令说明（帮助） ───
        "help_bind": "/aoe4 bind <游戏ID>      通过名字搜索绑定",
        "help_bindid": "/aoe4 bindid <ID>        通过Profile ID直接绑定",
        "help_unbind": "/aoe4 unbind              解绑账号",
        "help_me": "/aoe4 me                  查看绑定信息（加 -gid 显示最近GID）",
        "help_profile": "/aoe4 profile [ID]  @/-id  查询玩家资料（加 -gid 显示最近GID）",
        "help_recent": "/aoe4 recent [ID] [N] @/-id  最近对局记录（加 -gid/-pid 显示ID）",
        "help_last": "/aoe4 last [ID] @/-id      上一局详情\n                       加 -score 评分图  -gid/-pid 显示ID",
        "help_compare": "/aoe4 compare <A> <B> @/-id  玩家对比",
        "help_mecompare": "/aoe4 mecompare <A> @/-id  自己 vs 指定玩家",
        "help_leaderboard": "/aoe4 leaderboard [模式]  排行榜",
        "help_rank": "/aoe4 rank [模式] [数量]  同上",
        "help_search": "/aoe4 search <关键词>     搜索玩家",
        "help_civ": "/aoe4 civ [名称]         文明概览（不填列出所有）",
        "help_unit": "/aoe4 unit <名称>        查询单位数据",
        "help_building": "/aoe4 building <名称>    查询建筑数据",
        "help_tech": "/aoe4 tech <名称>        查询科技数据",
        "help_counter": "/aoe4 counter <单位>     查询克制关系",
        "help_patch": "/aoe4 patch             查看最近版本更新",
        "help_game": "/aoe4 game <比赛ID>     通过ID查比赛详情\n                       加 -score 评分图  -gid/-pid 显示ID",

        "section_bind": "📌 账号绑定",
        "section_stats": "📊 战绩查询",
        "section_leaderboard": "🏆 天梯与搜索",
        "section_data": "📖 游戏数据",
        "section_patch": "📰 版本信息",

        # ─── 绑定系统 ───
        "not_bind": "你还没有绑定游戏账号，请使用 /aoe4 bind <游戏ID> 绑定",
        "bind_success": "✅ 绑定成功！{country}{name}\nProfile ID: {pid}",
        "unbind_success": "✅ 已成功解绑",
        "unbind_none": "你还没有绑定账号",
        "bind_usage": "用法: /aoe4 bind <游戏ID>",
        "bindid_usage": "用法: /aoe4 bindid <Profile ID>",
        "bindid_invalid": "Profile ID 必须是数字",
        "bindid_not_found": "未找到 Profile ID 为 {pid} 的玩家",
        "bind_multiple": "找到多个「{name}」，请使用 Profile ID 精确绑定:",
        "bind_multiple_hint": "使用 /aoe4 bindid <Profile ID> 绑定",
        "bind_data_fail": "绑定的账号: {name} (ID: {pid})\n数据查询失败，请稍后重试",

        # ─── 玩家资料 ───
        "profile_title": "📋 {country}{name}  |  ID: {pid}",
        "profile_no_rank": "暂无排位数据",

        # ─── 对局 ───
        "recent_title": "🎮 {name} 最近 {n} 场对局",
        "recent_empty": "{name} 最近没有对局记录",
        "last_no_game": "未找到上一局对局数据",
        "last_no_data": "无法获取本局你的数据",
        "game_usage": "用法: /aoe4 game <比赛ID> [-score] [-gid] [-pid]",
        "game_invalid_id": "比赛ID必须是数字",
        "game_not_found": "未找到比赛 {gid}",
        "game_title": "🎮 比赛 #{gid} | {kind} | {map} | {dur} | {time}{ids}",
        "last_title": "🎮 上一局 | {icon} {result}{ids}",
        "last_line": "  {kind} | {map} | {dur} | {time}",
        "last_civ": "  🏛 {civ} {rd}",
        "last_eco_mil_tech": "  📊 经济: {eco}  军事: {mil}  科技: {tech}",
        "score_unavailable": "📊 评分数据暂不可用，显示阵容:",
        "recent_score_unavailable": "无法获取详细数据",

        # ─── 评分对比文字版 ───
        "score_comparison": "📊 评分 Comparison",

        # ─── 天梯 ───
        "leaderboard_no_data": "暂无排行榜数据",
        "lb_rank": "排名",
        "lb_name": "玩家",
        "lb_rating": "Rating",
        "lb_games": "场次",
        "lb_winrate": "胜率",
        "lb_streak": "连胜/连败",

        # ─── 搜索 ───
        "search_usage": "用法: /aoe4 search <关键词>",
        "search_no_result": "未找到匹配的玩家",
        "search_result": "找到 {n} 个匹配玩家:",

        # ─── Game / Last -score 回退 ───
        "game_fallback_title": "🎮 比赛 | {kind} | {map} | {dur} | {time}{ids}",

        # ─── 队伍标签 ───
        "team_win": "胜队",
        "team_loss": "败队",
        "team_blue": "蓝队",
        "team_red": "红队",

        # ─── 图片渲染标题 ───
        "render_score_title": "🎮 {kind} | {map} | {dur}",
        "render_score_subtitle": "⏱ {time}",
        "render_analysis_title": "🎙️ 搞怪锐评",
        "render_analysis_subtitle": "{title} | {subtitle}",

        # ─── 搞怪锐评标签 ───
        "tag_farmer": "🌾 种田王",
        "tag_farmer_desc": "种了 {food} 食物，仿佛开了农场",
        "tag_economist": "🏠 经济大师",
        "tag_economist_desc": "经济分 {eco}，闷声发大财",
        "tag_god": "💀 战神下凡",
        "tag_god_desc": "KD {kd}，杀穿全场",
        "tag_muscle": "⚔️ 猛男",
        "tag_muscle_desc": "KD {kd}，实力碾压",
        "tag_feeder": "☁️ 白给王",
        "tag_feeder_desc": "阵亡 {deaths} 次，峡谷先锋",
        "tag_gifter": "🎁 送温暖",
        "tag_gifter_desc": "阵亡 {deaths} / 击杀 {kills}，慈善大使",
        "tag_slow": "🐢 养生玩家",
        "tag_slow_desc": "APM {apm}，慢工出细活",
        "tag_speed": "⚡ 手速怪",
        "tag_speed_desc": "APM {apm}，单身二十年",
        "tag_demolisher": "🏗️ 拆迁队长",
        "tag_demolisher_desc": "摧毁 {structdmg} 建筑",
        "tag_bruteforce": "👊 纯武力",
        "tag_bruteforce_desc": "一个建筑没拆也能赢，把对面人全杀光了",
        "tag_builder": "🏘️ 建房狂魔",
        "tag_builder_desc": "造了 {bprod} 个建筑",
        "tag_techie": "🔬 科技宅",
        "tag_techie_desc": "研究了 {upg} 项科技",
        "tag_brute": "🪓 莽夫",
        "tag_brute_desc": "科技是什么？干就完了",
        "tag_rich": "💰 资源大户",
        "tag_rich_desc": "总支出 {resources} 的石油大王",
        "tag_frugal": "💎 勤俭持家",
        "tag_frugal_desc": "只花 {resources} 资源就赢了",
        "tag_balanced": "⚖️ 均衡发展",
        "tag_balanced_desc": "食物/木材/黄金都过万的三好村民",
        "tag_social": "🏛️ 交际花",
        "tag_social_desc": "社会分 {soc}，帝国的社交达人",
        "tag_popdealer": "👶 人口贩子",
        "tag_popdealer_desc": "生产了 {sqprod} 个单位",
        "tag_warrior": "🗡️ 战争狂人",
        "tag_warrior_desc": "军事分 {mil}，眼里只有战争",
        "tag_average": "🤷 平平无奇",
        "tag_average_desc": "数据均衡，稳健型玩家",

        # ─── ID 后缀 ───
        "id_suffix_gid": "GID:{gid}",
        "id_suffix_pid": "PID:{pid}",
        "recent_gids_title": "📋 最近对局 GID:",

        # ─── 文明名称 ───
        "civ_abbasid": "阿巴斯王朝",
        "civ_english": "英格兰",
        "civ_chinese": "中国",
        "civ_french": "法兰西",
        "civ_hre": "神圣罗马帝国",
        "civ_mongols": "蒙古",
        "civ_rus": "罗斯",
        "civ_delhi": "德里苏丹国",
        "civ_ottomans": "奥斯曼",
        "civ_malians": "马里",
        "civ_byzantines": "拜占庭",
        "civ_japanese": "日本",
        "civ_ayyubids": "阿尤布",
        "civ_jeanne": "圣女贞德",
        "civ_dragon": "龙骑士团",
        "civ_zhuxi": "朱熹遗产",

        # ─── 模式名称 ───
        "mode_rm_solo": "1v1 排位",
        "mode_rm_2v2": "2v2 排位",
        "mode_rm_3v3": "3v3 排位",
        "mode_rm_4v4": "4v4 排位",
        "mode_rm_team": "组队排位",
        "mode_qm_1v1": "1v1 快速",
        "mode_qm_2v2": "2v2 快速",
        "mode_qm_3v3": "3v3 快速",
        "mode_qm_4v4": "4v4 快速",

        # ─── 单位/建筑/科技中文字段 ───
        "unit_hp": "生命值",
        "unit_cost": "造价",
        "unit_damage": "伤害",
        "unit_armor": "护甲",
        "unit_speed": "移速",
        "unit_range": "射程",
        "unit_rate": "攻击速度",
        "unit_bonus": "加成伤害",
        "unit_built_by": "建造于",
        "unit_trained_at": "训练于",
        "unit_requires": "需求",

        "building_hp": "生命值",
        "building_cost": "造价",
        "building_garrison": "驻军容量",
        "building_influence": "影响范围",
        "building_produces": "可生产",

        "tech_effect": "效果",
        "tech_cost": "造价",
        "tech_applies_to": "作用于",
        "tech_researched_at": "研发于",
        "tech_required_age": "需求时代",

        # ─── 错误消息 ───
        "err_not_found_cmd": "未找到指令 /aoe4 {sub} 的帮助",
        "err_data_query": "数据查询失败",
        "err_network": "网络请求失败，请稍后重试",
        "err_flaresolverr": "FlareSolverr 不可用",
    },

    "en": {
        # ─── Plugin Info ───
        "plugin_loaded": "astrbot-plugin-aoe4 loaded",
        "plugin_unloaded": "astrbot-plugin-aoe4 unloaded",
        "help_title": "🎮 AOE4 Query Plugin v1.1.0",
        "help_general_hint": "💡 Flags:  -gid show game ID  -pid show profile ID",

        # ─── Command Descriptions (Help) ───
        "help_bind": "/aoe4 bind <IGN>          Search & bind by IGN",
        "help_bindid": "/aoe4 bindid <ID>         Bind by profile ID directly",
        "help_unbind": "/aoe4 unbind               Unbind current account",
        "help_me": "/aoe4 me                   View bound info (add -gid for recent GIDs)",
        "help_profile": "/aoe4 profile [ID]  @/-id  View player profile (add -gid for recent GIDs)",
        "help_recent": "/aoe4 recent [ID] [N] @/-id  Recent games (add -gid/-pid to show IDs)",
        "help_last": "/aoe4 last [ID] @/-id       Last game details\n                       -score for image  -gid/-pid for IDs",
        "help_compare": "/aoe4 compare <A> <B> @/-id  Compare two players",
        "help_mecompare": "/aoe4 mecompare <A> @/-id  Self vs specified player",
        "help_leaderboard": "/aoe4 leaderboard [mode]  Leaderboard",
        "help_rank": "/aoe4 rank [mode] [count]  Same as leaderboard",
        "help_search": "/aoe4 search <keyword>     Search players",
        "help_civ": "/aoe4 civ [name]         Civilization overview (list all if empty)",
        "help_unit": "/aoe4 unit <name>        Query unit data",
        "help_building": "/aoe4 building <name>    Query building data",
        "help_tech": "/aoe4 tech <name>        Query technology data",
        "help_counter": "/aoe4 counter <unit>     Query counter relationships",
        "help_patch": "/aoe4 patch             View latest patch notes",
        "help_game": "/aoe4 game <gameID>     View game by ID\n                      -score for image  -gid/-pid for IDs",

        "section_bind": "📌 Account Binding",
        "section_stats": "📊 Match Stats",
        "section_leaderboard": "🏆 Leaderboard & Search",
        "section_data": "📖 Game Data",
        "section_patch": "📰 Patch Notes",

        # ─── Binding ───
        "not_bind": "You haven't bound an account yet. Use /aoe4 bind <IGN> to bind.",
        "bind_success": "✅ Bound successfully! {country}{name}\nProfile ID: {pid}",
        "unbind_success": "✅ Unbound successfully",
        "unbind_none": "You haven't bound any account yet.",
        "bind_usage": "Usage: /aoe4 bind <IGN>",
        "bindid_usage": "Usage: /aoe4 bindid <Profile ID>",
        "bindid_invalid": "Profile ID must be a number.",
        "bindid_not_found": "Player with profile ID {pid} not found.",
        "bind_multiple": "Found multiple results for「{name}」, please bind using Profile ID:",
        "bind_multiple_hint": "Use /aoe4 bindid <Profile ID> to bind",
        "bind_data_fail": "Bound account: {name} (ID: {pid})\nData query failed, please try again later.",

        # ─── Profile ───
        "profile_title": "📋 {country}{name}  |  ID: {pid}",
        "profile_no_rank": "No ranked data available",

        # ─── Matches ───
        "recent_title": "🎮 {name} - Last {n} Games",
        "recent_empty": "{name} has no recent games.",
        "last_no_game": "No last game data found.",
        "last_no_data": "Could not retrieve your data for this game.",
        "game_usage": "Usage: /aoe4 game <gameID> [-score] [-gid] [-pid]",
        "game_invalid_id": "Game ID must be a number.",
        "game_not_found": "Game {gid} not found.",
        "game_title": "🎮 Game #{gid} | {kind} | {map} | {dur} | {time}{ids}",
        "last_title": "🎮 Last Game | {icon} {result}{ids}",
        "last_line": "  {kind} | {map} | {dur} | {time}",
        "last_civ": "  🏛 {civ} {rd}",
        "last_eco_mil_tech": "  📊 Economy: {eco}  Military: {mil}  Tech: {tech}",
        "score_unavailable": "📊 Score data unavailable, showing lineup:",
        "recent_score_unavailable": "Could not retrieve detailed data",

        # ─── Score Comparison Text ───
        "score_comparison": "📊 Score Comparison",

        # ─── Leaderboard ───
        "leaderboard_no_data": "No leaderboard data available.",
        "lb_rank": "Rank",
        "lb_name": "Player",
        "lb_rating": "Rating",
        "lb_games": "Games",
        "lb_winrate": "Win%",
        "lb_streak": "Streak",

        # ─── Search ───
        "search_usage": "Usage: /aoe4 search <keyword>",
        "search_no_result": "No matching players found.",
        "search_result": "Found {n} matching players:",

        # ─── Game / Last -score fallback ───
        "game_fallback_title": "🎮 Game | {kind} | {map} | {dur} | {time}{ids}",

        # ─── Team Labels ───
        "team_win": "Victor",
        "team_loss": "Defeated",
        "team_blue": "Blue",
        "team_red": "Red",

        # ─── Image Render Titles ───
        "render_score_title": "🎮 {kind} | {map} | {dur}",
        "render_score_subtitle": "⏱ {time} ago",
        "render_analysis_title": "🎙️ Hot Takes",
        "render_analysis_subtitle": "{title} | {subtitle}",

        # ─── Tag Names ───
        "tag_farmer": "🌾 Farm King",
        "tag_farmer_desc": "Farmed {food} food, like a living plantation",
        "tag_economist": "🏠 Economy Master",
        "tag_economist_desc": "Economy score {eco}, quietly getting rich",
        "tag_god": "💀 God of War",
        "tag_god_desc": "KD {kd}, absolutely dominant",
        "tag_muscle": "⚔️ Strongman",
        "tag_muscle_desc": "KD {kd}, crushing the opposition",
        "tag_feeder": "☁️ Feeder King",
        "tag_feeder_desc": "Died {deaths} times, a true vanguard",
        "tag_gifter": "🎁 Charity Giver",
        "tag_gifter_desc": "{deaths} deaths / {kills} kills, a philanthropist",
        "tag_slow": "🐢 Casual Player",
        "tag_slow_desc": "APM {apm}, slow and steady",
        "tag_speed": "⚡ Speed Demon",
        "tag_speed_desc": "APM {apm}, lightning fast reflexes",
        "tag_demolisher": "🏗️ Demolisher",
        "tag_demolisher_desc": "Destroyed {structdmg} buildings",
        "tag_bruteforce": "👊 Pure Strength",
        "tag_bruteforce_desc": "Won without destroying a single building",
        "tag_builder": "🏘️ Construction Maniac",
        "tag_builder_desc": "Built {bprod} structures",
        "tag_techie": "🔬 Tech Geek",
        "tag_techie_desc": "Researched {upg} technologies",
        "tag_brute": "🪓 Brute Force",
        "tag_brute_desc": "Tech? Just smash things",
        "tag_rich": "💰 Resource Baron",
        "tag_rich_desc": "Spent {resources} total resources, an oil tycoon",
        "tag_frugal": "💎 Frugal Player",
        "tag_frugal_desc": "Won with only {resources} resources spent",
        "tag_balanced": "⚖️ Balanced",
        "tag_balanced_desc": "Food/wood/gold all above 15k, all-rounder",
        "tag_social": "🏛️ Social Butterfly",
        "tag_social_desc": "Society score {soc}, the empire's top socialite",
        "tag_popdealer": "👶 Pop Dealer",
        "tag_popdealer_desc": "Produced {sqprod} units",
        "tag_warrior": "🗡️ Warmonger",
        "tag_warrior_desc": "Military score {mil}, lives for war",
        "tag_average": "🤷 Average Joe",
        "tag_average_desc": "Balanced stats, a steady player",

        # ─── ID Suffix ───
        "id_suffix_gid": "GID:{gid}",
        "id_suffix_pid": "PID:{pid}",
        "recent_gids_title": "📋 Recent Game IDs:",

        # ─── Civilization Names ───
        "civ_abbasid": "Abbasid Dynasty",
        "civ_english": "English",
        "civ_chinese": "Chinese",
        "civ_french": "French",
        "civ_hre": "Holy Roman Empire",
        "civ_mongols": "Mongols",
        "civ_rus": "Rus",
        "civ_delhi": "Delhi Sultanate",
        "civ_ottomans": "Ottomans",
        "civ_malians": "Malians",
        "civ_byzantines": "Byzantines",
        "civ_japanese": "Japanese",
        "civ_ayyubids": "Ayyubids",
        "civ_jeanne": "Jeanne d'Arc",
        "civ_dragon": "Order of the Dragon",
        "civ_zhuxi": "Zhu Xi's Legacy",

        # ─── Mode Names ───
        "mode_rm_solo": "1v1 Ranked",
        "mode_rm_2v2": "2v2 Ranked",
        "mode_rm_3v3": "3v3 Ranked",
        "mode_rm_4v4": "4v4 Ranked",
        "mode_rm_team": "Team Ranked",
        "mode_qm_1v1": "1v1 Quick",
        "mode_qm_2v2": "2v2 Quick",
        "mode_qm_3v3": "3v3 Quick",
        "mode_qm_4v4": "4v4 Quick",

        # ─── Unit/Building/Tech Field Labels ───
        "unit_hp": "HP",
        "unit_cost": "Cost",
        "unit_damage": "Damage",
        "unit_armor": "Armor",
        "unit_speed": "Speed",
        "unit_range": "Range",
        "unit_rate": "Attack Speed",
        "unit_bonus": "Bonus Damage",
        "unit_built_by": "Built By",
        "unit_trained_at": "Trained At",
        "unit_requires": "Requires",

        "building_hp": "HP",
        "building_cost": "Cost",
        "building_garrison": "Garrison Capacity",
        "building_influence": "Influence",
        "building_produces": "Produces",

        "tech_effect": "Effect",
        "tech_cost": "Cost",
        "tech_applies_to": "Applies To",
        "tech_researched_at": "Researched At",
        "tech_required_age": "Required Age",

        # ─── Error Messages ───
        "err_not_found_cmd": "Command /aoe4 {sub} help not found.",
        "err_data_query": "Data query failed.",
        "err_network": "Network request failed, please try again later.",
        "err_flaresolverr": "FlareSolverr unavailable.",
    },
}
