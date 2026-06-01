# Step 1：数据结构参考

记录 API 返回数据的关键字段结构，后序步骤的匹配和渲染逻辑依赖于此。

## 单位数据（units）

来源：`data.aoe4world.com/units/all.json` → `data[]`

```json
{
  "id": "archer",
  "name": "Archer",
  "age": 2,
  "civs": ["en", "fr", "hr"],
  "displayClasses": ["LightRangedInfantry", "Infantry"],
  "hitpoints": 60,
  "costs": { "food": 0, "wood": 60, "gold": 0, "stone": 0, "time": 20 },
  "movement": { "speed": 1.4 },
  "weapons": [{
    "type": "ranged", "damage": 6, "speed": 1.5,
    "range": { "min": 0, "max": 5 },
    "modifiers": [{
      "type": "bonus_damage", "damage": 6,
      "target": { "displayClasses": ["LightMeleeInfantry"] }
    }]
  }],
  "armor": [
    { "type": "ranged", "value": 0 },
    { "type": "melee", "value": 0 }
  ],
  "producedBy": ["archery-range"],
  "unique": false,
  "description": "Cheap ranged infantry with good damage vs. unarmored targets..."
}
```

### 关键字段用途

| 字段 | 用途 |
|:-----|:-----|
| `id` | 匹配、翻译（如 `veteran-archer`） |
| `age` | 时代分组（1=黑暗 2=封建 3=城堡 4=帝国） |
| `civs` | 文明过滤 |
| `displayClasses` | 克制匹配、科技匹配 |
| `weapons[].modifiers[].target.displayClasses` | 克制关系计算 |
| `weapons[].modifiers[].damage` | 额外伤害数值 |
| `unique` | 是否为特色单位 |

### 克制关系计算

```python
def compute_counters(unit):
    """提取该单位克制哪些分类"""
    counters = []
    for weapon in unit.get("weapons", []):
        for mod in weapon.get("modifiers", []):
            target_classes = mod.get("target", {}).get("displayClasses", [])
            bonus = mod.get("damage", 0)
            if target_classes and bonus > 0:
                counters.append({
                    "classes": target_classes,  # 克制的分类列表
                    "damage": bonus,            # 额外伤害
                    "type": weapon.get("type", "")  # 武器类型
                })
    return counters

def compute_countered_by(unit, all_units):
    """提取哪些单位克制该单位"""
    unit_classes = set(unit.get("displayClasses", []))
    countered_by = []
    for other in all_units:
        if other["id"] == unit["id"]:
            continue
        for weapon in other.get("weapons", []):
            for mod in weapon.get("modifiers", []):
                target_classes = mod.get("target", {}).get("displayClasses", [])
                bonus = mod.get("damage", 0)
                if target_classes and bonus > 0 and unit_classes & set(target_classes):
                    countered_by.append({
                        "unit": other["name"],  # 克制方单位名
                        "damage": bonus
                    })
                    break
    return countered_by
```

## 科技数据（technologies）

来源：`data.aoe4world.com/technologies/all.json` → `data[]`

```json
{
  "id": "steeled-arrow",
  "name": "Steeled Arrow",
  "age": 2,
  "civs": ["en", "fr", "hr"],
  "displayClasses": [],
  "description": "+1 ranged damage",
  "costs": { "gold": 100, "food": 50 },
  "producedBy": ["blacksmith"],
  "unique": false,
  "duration": 60
}
```

### 字段匹配可用性

| 字段 | 是否可用 | 说明 |
|:-----|:--------:|:-----|
| `age` | ✅ | 按时代过滤 |
| `displayClasses` | ⚠️ | 许多科技此字段为空（如铁匠铺科技） |
| `producedBy` | ✅ | 可用于推断影响范围 |
| `description` | ✅ | 关键词匹配 |
| `unique` | ✅ | 特色科技限文明 |
| `civs` | ✅ | 文明过滤 |

## 建筑数据（buildings）

来源：`data.aoe4world.com/buildings/all.json` → `data[]`

```json
{
  "id": "blacksmith",
  "name": "Blacksmith",
  "age": 2,
  "civs": ["en", "fr", "hr"],
  "displayClasses": ["Building"],
  "hitpoints": 1500,
  "costs": { "wood": 150, "gold": 0, "stone": 0, "time": 30 },
  "armor": [{ "type": "melee", "value": 5 }, { "type": "ranged", "value": 10 }],
  "produces": ["steeled-arrow", "arrow-guards"],
  "unique": false
}
```

## 字段对应关系

```
weapon.type → armor_types (zh-CN.json)
  "melee" → "近战"     "ranged" → "远程"
  "siege" → "攻城"     "fire"   → "火焰"

displayClasses → display_classes (zh-CN.json)
  "LightRangedInfantry" → "轻装远程步兵"
  "HeavyMeleeCavalry"   → "重装近战骑兵"

modifier → 克制显示
  modifier.target.displayClasses + modifier.damage
  → "克制 轻装近战步兵 (+6 近战)"
```
