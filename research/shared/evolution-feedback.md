# 使用回流（Evolution Feedback）

> 从 盘古开天 自身的 worse 记录和锻造/进化过程中提炼的教训卡片。
> 每条卡片 = 一次真实教训 → 根因 → 修复动作。
> 新 skill 创建时先查本文件——避免重复踩坑。

## 卡片格式

```markdown
### [FEEDBACK-NN] 简短标题
- **日期**: YYYY-MM-DD
- **场景**: 哪个 Phase / 哪个 skill / 什么操作
- **问题**: 发生了什么
- **根因**: 为什么发生
- **修复**: 改了什么（SKILL.md / forge.md / evolve.md / scripts/）
- **通用性**: 通用（回填 iron-rules/anti-patterns/taste-signals）｜领域特定（只在 results.tsv 记录）
- **回填**: [ ] iron-rules  [ ] anti-patterns  [ ] taste-signals  [ ] 仅记录
```

---

## 教训卡片

### [FEEDBACK-01] 检查点被静默跳过

- **日期**: 2026-10-04
- **场景**: knowledge-cards 锻造全程，4 个 CHECKPOINT 零交互
- **问题**: 用户发现全程没有在任何检查点停过——SKILL.md 写了 🔴 CHECKPOINT，但执行时全部跳过
- **根因**: 「不阻塞交付」原则被无限扩大，吞掉了检查点的闸门语义；没有区分运行模式（交互 vs 无人值守）；红队轮未跑（门槛放过）
- **修复**: SKILL.md 新增「检查点语义」——交互模式=阻塞闸门+2-4个具体确认问题；无人值守才允许默认推进+显著声明+逐条记档；跳过检查点=硬性失败
- **通用性**: 通用
- **回填**: [x] anti-patterns (AP-03)  [ ] iron-rules  [ ] taste-signals

---

### [FEEDBACK-02] 意图显影未索要参照物

- **日期**: 2026-10-04
- **场景**: knowledge-cards L1 显影，用户只说「做个知识卡片网页」
- **问题**: 用户给参照图后证明要的是「节点-连线架构图」而非竖排卡片流——整个形态做错了
- **根因**: L1 显影时未主动索要参照物，只做方向卡就往下走
- **修复**: 需求挖掘第一步=索要参照物（一图胜十问）；意图档案归档
- **通用性**: 通用
- **回填**: [x] iron-rules (IR-10)  [ ] anti-patterns  [ ] taste-signals

---

### [FEEDBACK-03] 观感维度缺失配方库与惊喜线

- **日期**: 2026-10-04
- **场景**: 光刻机 demo 被判「粗糙」，对比 html-to-video（进化后）与 threejs-web（初版）
- **问题**: threejs-web 初版观感粗糙，html-to-video 进化后观感大幅提升
- **根因**: ① F1.0 只搜同类 skill 不搜美学标杆 ② 产出型 skill 无配方库强制 ③ 观感验证被简化丢惊喜线 ④ 活页面动态交互无脚本化验证
- **修复**: forge.md 双轨侦察（同类 skill + 美学标杆）；配方库必备（F3 强制检查）；两档观感验证（及格线 + 惊喜线）；交互验证脚本化
- **通用性**: 通用
- **回填**: [ ] iron-rules  [ ] anti-patterns  [x] taste-signals (TS-02, TS-03)

---

### [FEEDBACK-04] 必须走上进化契约

- **日期**: 2026-10-04
- **场景**: 用户指令强调必须走上进化
- **问题**: 交付即第 0 代的概念未明确编码
- **根因**: 进化契约未写入 SKILL.md 铁律层
- **修复**: SKILL.md 铁律 10 + evolve.md 进化契约（交付即第 0 代，worse 强制进化，两次 worse 升级重写）
- **通用性**: 通用
- **回填**: [x] iron-rules (IR-09)  [ ] anti-patterns  [ ] taste-signals

---

### [FEEDBACK-05] 第一阶段理解与定义

- **日期**: 2026-10-04
- **场景**: 用户指令要求扩充提示词/挖掘需求/完善内容/再侦察学习
- **问题**: 原 Phase 0.5 直接跳到 F1 侦察，缺少充分的理解与定义阶段
- **根因**: 阶段编号与内容不匹配，「第一阶段」实际是 Phase 0.5 的一部分
- **修复**: 重构为「第一阶段：理解与定义」（七要素简报+隐性五问+MVP/增强项），修历史编号 bug
- **通用性**: 通用
- **回填**: [ ] iron-rules  [ ] anti-patterns  [ ] taste-signals

---

### [FEEDBACK-06] 思维工具层缺失

- **日期**: 2026-10-04
- **场景**: 用户指令要求融入第一性原理/钢人/对抗性思维
- **问题**: 管线有步骤但缺少贯穿的思维工具
- **根因**: 方法论停留在流程层面，未上升到思维层面
- **修复**: forge.md 思维工具表 + F1.0 第一性回问 + F2.0 本质约束 + F2.2 钢人失效条件 + F4 红队轮 + F5/E2 钢人反对 + 方向卡钢人反对
- **通用性**: 通用
- **回填**: [ ] iron-rules  [ ] anti-patterns  [x] taste-signals (TS-09, TS-10)

---

### [FEEDBACK-07] 结构分虚高，作品分一般

- **日期**: 2026-10-21
- **场景**: 用户复盘五个案例产出（threejs-web / knowledge-cards / html-to-video / web-game-craft / 光刻机 demo / 幻碑之谷），称「效果还是一般」
- **问题**: 静态 rubric 几乎满分（threejs-web 81/81、knowledge-cards 78.6/81、html-to-video 78.6/81），但截图与视频成品观感平庸：扁平材质、低对比、同款暗底青蓝、构图空
- **根因**: ① rubric 量的是 SKILL.md 文档结构，不是产物；② 观感闸门只数配方数量，不查工艺参数；③ 美学标杆轨实际是选做，且拿同类 skill 默认模板当标杆；④ 一轮成型，没有美术方向变体
- **修复**: 新增 `references/output-quality.md`（参照物关/工艺参数关/盲评对比关）；F1.0 美学标杆轨改为产出型必做并落 `art-direction.md`；F2 增加工艺参数卡；F4 增加产出质量门与反模板测试；迭代上限产出型 3 轮；rubric_score.py 输出改称「文档结构分」并探测产出证据
- **通用性**: 通用
- **回填**: [x] iron-rules (IR-11)  [x] anti-patterns (AP-13, AP-15)  [x] taste-signals (TS-11, TS-12)

---

### [FEEDBACK-08] baseline/paired 证据链被降级记账

- **日期**: 2026-10-21
- **场景**: 案例复盘发现两类记账问题——knowledge-cards 的 baseline 是 dry_run 猜测；web-game-craft 79.3→86.3 记录为 paired，但 judge 就是改者本人
- **问题**: 没有真实对照与独立评审，分数却按 keep 上调，进化链整体失真
- **根因**: 缺少 `self_eval` 模式；paired 只定义了「同一 judge 比较」却没要求「独立且不知来源」；baseline 允许用默认行为描述代替实跑
- **修复**: testing.md §8 增加 `self_eval` 与「自查陷阱」；evolve.md 规定 self_eval 不得 keep、paired 必须比成品、baseline 必须真实跑；E1/E2 增加产出型规则
- **通用性**: 通用
- **回填**: [x] iron-rules (IR-11)  [x] anti-patterns (AP-14)  [ ] taste-signals
