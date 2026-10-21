# 顶级 skill 的共性拆解（2026-10）

> 目的：回答「为什么有些 GitHub skill 能爆火，而结构合规的 skill 仍然平庸」。
> 样本：archify（[tt-a1i/archify](https://github.com/tt-a1i/archify)，86k★，流程图/架构图）、taste-skill（[Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)，99k★，前端美术方向）、sprite-gen（[aldegad/sprite-gen](https://github.com/aldegad/sprite-gen)，2.9k★，像素动画）、guizang-ppt-skill（[op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill)，28k★，演示文稿）。四者领域不同，但成功机制高度一致。
> 结论先说：**它们卖的不是「一份更好的提示词」，而是「一个被命名的设计论点 + 一套独创范例 + 一条可验证的生产线」。**

---

## 一、四个样本做对了什么

### 1. archify（流程图/架构图，86k★）

| 观察 | 证据 |
|------|------|
| 有命名的设计论点 | `DESIGN.md` 开篇 **Creative North Star: "The Evidence Console"**——「精密的工程仪器，不是绘图套件」 |
| 有完整设计系统 | 颜色全部语义化（frontend=cyan、backend=green、database=violet……），并立「Semantic Color Rule」「One Voice Rule」「Legibility Floor Rule」等命名规则 |
| 有类型路由器 | 10 种图（architecture/workflow/sequence/dataflow/lifecycle/erd/class/tree/timeline/waterfall），每种有独立 schema + 示例 |
| 有独创范例集 | `examples/` 下每类图都有 1-3 个 JSON + 渲染好的 HTML（cache-miss、checkout、incident、payment……），README 直接挂 live gallery |
| 有确定性生产线 | `bin/archify.mjs finalize` 串起 validate → deliver → check → browser-check；失败有修复手册与重试上限；交付带 receipt |
| 有锋利边界 | description 末尾直接写 **Not for dashboards** |
| 有分发门面 | README 首屏 hero 图 + 35 秒 demo 视频 + 130K installs 徽章 + 案例页 |

关键差异：它不是「教 AI 画图」，而是**把图变成一种有 schema、可校验、可交互的产物格式**。这就是「非显然的抽象」。

### 2. taste-skill（前端美术方向，99k★）

| 观察 | 证据 |
|------|------|
| 有反默认的机制 | `draw.mjs` 从 247 个真实获奖站点蒸馏的 library 里**发牌**，一次给 3 个方向，逼创作者离开模型默认审美 |
| 论点来自对象本身 | 强制句式：「在这个页面上，**[属于这个主体的东西]** 变成 **[方向要求的装置]**」，并跑**竞争测试**：把最近的真实竞品代入，句子仍成立 = 这个想法属于品类，不属于这个主体 |
| 有原创资产库 | `library/` 下 palettes / type / heroes / motions / sections / sites 全部结构化 |
| 有机器校验 | `inspect.mjs` 在真实浏览器里量房子风格；三档宽度截图 + juror rubric + 看图修正循环 |
| 有诚实警告 | 明确写「去掉装饰只做了一半；另一半是实质：更大的字、整块颜色、真实图片、每节完整内容」 |

关键差异：它解决的不是「怎么排版」，而是**「怎么让模型不做平均值」**——用发牌器 + 主体盘点 + 竞争测试，把「品味」变成可操作的选择过程。

### 3. sprite-gen（像素动画，2.9k★）

| 观察 | 证据 |
|------|------|
| 有极强的工艺约束 | 朝向、handedness、body-plan、play mode、loop 接缝、RIFE 补帧、alpha 精确导出，全部写成表与脚本 |
| 有确定性流水线 | 24 个脚本覆盖 prepare/generate/extract/interpolate/compose/QA/curation/export |
| 有可验证产物 | 每个环节产出 report、GIF/WebP、atlas；`score_sprite_run.py`、`inspect_sprite_run.py`、`run_correction_loop.py` |
| 有「问而不是猜」的协议 | codex 不可用时 **exit 75**：不生成、不重试、不自动换 provider，把选择权交还用户 |
| 有原创演示 | docs/assets 下几十个 GIF：attack、walk、scene、before/after |

关键差异：把「看起来像像素游戏」拆成**可测量、可修复的工序**，而不是一句「画得精致点」。

### 4. guizang-ppt-skill（演示文稿，28k★）

| 观察 | 证据 |
|------|------|
| 有明确风格阵营 | `layouts.md` + `layouts-swiss.md` + `themes.md` + `themes-swiss.md`，两套完整视觉语言而非一套模板 |
| 有真实素材锚点 | `assets/screenshot-backgrounds/` 按 style-a/style-b 分组的真实背景图 |
| 有校验脚本 | `validate-swiss-deck.mjs`、`validate-presenter-mode.mjs`、runtime sync check |
| 有展示门面 | README hero 截图 + 演示模式 |

关键差异：不是「生成 PPT」，而是**「生成某种有立场的 PPT」**，并给每套立场配素材与校验。

---

## 二、六条可迁移的共性（按重要性排序）

| # | 共性 | 一句话判据 | 盘古开天 现状 |
|---|------|-----------|------------------|
| 1 | **命名论点** | 能用一句话说出「非显然的问题 + 默认做法为什么失败 + 我的解法」；同类 skill 说不出同样的话 | 缺（只提炼铁律/模型，不要求论点） |
| 2 | **独创范例集** | 每个核心模式至少 1 件可打开、可运行、可对照的成品；不是一张截图 | 缺（只有 1-2 张 showcase 截图） |
| 3 | **确定性核心** | 核心变换由脚本/schema 完成，有一键 verify/finalize；不是靠散文描述 | 部分（只有 quality_check/rubric_score） |
| 4 | **设计系统** | 颜色/字阶/间距/组件有 token 与命名规则，不是形容词 | 上一轮已加工艺参数卡，但未要求命名规则 |
| 5 | **反默认机制** | 有发牌器/变体/竞争测试，强制偏离模型默认审美 | 部分（已加 2-3 变体，缺「发牌」与主体盘点） |
| 6 | **锋利边界与门面** | description 写清不做什么；README 有 hero、gallery、真实 demo | 部分（有诚实边界，README 模板偏弱） |

---

## 三、映射到 盘古开天 的落点

| 共性 | 落点 | 交付物 |
|------|------|--------|
| 命名论点 | F2 开头（先于质量维度卡） | `references/design-thesis.md` |
| 独创范例集 | F3 出厂闸门 | `examples/`（每模式 ≥1 件）+ `assets/showcase/` 署名作品 |
| 确定性核心 | F3 构建 + F4 验收 | `scripts/` 核心变换 + 一键 `verify`/`finalize` |
| 设计系统 | F2 工艺参数卡 + 命名规则 | `references/design-system.md`（或并入 art-direction.md） |
| 反默认机制 | 第一阶段素材盘点 + F3 变体 | 「只有这个主体才有」的 8-12 条清单；2-3 个方向变体 |
| 锋利边界与门面 | F3.5 README | hero + gallery 索引 + 真实 demo |

---

## 四、反例：结构合规但平庸的典型症状

- SKILL.md 十维近乎满分，`examples/` 为空或只有一张截图
- 论点写成「帮助用户更高效地完成 X」——任何同类都能这么说
- 核心步骤用散文描述，换个模型就执行不一致
- README 只有安装命令，没有一件能点开看的成品
- 五个 skill 产出共享同一套暗底青蓝模板

**判定**：以上任意两条命中，视为「文档型 skill」，不得宣称发布级；只能算工作流草稿。

---

## 五、给 盘古开天 的硬约束（已落地）

1. 没有 `design-thesis.md` 的产出型 skill 不许进入 F3。
2. 范例集不足 3 件（且每件能打开/运行）不许出厂；署名作品必须手写，不许模板直出。
3. 核心变换必须脚本化；没有一键 verify 的产出型 skill，F4 判硬性失败。
4. 论点必须通过竞争测试；「更高效/更专业/更好用」一律判空话。
5. README 必须有 hero + gallery；没有可点开的作品，不算完成 F3.5。
