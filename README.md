# astrbot_plugin_aoe4

帝国时代4（Age of Empires IV）信息查询 AstrBot 插件。支持评分图片渲染、搞怪锐评、文明胜率矩阵、完整游戏数据查询。

## 指令列表

| 指令 | 功能 | 用法示例 |
|------|------|----------|
| `/aoe4` | 显示帮助菜单 | `/aoe4` |
| `/aoe4 bind <游戏ID>` | 通过名字搜索绑定游戏账号 | `/aoe4 bind beasty` |
| `/aoe4 bindid <ID>` | 通过Profile ID直接绑定 | `/aoe4 bindid 17594316` |
| `/aoe4 unbind` | 解绑已绑定的账号 | `/aoe4 unbind` |
| `/aoe4 me [-gid]` | 查看已绑定的账号信息 | `/aoe4 me` |
| `/aoe4 profile [ID] [-gid]` | 查询玩家资料（加 -gid 显示最近GID） | `/aoe4 profile beasty` |
| `/aoe4 recent [数量] [-gid/-pid]` | 最近对局记录（加 -gid/-pid 显示ID） | `/aoe4 recent 5 -gid` |
| `/aoe4 last [-score] [-gid/-pid]` | 上一局详情 + 评分对比图片 | `/aoe4 last -score` |
| `/aoe4 game <比赛ID> [-score] [-gid/-pid]` | 通过ID查比赛详情 | `/aoe4 game 234891793 -score` |
| `/aoe4 matchup [模式]` | 文明对战胜率矩阵（图片） | `/aoe4 matchup solo` |
| `/aoe4 compare <A> <B>` | 两个玩家数据对比 | `/aoe4 compare beasty 17594316` |
| `/aoe4 mecompare <玩家>` | 自己 vs 指定玩家对比 | `/aoe4 mecompare beasty` |
| `/aoe4 leaderboard [模式] [数量]` | 查看天梯排行榜 | `/aoe4 leaderboard solo` |
| `/aoe4 rank [模式] [数量]` | 同上 | `/aoe4 rank 3v3` |
| `/aoe4 search <关键词>` | 搜索玩家 | `/aoe4 search beasty` |
| `/aoe4 civ [名称]` | 文明概览（不填列所有） | `/aoe4 civ 中国` |
| `/aoe4 unit <名称>` | 查询单位数据 | `/aoe4 unit man-at-arms` |
| `/aoe4 building <名称>` | 查询建筑数据 | `/aoe4 building barrack` |
| `/aoe4 tech <名称>` | 查询科技数据 | `/aoe4 tech bloomery` |
| `/aoe4 counter <单位>` | 查询克制关系 | `/aoe4 counter 长矛兵` |
| `/aoe4 patch` | 查看最近版本更新 | `/aoe4 patch` |

### 通用标志

| 标志 | 说明 |
|------|------|
| `-score` | 用图片展示评分对比 + 搞怪锐评（需要 Playwright） |
| `-gid` | 在输出中显示对局 ID |
| `-pid` | 在输出中显示玩家 Profile ID |

### 支持的模式参数

| 参数 | 说明 |
|------|------|
| `solo` / `1v1` | 单挑排位（默认） |
| `2v2` | 双排 |
| `3v3` | 三排 |
| `4v4` | 四排 |

## 已实现功能

### 账号与资料
- [x] 账号绑定 / 解绑 / 查看绑定信息
- [x] 玩家资料查询（排位信息、段位、胜率等）
- [x] 玩家对比（A vs B / 自己 vs 指定玩家）

### 对局查询
- [x] 最近对局记录（地图、文明、结果、对手等）
- [x] 上一局对局详情（含经济/军事/科技评分）
- [x] 按比赛ID查询对局详情
- [x] **评分对比图片渲染**（卡片样式，支持 2~8 人）
- [x] **搞怪锐评分析**（种田王、白给王、战神下凡等趣味标签）
- [x] **文明对战胜率矩阵**（二维表图片，显示各文明对阵胜率）
- [x] 显示对局 ID / Profile ID 标志

### 天梯与搜索
- [x] 天梯排行榜（支持 solo / 2v2 / 3v3 / 4v4 等模式）
- [x] 玩家搜索（按游戏ID关键词）

### 游戏数据
- [x] 文明概览（特色单位/建筑/科技）
- [x] 单位详细数据（生命值、造价、伤害、护甲等）
- [x] 建筑详细数据（生命值、造价、驻军、影响等）
- [x] 科技效果查询（效果描述、造价、研发建筑等）
- [x] 兵种克制关系查询
- [x] 版本更新信息查询

### 多语言支持
- [x] 简体中文
- [x] English

## 依赖

```bash
pip install astrbot>=4.0.0
```

### 图片渲染（可选）

评分对比和文明胜率矩阵需要 Playwright + Chromium，未安装时会自动尝试安装：

```bash
pip install playwright
playwright install chromium
```

国内环境可配置镜像源加速：

```bash
PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright python -m playwright install chromium
```

> 如果 Playwright 不可用，`-score` 和 `matchup` 功能会自动回退到文字输出。

## 数据来源

- [AoE4 World API](https://aoe4world.com/api) — 玩家数据、天梯、对局
- [AoE4 World Data](https://data.aoe4world.com/) — 游戏内单位、建筑、科技数据
