# Changelog

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
