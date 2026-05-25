import asyncio
import aiohttp
from astrbot.api import logger

DATA_BASE = "https://data.aoe4world.com"
USER_AGENT = "astrbot-plugin-aoe4/1.1.0 (QQ bot plugin; contact: @RiyoruAstral)"

CIV_NAME_TO_CODE = {
    "abbasid_dynasty": "ab", "english": "en", "chinese": "ch",
    "french": "fr", "holy_roman_empire": "hr", "mongols": "mo",
    "rus": "ru", "delhi_sultanate": "de", "ottomans": "ot",
    "malians": "ma", "byzantines": "by", "japanese": "jp",
    "ayyubids": "ay", "jeanne_darc": "jd", "order_of_the_dragon": "od",
    "zhu_xis_legacy": "zx",
    "jin_dynasty": "ji",
    "golden_horde": "gh",
    "sengoku_daimyo": "sg",
    "knights_templar": "kt",
    "house_of_lancaster": "hl",
    "macedonian_dynasty": "md",
    "阿巴斯王朝": "ab", "英格兰": "en", "中国": "ch", "法兰西": "fr",
    "神圣罗马帝国": "hr", "蒙古": "mo", "罗斯": "ru", "德里苏丹国": "de",
    "奥斯曼": "ot", "马里": "ma", "拜占庭": "by", "日本": "jp",
    "阿尤布": "ay", "圣女贞德": "jd", "龙骑士团": "od", "朱熹遗产": "zx",
    "金朝": "ji",
    "战国大名": "sg",
    "圣殿骑士团": "kt",
    "兰开斯特王朝": "hl",
    "马其顿王朝": "md",
}

CIV_CODE_TO_NAME = {
    "ab": "阿巴斯王朝", "en": "英格兰", "ch": "中国", "fr": "法兰西",
    "hr": "神圣罗马帝国", "mo": "蒙古", "ru": "罗斯", "de": "德里苏丹国",
    "ot": "奥斯曼", "ma": "马里", "by": "拜占庭", "jp": "日本",
    "ay": "阿尤布", "jd": "圣女贞德", "od": "龙骑士团", "zx": "朱熹遗产",
    "ji": "金朝",
    "gh": "金朝",
    "sg": "战国大名",
    "kt": "圣殿骑士团",
    "hl": "兰开斯特王朝",
    "md": "马其顿王朝",
    "vf": "法国变体", "vh": "神圣罗马帝国变体", "va": "阿巴斯变体",
    "vr": "罗斯变体", "vc": "中国变体", "vd": "德里变体", "vm": "蒙古变体",
    "vo": "奥斯曼变体", "vj": "日本变体", "vb": "拜占庭变体",
}


