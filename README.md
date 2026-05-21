# AstrByAOE4SearchView

帝国时代4（Age of Empires IV）信息查询 AstrBot 插件。

## 指令列表

| 指令 | 功能 | 用法示例 |
|------|------|----------|
| `/aoe4` | 显示帮助菜单 | `/aoe4` |
| `/aoe4 bind <游戏ID>` | 绑定游戏账号 | `/aoe4 bind beasty` |
| `/aoe4 unbind` | 解绑已绑定的账号 | `/aoe4 unbind` |
| `/aoe4 me` | 查看已绑定的账号信息 | `/aoe4 me` |
| `/aoe4 profile [ID]` | 查询玩家资料 | `/aoe4 profile` |
| `/aoe4 recent [数量]` | 查询最近对局记录 | `/aoe4 recent 5` |
| `/aoe4 last` | 查看上一局详细数据 | `/aoe4 last` |
| `/aoe4 leaderboard [模式] [数量]` | 查看天梯排行榜 | `/aoe4 leaderboard solo` |
| `/aoe4 rank [模式] [数量]` | 同上 | `/aoe4 rank 3v3` |
| `/aoe4 search <关键词>` | 搜索玩家 | `/aoe4 search beasty` |
| `/aoe4 civ [名称]` | 文明概览（不填列所有） | `/aoe4 civ 中国` |
| `/aoe4 unit <名称>` | 查询单位数据 | `/aoe4 unit man-at-arms` |
| `/aoe4 building <名称>` | 查询建筑数据 | `/aoe4 building barrack` |
| `/aoe4 tech <名称>` | 查询科技数据 | `/aoe4 tech bloomery` |

## 已实现功能

### Phase 1 ✅
- [x] 账号绑定系统（`bind` / `unbind` / `me`）
- [x] 玩家资料查询（排位信息、段位、胜率等）
- [x] 最近对局查询（地图、文明、结果、对手等）

### Phase 2 ✅
- [x] 天梯排行榜（支持多种模式）
- [x] 玩家搜索（按游戏ID关键词）
- [x] 上一局对局详情（含经济/军事/科技评分）

### Phase 3 ✅
- [x] 文明概览（特色单位/建筑/科技）
- [x] 单位详细数据（生命值、造价、伤害、护甲等）
- [x] 建筑详细数据（生命值、造价、驻军、影响等）
- [x] 科技效果查询（效果描述、造价、研发建筑等）

## 数据来源

- [AoE4 World API](https://aoe4world.com/api) — 玩家数据、天梯、对局
- [AoE4 World Data](https://data.aoe4world.com/) — 游戏内单位、建筑、科技数据
