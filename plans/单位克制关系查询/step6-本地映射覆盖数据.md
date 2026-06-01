# Step 6：本地映射覆盖数据

## 目标

建立本地 JSON 覆盖系统，修正自动规则无法处理的特殊案例（如手炮手不吃铁匠铺远程攻）。

## 文件结构

```
data/tech_data/
├── metadata.json          — 版本记录 + 更新时间
├── overrides.json         — 跨文明通用例外
└── civ_overrides/         — 按文明
    ├── od.json            — 龙之骑士团
    ├── zx.json            — 朱熹遗产
    └── ...
```

## format

### metadata.json

```json
{
  "version": 1,
  "updated_at": "2026-05-29T12:00:00Z",
  "schema_version": 1
}
```

### overrides.json

```json
{
  "exclude_techs": {
    "handcannoneer": {
      "tech_ids": ["steeled-arrow", "arrow-guards", "platecutter-points"],
      "reason": "火药单位不吃铁匠铺远程攻"
    }
  },
  "force_techs": {
    "handcannoneer": {
      "tech_ids": ["serpentine-powder"],
      "reason": "蛇纹石科技影响手炮手"
    }
  }
}
```

### civ_overrides/od.json

```json
{
  "civ": "od",
  "updated_at": "2026-05-29T12:00:00Z",
  "units": {
    "gilded-spearman": {
      "base_unit": "spearman",
      "techs": {
        "available": { "elite-army": "exact" },
        "unavailable": { "chivalry": "骑兵科技不适用" }
      }
    }
  },
  "note": "龙之骑士团所有单位均为特色变体"
}
```

## 读取优先级

```
对每个单位：
  1. civ_overrides/{civ}.json → 有本文明该单位条目？→ 直接返回
  2. overrides.json → 有 exclude_techs / force_techs？→ 应用过滤
  3. step3 自动规则匹配 → 兜底
```

## TechDataManager

```python
class TechDataManager:
    def __init__(self, data_dir: str, tr):
        self._data_dir = data_dir
        self._overrides: dict = {}
        self._civ_overrides: dict[str, dict] = {}
        self._loaded_at: float = 0.0

    def load(self):
        path = os.path.join(self._data_dir, "overrides.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self._overrides = json.load(f)
        civ_dir = os.path.join(self._data_dir, "civ_overrides")
        if os.path.exists(civ_dir):
            for fname in os.listdir(civ_dir):
                if fname.endswith(".json"):
                    code = fname.replace(".json", "")
                    with open(os.path.join(civ_dir, fname), encoding="utf-8") as f:
                        self._civ_overrides[code] = json.load(f)
        self._loaded_at = time.monotonic()

    def apply_overrides(self, unit_id: str, civ_code: str, matched_techs: list) -> list:
        """对自动匹配的科技列表应用覆盖规则"""
        # 1. 先查 civ_overrides
        # 2. 再查 overrides
        # 3. 返回修正后的科技列表
```

## 注意事项

- 增量维护，不用一次写完
- 缓存遵循 `data_cache_ttl`
- 大版本更新后审查 `metadata.json`
