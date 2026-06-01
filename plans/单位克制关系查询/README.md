# 单位克制关系查询 — 开发步骤总览

| 步骤 | 文件 | 核心内容 |
|:----:|:-----|:---------|
| 1 | [step1-数据结构参考](./step1-数据结构参考.md) | API 返回的 unit/tech/building 字段说明 |
| 2 | [step2-多时代变体数据获取](./step2-多时代变体数据获取.md) | `get_counter_info` 改为返回所有时代变体 |
| 3 | [step3-科技自动匹配规则](./step3-科技自动匹配规则.md) | displayClasses 交集 / producedBy+描述推断 / unique匹配 |
| 4 | [step4-图片渲染-HTML模板](./step4-图片渲染-HTML模板.md) | HTML 布局、CSS 配色、渐变背景、分栏 |
| 5 | [step5-数据编排与降级输出](./step5-数据编排与降级输出.md) | main.py 改造 + 渲染降级逻辑 |
| 6 | [step6-本地映射覆盖数据](./step6-本地映射覆盖数据.md) | overrides.json + civ_overrides 文件格式 |
| 7 | [step7-文明数据补充](./step7-文明数据补充.md) | 文明优先级、增量维护、QA 清单 |

## 依赖关系

```
step1 (数据结构) ─→ step2 (数据获取) ─→ step3 (科技匹配)
                                                │
                                                ├→ step4 (HTML模板) ─→ step5 (输出编排)
                                                │
                                                └→ step6 (映射覆盖) ─→ step7 (文明补充)
```

## 涉及代码文件

| 文件 | 改动范围 |
|:-----|:---------|
| `data_client.py` | step1-step3, step6 |
| `score_renderer.py` | step4 |
| `main.py` | step5 |
| `data/tech_data/` | step6-step7 |
