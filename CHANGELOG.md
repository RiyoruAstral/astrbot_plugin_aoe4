# Changelog

## [1.5.0] - 2026-06-01

### Added
- `/aoe4 radar [游戏ID] [-n N] [-force]`：评分雷达图图片输出，用 4 轴 SVG 雷达图直观展示每位玩家的军事/经济/科技/社会四项评分分布
- 支持 1v1 至 4v4 全部多人场景，卡片自适应布局（2 列 / 3 列）
- 雷达图含归一化百分比标注，一眼看出局内强弱项
- 每个玩家卡片底部附带搞怪锐评标签
- 新增中英文 `help_radar` 指令说明

## [1.4.0] - 2026-05-29

### Added
- `/aoe4 me -civ`：查看绑定账号最近 N 场的文明胜率分布（含胜率条 + 均分差）
- `/aoe4 last -n N`：查看倒数第 N 局详情，如 `/aoe4 last -n 3`
- `/aoe4 leaderboard me [模式]`：在排行榜中搜索自己的排名位置，显示附近玩家
- 新增 `data_cache_ttl` 配置项：文明/单位/建筑/科技数据的缓存过期时间（默认 86400 秒/1天）
- 新增 `myciv_analysis_games` 配置项：`/aoe4 me -civ` 分析的最近对局数（默认 5，范围 2~50）

### Changed
- `/aoe4 recent [N]` 超过 5 局时自动分页，每 5 局一条消息
- `AoE4DataClient` 缓存机制：增加 TTL 判断，过期后自动重新请求游戏数据

## [1.3.0] - 2026-05-29

### Added
- 新增 `summary_cache_ttl` 配置项：FlareSolverr 失败结果缓存时间（默认 120 秒），到期后自动重试
- `/aoe4 last -force` / `/aoe4 game -force`：强制刷新评分缓存，跳过 TTL
- 新增 `pypi_mirror` 配置项：Playwright 自动安装时的 PyPI 镜像源
- 新增 `chromium_download_host` 配置项：Playwright Chromium 浏览器下载镜像
- 新增 `api_timeout_default` / `api_timeout_leaderboard` 配置项：API 请求超时时间

### Changed
- Playwright 自动安装逻辑从模块加载时延迟到插件 `__init__` 初始化时执行，`pypi_mirror` 配置现在生效
- Chromium 下载镜像尝试顺序：配置镜像 → Playwright 官方 → 默认源（fallback）

## [1.2.0] - 2026-05-27

### Added
- 自动安装 playwright Python 包（ImportError 时自动 `pip install playwright==1.48.0 --no-deps` + 核心依赖 `pyee`, `greenlet`）
- 插件初始化时主动预下载 Chromium 浏览器
- `/aoe4 leaderboard` 新增 `-pid` 参数显示玩家 Profile ID
- `/aoe4 recent` 新增对手/队友的 `-pid` 显示支持
- `/aoe4 matchup` 全面支持所有模式：`solo/1v1/2v2/3v3/4v4/team` 及快速模式 `qm/qm_1v1/qm_2v2/qm_3v3/qm_4v4`
- 新增 Tughlaq Dynasty（图格鲁克王朝）中英文翻译
- `/aoe4 patch` 显示版本更新相对时间（X 年前/月前/天前）

### Fixed
- `/aoe4 patch` 修复 `KeyError: 'date'` 崩溃（`_parse_rss_aoe4` 缺少 `date` 字段）
- `/aoe4 recent` 修复 `-pid` 和 `-id` 同时使用时 flag 解析错误的 bug
- `/aoe4 civ` 修复每个文明输出两遍的问题（按显示名称去重）
- `/aoe4 civ` 特色单位/建筑/科技名称现在经过 i18n 翻译
- `/aoe4 patch` 字段改用 `.get()` 防御性取值，避免类似 KeyError

### Changed
- pip 安装源改为清华镜像 `https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple`
- Chromium 下载镜像改为官方 fallback CDN `https://playwright.azureedge.net/`
- pip 安装 playwright 使用 `--no-deps` 跳过依赖检查，手动安装精简核心库
