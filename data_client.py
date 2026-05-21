import asyncio
import aiohttp
from astrbot.api import logger

DATA_BASE = "https://data.aoe4world.com"
USER_AGENT = "AstrByAOE4SearchView/1.0.0 (QQ bot plugin; contact: @RiyoruAstral)"


CIV_CODE_TO_NAME = {
    "ab": "阿巴斯王朝", "en": "英格兰", "ch": "中国", "fr": "法兰西",
    "hr": "神圣罗马帝国", "mo": "蒙古", "ru": "罗斯", "de": "德里苏丹国",
    "ot": "奥斯曼", "ma": "马里", "by": "拜占庭", "jp": "日本",
    "ay": "阿尤布", "jd": "圣女贞德", "od": "龙骑士团", "zx": "朱熹遗产",
    "vf": "法国变体", "vh": "神圣罗马帝国变体", "va": "阿巴斯变体",
    "vr": "罗斯变体", "vc": "中国变体", "vd": "德里变体", "vm": "蒙古变体",
    "vo": "奥斯曼变体", "vj": "日本变体", "vb": "拜占庭变体",
}

CIV_NAME_TO_CODE = {v: k for k, v in CIV_CODE_TO_NAME.items()}
CIV_NAME_TO_CODE.update({
    "abbasid_dynasty": "ab", "english": "en", "chinese": "ch",
    "french": "fr", "holy_roman_empire": "hr", "mongols": "mo",
    "rus": "ru", "delhi_sultanate": "de", "ottomans": "ot",
    "malians": "ma", "byzantines": "by", "japanese": "jp",
    "ayyubids": "ay", "jeanne_darc": "jd", "order_of_the_dragon": "od",
    "zhu_xis_legacy": "zx",
})

AGE_NAMES = {1: "黑暗时代", 2: "封建时代", 3: "城堡时代", 4: "帝王时代"}

WEAPON_TYPE_LABELS = {"melee": "近战", "ranged": "远程", "siege": "攻城", "fire": "火焰"}

ARMOR_TYPE_LABELS = {"melee": "近战护甲", "ranged": "远程护甲", "fire": "火焰护甲"}


class AoE4DataClient:
    def __init__(self):
        self._session: aiohttp.ClientSession | None = None
        self._units: list[dict] | None = None
        self._buildings: list[dict] | None = None
        self._technologies: list[dict] | None = None
        self._lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={"User-Agent": USER_AGENT})
        return self._session

    async def _fetch_json(self, path: str) -> dict | None:
        session = await self._get_session()
        try:
            async with session.get(f"{DATA_BASE}{path}", timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning(f"AoE4 Data 返回 {resp.status}: {path}")
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f"AoE4 Data 请求失败 {path}: {e}")
            return None

    async def _ensure_loaded(self):
        if self._units is not None:
            return
        async with self._lock:
            if self._units is not None:
                return
            logger.info("正在加载 AoE4 游戏数据...")
            tasks = [
                self._fetch_json("/units/all.json"),
                self._fetch_json("/buildings/all.json"),
                self._fetch_json("/technologies/all.json"),
            ]
            results = await asyncio.gather(*tasks)
            self._units = (results[0] or {}).get("data", [])
            self._buildings = (results[1] or {}).get("data", [])
            self._technologies = (results[2] or {}).get("data", [])
            logger.info(f"AoE4 游戏数据加载完成: {len(self._units)} 单位, {len(self._buildings)} 建筑, {len(self._technologies)} 科技")

    def _match(self, items: list[dict], query: str) -> list[dict]:
        q = query.lower().replace("-", " ").replace("_", " ")
        results = []
        for item in items:
            name = item.get("name", "").lower()
            mid = item.get("id", "").lower().replace("-", " ").replace("_", " ")
            if q in name or q in mid:
                results.append(item)
        return results[:10]

    async def search_units(self, query: str) -> list[dict]:
        await self._ensure_loaded()
        return self._match(self._units, query)

    async def search_buildings(self, query: str) -> list[dict]:
        await self._ensure_loaded()
        return self._match(self._buildings, query)

    async def search_technologies(self, query: str) -> list[dict]:
        await self._ensure_loaded()
        return self._match(self._technologies, query)

    async def get_civ_data(self, civ_code: str) -> dict | None:
        await self._ensure_loaded()
        civ_units = [u for u in self._units if civ_code in u.get("civs", [])]
        civ_buildings = [b for b in self._buildings if civ_code in b.get("civs", [])]
        civ_techs = [t for t in self._technologies if civ_code in t.get("civs", [])]
        if not civ_units and not civ_buildings and not civ_techs:
            return None
        return {"units": civ_units, "buildings": civ_buildings, "technologies": civ_techs}

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


