# Step 5：数据编排与降级输出

## 目标

改造 `main.py` 的 `_handle_counter`，在有 Playwright 时走图片渲染，无 Playwright 时保持现有文字模式。

## 改造后 _handle_counter 流程

```python
async def _handle_counter(self, event: AstrMessageEvent):
    # 1. 参数解析（不变）
    parts = event.message_str.strip().split(maxsplit=2)
    if len(parts) < 3:
        yield event.plain_result("用法: /aoe4 counter <单位名>")
        return
    query = parts[2]

    # 2. 数据获取（改造后，返回所有时代变体 + 科技）
    info = await self.data.get_counter_image_data(query)
    if not info:
        yield event.plain_result(f"未找到单位「{query}」")
        return
    if not info.get("variants"):
        yield event.plain_result(f"未找到单位「{query}」的数据")
        return

    # 3. 有 Playwright → 渲染图片
    if HAS_RENDERER:
        try:
            img_result = await self._render_counter_image(event, info)
            if img_result:
                yield img_result
                return
        except Exception as e:
            logger.error(f"克制图渲染失败: {e}")

    # 4. 无 Playwright 或渲染失败 → 回退文字模式
    lines = self.data.format_counter_info(info)
    yield self._forward_result(event, "\n".join(lines))
```

## 新增 _render_counter_image

```python
async def _render_counter_image(self, event: AstrMessageEvent, unit_data: dict):
    from score_renderer import generate_counter_html, render_html_to_image

    html = generate_counter_html(unit_data, self.tr.get_lang())
    cache_dir = os.path.join(tempfile.gettempdir(), "aoe4_counter_cache")
    os.makedirs(cache_dir, exist_ok=True)
    img_path = os.path.join(cache_dir, f"counter_{uuid.uuid4().hex}.jpg")

    ok = await render_html_to_image(html, img_path, width=640)
    if ok and os.path.exists(img_path):
        return event.chain_result([Image(file=img_path)])
    return None
```

## 降级优先级

```
HAS_RENDERER = True?
  ├─ 是 → render_counter_image()
  │       ├─ 成功 → 输出图片
  │       └─ 失败 → logger.error + 回退文字
  └─ 否 → 回退文字
```

## 文字模式兼容

改造后的 `format_counter_info` 需要同时兼容旧格式（单单位）和新格式（多时代变体）。数据结构变化：

```python
# 新结构
info = {
    "unit_name": "Archer",
    "variants": [
        { "age": 2, "name": "弓箭手", "counters": [...], "countered_by": [...] },
        ...
    ]
}

# 文字输出：仅显示基础变体（第一个），保持与现有一致
base = info["variants"][0]
lines = [f"⚔️ {info['unit_name']} 克制关系"]
# ... 原有逻辑不变（仅取 base 的数据）
```
