# 共享知识库

> 跨 skill 的通用知识层。每个 skill 的调研文件是独立的，但提炼出的**通用铁律、反模式、品味倾向**不锁在各自目录——它们回填到这里，新 skill 创建时先查这里，避免重复踩坑。

## 目录结构

```
shared/
├── README.md            # 本文件：使用指南
├── incoming.md          # 待吸收清单：定期生态扫描发现的新 skill/新范式
├── iron-rules.md        # 通用铁律：跨领域违反必出事故的规则
├── anti-patterns.md     # 通用反模式：AI 常见俗手 + 跨领域反模式
├── taste-signals.md     # 品味信号：跨领域通用的审美/判断倾向
└── evolution-feedback.md # 使用回流：从 worse 记录提炼的教训卡片（同 盘古开天 根目录）
```

## 使用规则

### 创建新 skill 时
1. **先查 `iron-rules.md`**：这个领域有哪些通用铁律？新 skill 的铁律层必须覆盖相关条目。
2. **先查 `anti-patterns.md`**：这个领域有哪些常见俗手？新 skill 的品味层必须编码反模式。
3. **查 `incoming.md`**：最近有没有待吸收的同类 skill？有的话优先精读。
4. 提炼出新的通用知识 → 回填到对应文件（标注来源 skill）。

### 进化 skill 时
1. 如果 worse 记录指向一个**通用问题**（不只是该 skill 特有的）→ 提炼为教训卡片 → 回填 `evolution-feedback.md` 和对应通用文件。
2. 如果 worse 记录指向一个**领域特有问题** → 只在该 skill 的 `results.tsv` 记录，不回填共享层。

### 定期维护
- **每月一次**（可做成定时任务）：跑 `analyze_evolution.py` 看趋势 → 高频 worse 维度 → 审视共享层是否需要更新。
- **每季度一次**：跑生态扫描 → 新 skill/新范式 → 追加到 `incoming.md`。

## 回填标记

每个共享条目标注来源：

```markdown
## [IR-03] 铁律：没有基线就没有发言权
来源: 盘古开天 铁律1 / obra/superpowers 文档TDD
首次提炼: 2026-10-01
回填次数: 3（html-to-video, knowledge-cards, threejs-web）
```

- `回填次数` 表示有多少个 skill 验证过这条铁律——次数越多越可信。
- 没有来源的条目不进共享层（避免编造）。