class AoE4DataClient:
    def __init__(self, translator=None):
        self._session: aiohttp.ClientSession | None = None
        self._units: list[dict] | None = None
        self._buildings: list[dict] | None = None
        self._technologies: list[dict] | None = None
        self._lock = asyncio.Lock()
        self.tr = translator

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={"User-Agent": USER_AGENT})
        return self._session

    async def _fetch_json(self, path: str) -> dict | None:
        session = await self._get_session()
        try:
            async with session.get(f"{DATA_BASE}{path}", timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning(f"AoE4 Data returned {resp.status}: {path}")
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f"AoE4 Data request failed {path}: {e}")
            return None

    async def _ensure_loaded(self):
        if self._units is not None:
            return
        async with self._lock:
            if self._units is not None:
                return
            label = self.tr.t("loading_data") if self.tr else "Loading AoE4 game data..."
            logger.info(label)
            tasks = [
                self._fetch_json("/units/all.json"),
                self._fetch_json("/buildings/all.json"),
                self._fetch_json("/technologies/all.json"),
            ]
            results = await asyncio.gather(*tasks)
            self._units = (results[0] or {}).get("data", [])
            self._buildings = (results[1] or {}).get("data", [])
            self._technologies = (results[2] or {}).get("data", [])
            done = self.tr.t("data_loaded") if self.tr else "Game data loaded"
            logger.info(f"{done}: {len(self._units)} units, {len(self._buildings)} buildings, {len(self._technologies)} techs")

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

    async def get_counter_info(self, query: str) -> dict | None:
        await self._ensure_loaded()
        results = self._match(self._units, query)
        if not results:
            return None
        unit = results[0]
        unit_classes = set(unit.get("displayClasses", []))
        counters = []
        for w in unit.get("weapons", []):
            for mod in w.get("modifiers", []):
                target = mod.get("target", {})
                target_classes = target.get("displayClasses", [])
                bonus = mod.get("damage", 0)
                if target_classes and bonus > 0:
                    counters.append({
                        "classes": target_classes,
                        "bonus_damage": bonus,
                        "weapon_type": w.get("type", mod.get("type", "")),
                    })
        countered_by = []
        for other in self._units:
            if other["id"] == unit["id"]:
                continue
            other_classes = set(other.get("displayClasses", []))
            for w in other.get("weapons", []):
                for mod in w.get("modifiers", []):
                    target = mod.get("target", {})
                    target_classes = target.get("displayClasses", [])
                    bonus = mod.get("damage", 0)
                    if target_classes and bonus > 0 and unit_classes & set(target_classes):
                        countered_by.append({
                            "unit": other["name"],
                            "classes": target_classes,
                            "bonus_damage": bonus,
                        })
                        break
                if countered_by and countered_by[-1].get("unit") == other["name"]:
                    continue
        return {
            "unit": unit,
            "counters": counters,
            "countered_by": countered_by,
        }

    # ─── Localized formatting methods ───

    def _t(self, section: str, key: str, fallback: str = "") -> str:
        if self.tr:
            return getattr(self.tr, section, lambda k, f: self.tr.t(k, default=f))(key, fallback)
        return fallback or key

    def _civ_name(self, code: str) -> str:
        return self.tr.civ(code) if self.tr else code

    def _age_name(self, age: int | str | None) -> str:
        return self.tr.age(age) if self.tr else str(age or "?")

    def _weapon_type(self, t: str) -> str:
        return self.tr.weapon_type(t) if self.tr else t

    def _armor_type(self, t: str) -> str:
        return self.tr.armor_type(t) if self.tr else t

    def _class_label(self, cls: str) -> str:
        return self.tr.display_class(cls) if self.tr else cls

    def _resource_label(self, r: str) -> str:
        return self.tr.resource(r) if self.tr else r

    def _costs_str(self, costs: dict) -> str:
        parts = []
        for r in ("food", "wood", "gold", "stone"):
            v = costs.get(r, 0)
            if v:
                parts.append(f"{self._resource_label(r)}{v}")
        time_s = costs.get("time", 0)
        if self.tr:
            parts.append(f"{self.tr.resource('time')}:{time_s}s")
        else:
            parts.append(f"Time:{time_s}s")
        return " ".join(parts)

    def _armor_str(self, armors: list) -> str:
        if not armors:
            return self.tr.game_label("none") if self.tr else "无"
        return " ".join(f"{self._armor_type(a['type'])}:{a['value']}" for a in armors)

    def _civs_str(self, civ_codes: list[str]) -> str:
        names = [self._civ_name(c) for c in civ_codes]
        return ", ".join(names)

    def _display_classes_str(self, classes: list[str]) -> str:
        if not classes:
            return self.tr.game_label("none") if self.tr else "无"
        return ", ".join(self._class_label(c) for c in classes)

    def format_unit(self, unit: dict) -> list[str]:
        hp = unit.get("hitpoints", "?")
        lines = [
            f"⚔️ {unit['name']}",
            f"  {self._civs_str(unit.get('civs', []))} | {self._age_name(unit.get('age', '?'))}",
            f"  {self.tr.unit_field('type') if self.tr else '类型'}: {self._display_classes_str(unit.get('displayClasses', []))}",
            f"  {self.tr.unit_field('hp') if self.tr else '生命值'}: {hp}",
        ]
        desc = unit.get("description", "")
        if desc:
            lines.append(f"  {self.tr.unit_field('description') if self.tr else '描述'}: {desc.replace(chr(10), ' ')}")
        costs = unit.get("costs", {})
        lines.append(f"  {self.tr.unit_field('cost') if self.tr else '造价'}: {self._costs_str(costs)}")
        movement = unit.get("movement", {})
        if movement:
            spd = movement.get("speed", "?")
            lines.append(f"  {self.tr.unit_field('speed') if self.tr else '移动速度'}: {spd}")
        weapons = unit.get("weapons", [])
        if weapons:
            w = weapons[0]
            wt = self._weapon_type(w.get("type", ""))
            dmg = w.get("damage", "?")
            spd = w.get("speed", "?")
            rng = w.get("range", {})
            rng_label = self.tr.unit_field("range") if self.tr else "射程"
            rng_str = f" {rng_label}:{rng.get('min', 0)}-{rng.get('max', 0)}" if rng.get("max") else ""
            lines.append(f"  {self.tr.unit_field('weapon') if self.tr else '武器'}: {wt} {self.tr.unit_field('damage') if self.tr else '伤害'}:{dmg} {self.tr.unit_field('attack_speed') if self.tr else '速度'}:{spd}s{rng_str}")
            if len(weapons) > 1:
                lines.append(f"  {self.tr.unit_field('secondary_weapon') if self.tr else '副武器'}: {weapons[1].get('name', '?')} {self.tr.unit_field('damage') if self.tr else '伤害'}:{weapons[1].get('damage', '?')}")
        armor = unit.get("armor", [])
        lines.append(f"  {self.tr.unit_field('armor') if self.tr else '护甲'}: {self._armor_str(armor)}")
        produced = unit.get("producedBy", [])
        if produced:
            prod_label = self.tr.unit_field("production_building") if self.tr else "生产建筑"
            lines.append(f"  {prod_label}: {', '.join(produced)}")
        unique = unit.get("unique", False)
        if unique:
            lines.append(f"  ⭐ {self.tr.unit_field('unique_unit') if self.tr else '特色单位'}")
        return lines

    def format_building(self, building: dict) -> list[str]:
        lines = [
            f"🏛️ {building['name']}",
            f"  {self._civs_str(building.get('civs', []))} | {self._age_name(building.get('age', '?'))}",
            f"  {self.tr.unit_field('type') if self.tr else '类型'}: {self._display_classes_str(building.get('displayClasses', []))}",
            f"  {self.tr.building_field('hp') if self.tr else '生命值'}: {building.get('hitpoints', '?')}",
        ]
        desc = building.get("description", "")
        if desc:
            lines.append(f"  {self.tr.unit_field('description') if self.tr else '描述'}: {desc}")
        costs = building.get("costs", {})
        lines.append(f"  {self.tr.building_field('cost') if self.tr else '造价'}: {self._costs_str(costs)}")
        armor = building.get("armor", [])
        lines.append(f"  {self.tr.building_field('armor') if self.tr else '护甲'}: {self._armor_str(armor)}")
        garrison = building.get("garrison", {})
        if garrison:
            cap = garrison.get("capacity", 0)
            if cap:
                lines.append(f"  {self.tr.building_field('garrison_capacity') if self.tr else '驻军容量'}: {cap}")
        influences = building.get("influences", [])
        if influences:
            lines.append(f"  {self.tr.building_field('influence') if self.tr else '影响'}: {influences[0].replace(chr(10), ' ')}")
        unique = building.get("unique", False)
        if unique:
            lines.append(f"  ⭐ {self.tr.building_field('unique_building') if self.tr else '特色建筑'}")
        return lines

    def format_technology(self, tech: dict) -> list[str]:
        lines = [
            f"🔬 {tech['name']}",
            f"  {self._civs_str(tech.get('civs', []))} | {self._age_name(tech.get('age', '?'))}",
            f"  {self.tr.tech_field('category') if self.tr else '类别'}: {self._display_classes_str(tech.get('displayClasses', []))}",
        ]
        desc = tech.get("description", "")
        if desc:
            lines.append(f"  {self.tr.tech_field('effect') if self.tr else '效果'}: {desc}")
        costs = tech.get("costs", {})
        lines.append(f"  {self.tr.tech_field('cost') if self.tr else '造价'}: {self._costs_str(costs)}")
        produced = tech.get("producedBy", [])
        if produced:
            prod_label = self.tr.tech_field("researched_at") if self.tr else "研发建筑"
            lines.append(f"  {prod_label}: {', '.join(produced)}")
        unique = tech.get("unique", False)
        if unique:
            lines.append(f"  ⭐ {self.tr.tech_field('unique_tech') if self.tr else '特色科技'}")
        return lines

    def format_counter_info(self, info: dict) -> list[str]:
        unit = info["unit"]
        counters = info["counters"]
        countered_by = info["countered_by"]
        lines = [f"⚔️ {unit['name']} {self.tr.game_label('counter_title') if self.tr else '克制关系'}"]
        if counters:
            for c in counters:
                cls_names = ", ".join(self._class_label(cl) for cl in c["classes"])
                lines.append(f"  🔼 {self.tr.game_label('counters') if self.tr else '克制'} {cls_names} (+{c['bonus_damage']} {c['weapon_type']})")
        else:
            lines.append(f"  {self.tr.game_label('no_counters') if self.tr else '无明显克制关系'}")
        if countered_by:
            seen_units = set()
            for cb in countered_by:
                if cb["unit"] not in seen_units:
                    seen_units.add(cb["unit"])
                    lines.append(f"  🔽 {self.tr.game_label('countered_by') if self.tr else '被'} {cb['unit']} {self.tr.game_label('countered') if self.tr else '克制'}")
        else:
            lines.append(f"  {self.tr.game_label('no_countered_by') if self.tr else '无明显被克制关系'}")
        desc = unit.get("description", "")
        if desc:
            lines.append(f"  💡 {desc.replace(chr(10), ' ')}")
        return lines
