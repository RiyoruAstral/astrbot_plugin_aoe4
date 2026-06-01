# Step 3：科技自动匹配规则

## 目标

对每个单位变体，自动匹配"哪些科技影响该单位"，填充图片右侧的科技面板。

## 策略 A：displayClasses 交集（覆盖 ~60%）

科技和单位的 `displayClasses` 有交集即匹配。

```python
def _display_classes_match(self, unit: dict, tech: dict) -> bool:
    unit_classes = set(unit.get("displayClasses", []))
    tech_classes = set(tech.get("displayClasses", []))
    if not tech_classes:
        return False  # 无分类标记的科技交给策略 B
    return bool(unit_classes & tech_classes)
```

示例：
```json
科技 "elite-army":        { "displayClasses": ["Infantry"] }
单位 "man-at-arms":       { "displayClasses": ["HeavyMeleeInfantry", "Infantry"] }
// ✅ Infantry 交集匹配 → match_type = "exact"
```

标记为 `"exact"`（精确匹配），渲染时用绿色高亮。

## 策略 B：producedBy + 描述关键词（覆盖 ~25%）

铁匠铺等建筑的科技没有 displayClasses，需通过描述推断。

```python
def _infer_affected_classes(self, tech: dict) -> list[str]:
    produced_by = tech.get("producedBy", [])
    desc = tech.get("description", "").lower()

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
            return ["ArrowShip", "SpringaldShip"]

    if "dock" in produced_by:
        return ["ArrowShip", "SpringaldShip", "Warship"]

    return []
```

匹配后比对单位 displayClasses，有交集则标记为 `"inferred"`（推断匹配），渲染时加 `⚠️`。

## 策略 C：unique 标志 + 文明匹配

特色科技只能影响同文明的单位。

```python
def _match_unique_by_civ(self, unit: dict, tech: dict) -> bool:
    if not tech.get("unique"):
        return False
    return bool(set(unit.get("civs", [])) & set(tech.get("civs", [])))
```

标记为 `"inferred"`。

## 优先级顺序

```
对每个科技，检查是否影响目标单位：
  1. 策略 A（displayClasses 交集）→ exact
  2. 策略 B（producedBy + 关键词）→ inferred
  3. 策略 C（unique + 文明）      → inferred
  4. 都不匹配 → 不显示
```

## 过滤规则

匹配到科技列表后，按以下规则过滤：

```python
def _filter_techs(self, unit: dict, techs: list[dict]) -> list[dict]:
    # 1. 科技 age ≤ 单位 age（不能研发未来时代的科技）
    # 2. 排除 overrides.json 中 exclude_techs 列表的科技（step6）
    # 3. 去重（同 id 只保留一次）
```

## 输出格式

```python
{
    "techs": [
        {
            "id": "steeled-arrow",
            "name": "钢铁箭头",
            "effect": "+1 远程攻击",
            "building": "铁匠铺",      # 翻译后的建筑名
            "age": 2,                   # 科技可用时代
            "available": true,          # 当前变体能否吃到
            "match_type": "exact"       # exact | inferred
        },
        ...
    ]
}
```

## 已知问题

| 问题 | 影响 | 解决（step6） |
|:-----|:-----|:--------------|
| Handcannoneer 被铁匠铺远程攻误匹配 | 显示不该有的科技 | overrides.json 排除 |
| 龙之骑士团变体独特科技不匹配 | 漏显示 | od.json 手动映射 |
