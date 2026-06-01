import asyncio
import json
import os
import re
import time
import aiohttp
from astrbot.api import logger

DATA_BASE = "https://data.aoe4world.com"
USER_AGENT = "astrbot_plugin_aoe4/1.1.0 (QQ bot plugin; contact: @RiyoruAstral)"
_TECH_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tech_data")

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
    "tughlaq_dynasty": "td",
    "阿巴斯王朝": "ab", "英格兰": "en", "中国": "ch", "法兰西": "fr",
    "神圣罗马帝国": "hr", "蒙古": "mo", "罗斯": "ru", "德里苏丹国": "de",
    "奥斯曼": "ot", "马里": "ma", "拜占庭": "by", "日本": "jp",
    "阿尤布": "ay", "圣女贞德": "jd", "龙骑士团": "od", "朱熹遗产": "zx",
    "金朝": "ji",
    "金账汗国": "gh",
    "战国大名": "sg",
    "圣殿骑士团": "kt",
    "兰开斯特王朝": "hl",
    "马其顿王朝": "md",
    "图格鲁克王朝": "td",
}

CIV_CODE_TO_NAME = {
    "ab": "阿巴斯王朝", "en": "英格兰", "ch": "中国", "fr": "法兰西",
    "hr": "神圣罗马帝国", "mo": "蒙古", "ru": "罗斯", "de": "德里苏丹国",
    "ot": "奥斯曼", "ma": "马里", "by": "拜占庭", "jp": "日本",
    "ay": "阿尤布", "jd": "圣女贞德", "od": "龙骑士团", "zx": "朱熹遗产",
    "ji": "金朝",
    "gh": "金账汗国",
    "sg": "战国大名",
    "kt": "圣殿骑士团",
    "hl": "兰开斯特王朝",
    "md": "马其顿王朝",
    "td": "图格鲁克王朝",
    "vf": "法国变体", "vh": "神圣罗马帝国变体", "va": "阿巴斯变体",
    "vr": "罗斯变体", "vc": "中国变体", "vd": "德里变体", "vm": "蒙古变体",
    "vo": "奥斯曼变体", "vj": "日本变体", "vb": "拜占庭变体",
}


class TechDataManager:
    def __init__(self, data_dir: str, tr):
        self._data_dir = data_dir
        self._tr = tr
        self._overrides: dict = {}
        self._civ_overrides: dict[str, dict] = {}
        self._loaded_at: float = 0.0

    def load(self):
        now = time.monotonic()
        if self._overrides and (now - self._loaded_at) < 60:
            return
        self._overrides = {}
        self._civ_overrides = {}
        path = os.path.join(self._data_dir, "overrides.json")
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self._overrides = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"tech_data overrides.json 加载失败: {e}")
        civ_dir = os.path.join(self._data_dir, "civ_overrides")
        if os.path.exists(civ_dir):
            for fname in os.listdir(civ_dir):
                if not fname.endswith(".json"):
                    continue
                civ_code = fname.replace(".json", "")
                try:
                    with open(os.path.join(civ_dir, fname), encoding="utf-8") as f:
                        self._civ_overrides[civ_code] = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"tech_data {fname} 加载失败: {e}")
        self._loaded_at = now

    def apply_exclude_techs(self, unit_id: str, tech_ids: list[str]) -> list[str]:
        excludes = self._overrides.get("exclude_techs", {}).get(unit_id, {}).get("tech_ids", [])
        if not excludes:
            return tech_ids
        return [tid for tid in tech_ids if tid not in excludes]

    def get_force_techs(self, unit_id: str) -> list[str]:
        return self._overrides.get("force_techs", {}).get(unit_id, {}).get("tech_ids", [])

    def get_name_override(self, unit_id: str) -> str | None:
        return self._overrides.get("unit_name_overrides", {}).get(unit_id)

    def get_civ_techs(self, unit_id: str, civ_code: str) -> dict | None:
        civ_data = self._civ_overrides.get(civ_code)
        if not civ_data:
            return None
        return civ_data.get("units", {}).get(unit_id)


