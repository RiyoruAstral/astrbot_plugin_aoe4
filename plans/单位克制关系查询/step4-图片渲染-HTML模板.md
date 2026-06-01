# Step 4：图片渲染 — HTML 模板

## 目标

在 `score_renderer.py` 新增 `generate_counter_html()` 函数，输出与现有评分图风格一致的 HTML。

## 布局结构

```
┌──────────────────────────────────────────────┐
│  ⚔️ 弓箭手 · 克制进化                          │  标题栏
│  轻装远程步兵                                  │  副标题
├───────────┬──────────────────────────────────┤
│ 🔹 封建    │  🏭 铁匠铺                       │
│  弓箭手    │  🔹 钢铁箭头   +1 远程攻击       │
│  ───────  │                                  │
│  HP:60    │  🏫 靶场                         │
│  攻击:6   │  🔹 精锐科技   HP+20 攻击+2      │
│  射程:5   │                                  │
│           │                                  │
│  🔼 轻步兵 +6                                │
│  🔽 骑手   +11                               │
├───────────┼──────────────────────────────────┤
│ 🔹 城堡    │  🏭 铁匠铺                       │
│  精锐弓    │  🔹 箭矢护板  +1 远程攻击        │
│  ───────  │                                  │
│  HP:80    │  📛 不可用                        │
│  攻击:8   │  ⛔ 远程攻对火药单位无效           │
│  射程:5   │                                  │
│           │                                  │
│  🔼 轻步兵 +8                                │
│  🔽 骑手   +15                               │
├───────────┼──────────────────────────────────┤
│ 🔹 帝国    │  🎯 特色科技                     │
│  精英弓    │  ⭐ 燃烧箭(大学)  射程+1         │
│  ───────  │                                  │
│  HP:100   │                                  │
│  攻击:12  │                                  │
│  射程:5   │                                  │
│           │                                  │
│  🔼 轻步兵 +12                               │
│  🔽 骑手   +18                               │
└───────────┴──────────────────────────────────┘
```

## 分栏比例

| 区域 | 宽度 | 内容 |
|:-----|:----:|:-----|
| 左侧（时代线） | 65% | 时代标签、单位名、属性、克制/被克制 |
| 右侧（科技面板） | 35% | 按建筑分组排列的科技条目 |

## CSS 配色

```css
body {
    background: linear-gradient(135deg, #1a1a2e, #0f0f23);
    color: #e0e0e0;
    font-family: 'Noto Sans SC', 'Segoe UI', sans-serif;
    width: 640px;
    padding: 16px;
}

/* 标题 */
.title { color: #ffd93d; font-size: 20px; font-weight: bold; }
.subtitle { color: #a0a0c0; font-size: 13px; }

/* 时代 */
.age-header { color: #ffd93d; font-size: 14px; font-weight: bold; }

/* 克制 */
.counter-up { color: #4ecdc4; }
.counter-down { color: #ff6b6b; }

/* 科技 */
.tech-available { color: #85d085; }
.tech-unavailable { color: #ff9999; text-decoration: line-through; opacity: 0.7; }
.tech-inferred { opacity: 0.85; }
.tech-inferred::before { content: "⚠️ "; }

/* 建筑分组标题 */
.building-header { color: #8888aa; font-size: 12px; margin-top: 4px; }

/* 分割线 */
.section-divider { border-top: 1px solid #2a2a4e; }

/* 无数据降级 */
.fallback-description { text-align: center; color: #a0a0c0; padding: 24px; }
```

## 渲染降级

| 情况 | 处理 |
|:-----|:-----|
| 无科技数据（仅有 description） | 不显示分栏，居中显示 description，上下留白 |
| 单个时代变体 | 只有一栏，右侧全时代科技不变 |
| 科技列表为空 | 右侧显示 "暂无可用科技" |

## 新增接口

```python
def generate_counter_html(unit_data: dict, lang: str = "zh-CN") -> str:
    """生成克制关系 HTML 字符串"""
```

返回的 HTML 传入 `render_html_to_image(html, path, width=640)` 即可渲染。
