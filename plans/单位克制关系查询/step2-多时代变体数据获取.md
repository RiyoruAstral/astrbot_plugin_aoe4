# Step 2：多时代变体数据获取

## 目标

将 `get_counter_info` 从仅返回第一个匹配单位，改为返回该单位系列的所有时代变体，按 age 分组。

## 当前行为

```python
results = self._match(self._units, query)  # 返回匹配列表
unit = results[0]                          # 只取第一个（如 archer 而非 veteran-archer）
```

## 改造后行为

```python
results = self._match(self._units, query)  # 匹配列表
variants = _group_variants(results)        # 按 base ID 分组 + 按 age 排序
```

### _group_variants 逻辑

```python
def _group_variants(self, results: list[dict]) -> list[list[dict]]:
    """按 base ID 分组，每组内按 age 升序排列"""
    base_map: dict[str, list[dict]] = {}
    for unit in results:
        base_id = unit["id"].split("-")[-1] if unit["id"].startswith("veteran-") or unit["id"].startswith("elite-") else unit["id"]
        base_id = re.sub(r"^(veteran-|elite-)", "", unit["id"])
        # 处理命名规律：archer / veteran-archer / elite-archer
        base_key = base_id
        # English/French: 后缀 "-man" → "man-at-arms", "veteran-man-at-arms"
        # Chinese: 直接按 id 前缀
        if base_key not in base_map:
            base_map[base_key] = []
        base_map[base_key].append(unit)
    
    groups = sorted(base_map.values(), key=lambda g: g[0].get("age", 0))
    groups = [sorted(g, key=lambda u: u.get("age", 0)) for g in groups]
    return groups
```

## 克制关系计算迁移

原来在 `get_counter_info` 内联的计算逻辑改为抽成独立方法，对每个变体调用一次：

```python
def _compute_unit_counters(self, unit: dict, all_units: list[dict]) -> dict:
    return {
        "counters": self._extract_counters(unit),
        "countered_by": self._extract_countered_by(unit, all_units),
    }
```

## 新增输出结构

`get_counter_info` 返回值改为：

```python
{
    "unit_name": "Archer",         # 原单位显示名
    "unit_class": "轻装远程步兵",    # 原单位分类（取第一个变体的 displayClasses）
    "variants": [
        {
            "unit_id": "archer",
            "name": "弓箭手",        # 已翻译
            "age": 2,               # 数字
            "hp": 60,
            "attack": 6,
            "range": 5,
            "display_class": "轻装远程步兵",
            "counters": [
                {"class": "轻装近战步兵", "damage": 6, "type": "近战"}
            ],
            "countered_by": [
                {"unit": "骑手", "damage": 11, "type": "近战"}
            ]
        },
        { "age": 3, "name": "精锐弓箭手", ... },   # veteran-archer
        { "age": 4, "name": "精英弓箭手", ... }    # elite-archer
    ],
    "description": "..."             # 原单位描述（已翻译）
}
```