class AoE4DataClient:
    def __init__(self, translator=None, cache_ttl: int = 86400):
        self._session: aiohttp.ClientSession | None = None
        self._units: list[dict] | None = None
        self._buildings: list[dict] | None = None
        self._technologies: list[dict] | None = None
        self._lock = asyncio.Lock()
        self._data_loaded_at: float = 0.0
        self._cache_ttl = cache_ttl
        self.tr = translator
        self._tech_data = TechDataManager(_TECH_DATA_DIR, translator)

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
        now = time.monotonic()
        if self._units is not None and self._cache_ttl > 0 and (now - self._data_loaded_at) < self._cache_ttl:
            return
        async with self._lock:
            if self._units is not None and self._cache_ttl > 0 and (now - self._data_loaded_at) < self._cache_ttl:
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
            self._normalize_display_classes()
            self._data_loaded_at = time.monotonic()
            self._tech_data.load()
            done = self.tr.t("data_loaded") if self.tr else "Game data loaded"
            logger.info(f"{done}: {len(self._units)} units, {len(self._buildings)} buildings, {len(self._technologies)} techs")

    def _normalize_display_classes(self):
        for lst in (self._units, self._buildings, self._technologies):
            if not lst:
                continue
            for item in lst:
                dcs = item.get("displayClasses")
                if dcs:
                    item["displayClasses"] = ["".join(dc.split()) for dc in dcs]
                for w in item.get("weapons") or []:
                    if not w:
                        continue
                    for m in w.get("modifiers") or []:
                        target = m.get("target", {})
                        classes = target.get("class")
                        if classes:
                            target["displayClasses"] = self._normalize_class_list(classes)
                        if m.get("damage") is None:
                            m["damage"] = 0

    @staticmethod
    def _normalize_class_list(classes: list) -> list[str]:
        result = []
        for cls in classes:
            if isinstance(cls, list):
                parts = [p.capitalize() for p in cls]
                result.append("".join(parts))
            else:
                result.append("".join(cls.split()))
        return result

    def _match(self, items: list[dict], query: str) -> list[dict]:
        q = query.lower().replace("-", " ").replace("_", " ")
        results = []
        for item in items:
            name = item.get("name", "")
            name_lower = name.lower()
            mid = item.get("id", "").lower().replace("-", " ").replace("_", " ")
            if q in name_lower or q in mid:
                results.append(item)
                continue
            if self.tr:
                for section_fn in (self.tr.unit, self.tr.building, self.tr.tech):
                    tname = section_fn(name).lower()
                    if tname != name_lower and q in tname:
                        results.append(item)
                        break
                    tname = section_fn(name.lower()).lower()
                    if tname != name_lower and q in tname:
                        results.append(item)
                        break
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
        data = await self.get_counter_image_data(query)
        if not data:
            return None
        variant = data["variants"][0]
        counters = variant.get("counters", [])
        countered_by = variant.get("countered_by", [])
        return {
            "unit": variant["_raw"],
            "counters": counters,
            "countered_by": countered_by,
        }

    async def get_counter_image_data(self, query: str) -> dict | None:
        """返回所有时代变体的结构化克制数据，供图片渲染使用"""
        await self._ensure_loaded()
        results = self._match(self._units, query)
        if not results:
            return None
        groups = self._group_variants(results)
        if not groups:
            return None
        main_unit = groups[0][0]
        variants = []
        for unit in groups[0]:
            counters = self._extract_counters(unit)
            countered_by = self._extract_countered_by(unit, self._units)
            tech_groups = self.get_affecting_techs(unit)
            variants.append({
                "unit_id": unit["id"],
                "name": self._unit_name(unit) if self.tr else unit.get("name", ""),
                "age": unit.get("age", 0),
                "hp": unit.get("hitpoints"),
                "attack": self._get_attack(unit),
                "range": self._get_range(unit),
                "display_class": self._display_classes_str(unit.get("displayClasses", [])),
                "counters": counters,
                "countered_by": countered_by,
                "tech_groups": tech_groups,
                "_raw": unit,
            })
        return {
            "unit_name": self._unit_name(main_unit) if self.tr else main_unit.get("name", ""),
            "unit_class": self._display_classes_str(main_unit.get("displayClasses", [])),
            "variants": variants,
            "description": main_unit.get("description", ""),
        }

    @staticmethod
    def _get_base_id(unit_id: str) -> str:
        return re.sub(r"-\d+$", "", unit_id)

    def _group_variants(self, results: list[dict]) -> list[list[dict]]:
        base_map: dict[str, list[dict]] = {}
        for unit in results:
            base = self._get_base_id(unit.get("id", ""))
            if base not in base_map:
                base_map[base] = []
            base_map[base].append(unit)
        groups = sorted(base_map.values(), key=lambda g: g[0].get("age", 0))
        result = []
        for g in groups:
            civs = set(tuple(u.get("civs", [])) for u in g)
            most_common_civ = max(civs, key=lambda c: sum(1 for u in g if u.get("civs", []) == list(c)))
            civ_list = list(most_common_civ)
            deduped = [u for u in g if u.get("civs", []) == civ_list]
            result.append(sorted(deduped, key=lambda u: u.get("age", 0)))
        return result

    def _extract_counters(self, unit: dict) -> list[dict]:
        counters = []
        for w in unit.get("weapons") or []:
            for mod in w.get("modifiers") or []:
                target = mod.get("target", {})
                target_classes = target.get("displayClasses", [])
                bonus = mod.get("damage", 0)
                if target_classes and bonus > 0:
                    counters.append({
                        "classes": target_classes,
                        "bonus_damage": bonus,
                        "weapon_type": w.get("type", mod.get("type", "")),
                    })
        return counters

    def _extract_countered_by(self, unit: dict, all_units: list[dict]) -> list[dict]:
        unit_classes = set(unit.get("displayClasses", []))
        countered_by = []
        for other in all_units:
            if other["id"] == unit["id"]:
                continue
            for w in other.get("weapons") or []:
                for mod in w.get("modifiers") or []:
                    target = mod.get("target", {})
                    target_classes = target.get("displayClasses", [])
                    bonus = mod.get("damage", 0)
                    if target_classes and bonus > 0 and unit_classes & set(target_classes):
                        countered_by.append({
                            "unit": self._unit_name(other),
                            "classes": target_classes,
                            "bonus_damage": bonus,
                        })
                        break
                if countered_by and countered_by[-1].get("unit") == other["name"]:
                    continue
        return countered_by

    @staticmethod
    def _get_attack(unit: dict) -> int | None:
        weapons = unit.get("weapons") or []
        if weapons:
            return weapons[0].get("damage")
        return None

    @staticmethod
    def _get_range(unit: dict) -> str | None:
        weapons = unit.get("weapons") or []
        if weapons:
            rng = weapons[0].get("range", {})
            if rng and rng.get("max"):
                return f"{rng.get('min', 0)}-{rng['max']}"
        return None

    def _group_techs_by_building(self, techs: list[dict]) -> list[dict]:
        """将科技按研发建筑分组"""
        groups: dict[str, list[dict]] = {}
        for t in techs:
            produced_by = t.get("producedBy", [])
            building_id = produced_by[0] if produced_by else "other"
            if building_id not in groups:
                groups[building_id] = []
            groups[building_id].append(t)
        result = []
        for bid, items in groups.items():
            result.append({
                "building_id": bid,
                "building_name": self.tr.building(bid) if self.tr else bid,
                "techs": sorted(items, key=lambda t: t.get("age", 0)),
            })
        return result

    def get_affecting_techs(self, unit: dict) -> list[dict]:
        results = []
        for tech in self._technologies:
            match_type = self._match_tech_to_unit(unit, tech)
            if match_type:
                results.append({"tech": tech, "match_type": match_type})
        filtered = self._filter_techs(unit, results)

        base_id = self._get_base_id(unit.get("id", ""))
        matched_ids = [f["tech"]["id"] for f in filtered]
        matched_ids = self._tech_data.apply_exclude_techs(base_id, matched_ids)

        force_ids = self._tech_data.get_force_techs(base_id)
        seen = set(matched_ids)
        final_techs = [t for t in self._technologies if t.get("id") in matched_ids]
        for tid in force_ids:
            if tid not in seen:
                for t in self._technologies:
                    if t.get("id") == tid:
                        final_techs.append(t)
                        seen.add(tid)
                        break
        return self._group_techs_by_building(final_techs)

    def _match_tech_to_unit(self, unit: dict, tech: dict) -> str | None:
        if self._display_classes_match(unit, tech):
            return "exact"
        if self._infer_from_produced_by(unit, tech):
            return "inferred"
        if self._match_unique_by_civ(unit, tech):
            return "inferred"
        return None

    @staticmethod
    def _display_classes_match(unit: dict, tech: dict) -> bool:
        unit_classes = set(unit.get("displayClasses", []))
        tech_classes = set(tech.get("displayClasses", []))
        if not tech_classes:
            return False
        return bool(unit_classes & tech_classes)

    def _infer_from_produced_by(self, unit: dict, tech: dict) -> bool:
        produced_by = tech.get("producedBy", [])
        desc = tech.get("description", "").lower()
        affected = self._infer_affected_classes(produced_by, desc)
        if not affected:
            return False
        unit_classes = set(unit.get("displayClasses", []))
        return bool(unit_classes & set(affected))

    @staticmethod
    def _infer_affected_classes(produced_by: list[str], desc: str) -> list[str]:
        desc = desc.lower()
        if "blacksmith" in produced_by:
            if "ranged" in desc:
                return ["LightRangedInfantry", "HeavyRangedInfantry"]
            if "melee" in desc:
                return ["LightMeleeInfantry", "HeavyMeleeInfantry"]
            if "cavalry" in desc:
                return ["LightMeleeCavalry", "HeavyMeleeCavalry",
                        "LightRangedCavalry", "HeavyRangedCavalry"]
            return []
        if "university" in produced_by:
            if "siege" in desc:
                return ["Siege"]
            if "arrow" in desc or "ship" in desc:
                return ["Ship"]
            return []
        if "dock" in produced_by:
            return ["Ship"]
        return []

    def _match_unique_by_civ(self, unit: dict, tech: dict) -> bool:
        if not tech.get("unique"):
            return False
        if not set(unit.get("civs", [])) & set(tech.get("civs", [])):
            return False
        tech_classes = tech.get("displayClasses")
        if tech_classes:
            return bool(set(unit.get("displayClasses", [])) & set(tech_classes))
        return True

    @staticmethod
    def _filter_techs(unit: dict, techs: list[dict]) -> list[dict]:
        unit_age = unit.get("age", 0)
        seen_ids = set()
        result = []
        for item in techs:
            tech = item["tech"]
            tid = tech.get("id", "")
            if tid in seen_ids:
                continue
            if tech.get("age", 0) > unit_age:
                continue
            seen_ids.add(tid)
            result.append(item)
        return result

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
        weapons = unit.get("weapons") or []
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
        unit_name = self._unit_name(unit) if self.tr else unit.get("name", "")
        lines = [f"⚔️ {unit_name} {self.tr.game_label('counter_title') if self.tr else '克制关系'}"]
        if counters:
            for c in counters:
                cls_names = ", ".join(self._class_label(cl) for cl in c["classes"])
                dmg_str = f" (+{c['bonus_damage']} {c['weapon_type']})" if c.get("bonus_damage") else ""
                lines.append(f"  🔼 {self.tr.game_label('counters') if self.tr else '克制'} {cls_names}{dmg_str}")
        elif not countered_by:
            desc = unit.get("description", "")
            if desc:
                lines.append(f"  💡 {self._translate_description(desc)}")
            return lines
        else:
            lines.append(f"  {self.tr.game_label('no_counters') if self.tr else '无明显克制关系'}")
        if countered_by:
            seen_units = set()
            for cb in countered_by:
                cb_name = self.tr.unit(cb["unit"]) if self.tr else cb["unit"]
                if cb_name not in seen_units:
                    seen_units.add(cb_name)
                    dmg_str = f" (+{cb['bonus_damage']})" if cb.get("bonus_damage") else ""
                    lines.append(f"  🔽 {self.tr.game_label('countered_by') if self.tr else '被'} {cb_name}{dmg_str} {self.tr.game_label('countered') if self.tr else '克制'}")
        else:
            lines.append(f"  {self.tr.game_label('no_countered_by') if self.tr else '无明显被克制关系'}")
        desc = unit.get("description", "")
        if desc:
            lines.append(f"  💡 {self._translate_description(desc)}")
        return lines

    def _unit_name(self, unit: dict) -> str:
        name = unit.get("name", "")
        if not self.tr:
            return name
        result = self.tr.unit(name)
        if result != name:
            return result
        result = self.tr.unit(name.lower())
        if result != name.lower():
            return result
        unit_id = unit.get("id", "")
        base = self._get_base_id(unit_id)
        override = self._tech_data.get_name_override(base)
        if override:
            return override
        age = unit.get("age", 0)
        old_key = self._old_format_key(base, age)
        if old_key:
            result = self.tr.unit(old_key)
            if result != old_key:
                return result
        return name

    @staticmethod
    def _old_format_key(base: str, age: int) -> str:
        if age <= 2:
            return base
        if age == 3:
            return f"veteran-{base}"
        if age >= 4:
            return f"elite-{base}"
        return base

    def _translate_description(self, desc: str) -> str:
        if not self.tr:
            return desc.replace(chr(10), " ")
        text = desc.replace(chr(10), " ")
        text = self._translate_countered_by(text)
        text = self._translate_vs_patterns(text)
        text = self._replace_keywords(text)
        return text

    def _translate_countered_by(self, text: str) -> str:
        m = re.search(r'(?:-\s*)?Countered\s+by\s+(\w[\w\s-]*)', text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip().rstrip(".")
            translated = self._find_unit_name(raw)
            text = text[:m.start()] + f"被 {translated} 克制" + text[m.end():]
        return text

    def _translate_vs_patterns(self, text: str) -> str:
        text = re.sub(
            r'\bGood\s+damage\s+vs\.?\s+(\w[\w\s]*)',
            lambda m: f"高伤害对抗 {self._replace_keywords(m.group(1).strip())}",
            text, flags=re.IGNORECASE
        )
        text = re.sub(
            r'\bGood\s+vs\.?\s+(\w[\w\s]*)',
            lambda m: f"擅长对抗 {self._replace_keywords(m.group(1).strip())}",
            text, flags=re.IGNORECASE
        )
        text = re.sub(
            r'\b(?:Weak|Ineffective)\s+against\s+(\w[\w\s]*)',
            lambda m: f"对 {self._replace_keywords(m.group(1).strip())} 较弱",
            text, flags=re.IGNORECASE
        )
        text = re.sub(
            r'\b(?:Weak|Ineffective)\s+vs\.?\s+(\w[\w\s]*)',
            lambda m: f"对 {self._replace_keywords(m.group(1).strip())} 较弱",
            text, flags=re.IGNORECASE
        )
        return text

    def _find_unit_name(self, raw: str) -> str:
        raw_lower = raw.lower().strip().rstrip(".")
        if not raw_lower or not self._units:
            return raw
        raw_singular = raw_lower.rstrip("s")
        raw_singular = raw_singular.replace("men", "man")
        for unit in self._units:
            uid = unit.get("id", "").lower()
            uname = unit.get("name", "").lower()
            if raw_lower == uname or raw_lower == uid:
                return self.tr.unit(unit["name"])
            if raw_singular == uname or raw_singular == uid:
                return self.tr.unit(unit["name"])
            if uname.startswith(raw_lower) or uid.startswith(raw_lower):
                return self.tr.unit(unit["name"])
        return self.tr.counter_keyword(raw) if self.tr.counter_keyword(raw) != raw else raw

    def _replace_keywords(self, text: str) -> str:
        if not self.tr:
            return text
        result = text
        result = re.sub(r'\brate of fire\b', self.tr.counter_keyword("rate of fire"), result, flags=re.IGNORECASE)
        result = re.sub(r'\battack speed\b', self.tr.counter_keyword("attack speed"), result, flags=re.IGNORECASE)
        result = re.sub(r'\bmovement speed\b', self.tr.counter_keyword("movement speed"), result, flags=re.IGNORECASE)
        result = re.sub(r'\branged armor\b', self.tr.counter_keyword("ranged armor"), result, flags=re.IGNORECASE)
        result = re.sub(r'\bmelee armor\b', self.tr.counter_keyword("melee armor"), result, flags=re.IGNORECASE)
        result = re.sub(r'\btarget(?:s)?\b', self.tr.counter_keyword("targets"), result, flags=re.IGNORECASE)
        result = re.sub(r'\bunarmored\b', self.tr.counter_keyword("unarmored"), result, flags=re.IGNORECASE)
        result = re.sub(r'\barmored\b', self.tr.counter_keyword("armored"), result, flags=re.IGNORECASE)
        result = re.sub(r'\branged\b', self.tr.counter_keyword("ranged"), result, flags=re.IGNORECASE)
        result = re.sub(r'\bmelee\b', self.tr.counter_keyword("melee"), result, flags=re.IGNORECASE)
        result = re.sub(r'\binfantry\b', self.tr.counter_keyword("infantry"), result, flags=re.IGNORECASE)
        result = re.sub(r'\bcavalry\b', self.tr.counter_keyword("cavalry"), result, flags=re.IGNORECASE)
        result = re.sub(r'\bcheap\b', self.tr.counter_keyword("cheap"), result, flags=re.IGNORECASE)
        result = re.sub(r'\bhigh\b', self.tr.counter_keyword("high"), result, flags=re.IGNORECASE)
        result = re.sub(r'\blow\b', self.tr.counter_keyword("low"), result, flags=re.IGNORECASE)
        return result