def _format_costs(costs: dict) -> str:
    parts = []
    for r in ("food", "wood", "gold", "stone"):
        v = costs.get(r, 0)
        if v:
            labels = {"food": "食物", "wood": "木材", "gold": "黄金", "stone": "石料"}
            parts.append(f"{labels[r]}{v}")
    time_s = costs.get("time", 0)
    parts.append(f"时间:{time_s}s")
    return " ".join(parts)


def _format_armor(armors: list) -> str:
    if not armors:
        return "无"
    return " ".join(f"{ARMOR_TYPE_LABELS.get(a['type'], a['type'])}:{a['value']}" for a in armors)


def _civs_str(civ_codes: list[str]) -> str:
    names = [CIV_CODE_TO_NAME.get(c, c) for c in civ_codes]
    return ", ".join(names)


def _display_classes(classes: list[str]) -> str:
    return ", ".join(classes) if classes else "无"


def format_unit(unit: dict) -> list[str]:
    lines = [
        f"⚔️ {unit['name']}",
        f"  {_civs_str(unit.get('civs', []))} | {AGE_NAMES.get(unit.get('age'), '?')}",
        f"  类型: {_display_classes(unit.get('displayClasses', []))}",
        f"  生命值: {unit.get('hitpoints', '?')}",
    ]
    desc = unit.get("description", "")
    if desc:
        lines.append(f"  描述: {desc.replace(chr(10), ' ')}")
    costs = unit.get("costs", {})
    lines.append(f"  造价: {_format_costs(costs)}")
    movement = unit.get("movement", {})
    if movement:
        lines.append(f"  移动速度: {movement.get('speed', '?')}")
    weapons = unit.get("weapons", [])
    if weapons:
        w = weapons[0]
        wt = WEAPON_TYPE_LABELS.get(w.get("type", ""), w.get("type", ""))
        dmg = w.get("damage", "?")
        spd = w.get("speed", "?")
        rng = w.get("range", {})
        rng_str = f" 射程:{rng.get('min', 0)}-{rng.get('max', 0)}" if rng.get("max") else ""
        lines.append(f"  武器: {wt} 伤害:{dmg} 速度:{spd}s{rng_str}")
        if len(weapons) > 1:
            lines.append(f"  副武器: {weapons[1].get('name', '?')} 伤害:{weapons[1].get('damage', '?')}")
    armor = unit.get("armor", [])
    lines.append(f"  护甲: {_format_armor(armor)}")
    produced = unit.get("producedBy", [])
    if produced:
        lines.append(f"  生产建筑: {', '.join(produced)}")
    unique = unit.get("unique", False)
    if unique:
        lines.append(f"  ⭐ 特色单位")
    return lines


def format_building(building: dict) -> list[str]:
    lines = [
        f"🏛️ {building['name']}",
        f"  {_civs_str(building.get('civs', []))} | {AGE_NAMES.get(building.get('age'), '?')}",
        f"  类型: {_display_classes(building.get('displayClasses', []))}",
        f"  生命值: {building.get('hitpoints', '?')}",
    ]
    desc = building.get("description", "")
    if desc:
        lines.append(f"  描述: {desc}")
    costs = building.get("costs", {})
    lines.append(f"  造价: {_format_costs(costs)}")
    armor = building.get("armor", [])
    lines.append(f"  护甲: {_format_armor(armor)}")
    garrison = building.get("garrison", {})
    if garrison:
        cap = garrison.get("capacity", 0)
        if cap:
            lines.append(f"  驻军容量: {cap}")
    influences = building.get("influences", [])
    if influences:
        lines.append(f"  影响: {influences[0].replace(chr(10), ' ')}")
    unique = building.get("unique", False)
    if unique:
        lines.append(f"  ⭐ 特色建筑")
    return lines


def format_technology(tech: dict) -> list[str]:
    lines = [
        f"🔬 {tech['name']}",
        f"  {_civs_str(tech.get('civs', []))} | {AGE_NAMES.get(tech.get('age'), '?')}",
        f"  类别: {_display_classes(tech.get('displayClasses', []))}",
    ]
    desc = tech.get("description", "")
    if desc:
        lines.append(f"  效果: {desc}")
    costs = tech.get("costs", {})
    lines.append(f"  造价: {_format_costs(costs)}")
    produced = tech.get("producedBy", [])
    if produced:
        lines.append(f"  研发建筑: {', '.join(produced)}")
    unique = tech.get("unique", False)
    if unique:
        lines.append(f"  ⭐ 特色科技")
    return lines
