# 进化管线详解（E0-E3）

> 设计哲学源自 autoresearch 循环：单一可编辑资产、双重评估（结构+实测）、棘轮机制（只保留改进）、独立评分、人在回路。核心修正：LLM-as-judge 的绝对分数是抽样不是测量——同一份未改动的文字换个 judge 评，总分可摆 ±8。因此 **keep/revert 只信 paired 同-judge 比较 + 奇数多数决**，绝对分数只用于 triage 排名。

---

## 进化契约（必须走上进化）

交付不是终点，是第 0 代。每个出厂 skill 自动进入以下契约：

1. **三件套随行**：test-prompts.json / results.tsv / git（或备份链）——缺任何一件视为未出厂
2. **每次真实使用都是一次评估**：用户认可 → results.tsv 记 keep；用户给出差评或判 worse → **强制触发一轮进化**（E0-E3），不许「就这样吧」
3. **同一问题第 2 次 worse → 升级处理**：探索性重写（E2.5）或回炉 F2 内核，不再做表层修补
4. **进化历史是资产**：展示 skill 时展示它的代次与进化记录（results.tsv）——让用户看到它在变强
5. 用户说「优化/升级/评分」= 主动走本管线；用户没说但给了差评 = 被动触发，同样走本管线，**没有豁免**
6. **代表作回流**：成功使用 ≠ 结束——工件择优回填 showcase 并拆解回配方/踩坑（E4，见 forge.md），skill 每被用好一次就变深一次；深度等级 L1 框架级 → L2 工程级 → L3 专家级 随回流晋升

## E0 初始化

```
1. 确认优化范围：全部 skills（扫描已安装目录）→ 用户指定列表
2. git 可用 → 创建分支 auto-evolve/YYYYMMDD-HHMM
   git 不可用 → 询问用户：init 还是文件备份模式（cp SKILL.md SKILL.md.bak.YYYYMMDD-HHMM）
3. results.tsv 不存在 → 创建并写表头（见下）；已存在 → 读取历史优化记录
```

results.tsv 格式（9 列，制表符分隔）：

```tsv
timestamp	commit	skill	old_score	new_score	status	dimension	note	eval_mode
```

`eval_mode` 取值：`paired`（同 judge 比改前改后，keep/revert 唯一权威依据）｜`full_test`（子 agent 跑真实测试题）｜`dry_run`（模拟推演，仅供参考）。paired 行的 `new_score` 栏记投票比数（如 `3-0 better`），`note` 记一句裁断理由。

## E0.5 测试题设计

没有测试题，「实测」维度就是凭空打分。对每个 skill：

1. 读取 SKILL.md 理解它做什么
2. 设计 **3 道测试题（happy_path / complex / failure 各一道）**；已存在 test-prompts.json → 展示并问用户「复用 / 重写 / 追加」
4. **🔴 CHECKPOINT · 展示全部测试题，用户确认后进入评估**

## E1 基线评估（triage 用途）

```
for each skill:
  1. 读取 SKILL.md 全文，按 rubric（见 rubric.md）维度 1-7、9、10 逐项打分（附理由）
  2. 运行时中立性红灯扫描（gate 项，扫描命令与假阳性判别见 rubric.md 末节）
  3. 效果维度（维度 8）：每个测试题 spawn 子 agent——
     with_skill：带着 SKILL.md 执行
     baseline：不带 skill 执行
     对比输出质量打分
  4. 子 agent 不可用 → 干跑验证打分，标 dry_run（判定规则见 testing.md §6：full_test ≥1 次且 dry_run 数 < full_test 数，否则评估失效警告）
  5. 计算加权总分，记入 results.tsv
```

评估完成后展示评分卡（按分数升序，标注每支的结构短板与效果短板）。

**🔴 CHECKPOINT · 🛑 STOP：暂停等用户确认，再进入优化循环。**

## E2 优化循环

```
for each skill（按基线分升序，先修最弱的）:
  round = 0
  while round < MAX_ROUNDS (默认 3):
    round += 1

    # Step 1 诊断：weighted_gap = weight × (10 - score) / 10，取最大者
    #   为什么不用「原始分最低」：低权重维度会制造进步幻觉
    #   加权短板相近（差距 ≤1.0）→ 回退原始分升序
    #   ⚠ 相关簇警告：工作流清晰度/失败分支/检查点三维相关——修其一时
    #     另两维常跟涨，看整簇短板再决定是否同步改，避免下轮白做

    # Step 2 改进方案：改什么（具体段落）、为什么（对应 rubric 条目）、预期提升
    #   改动后体积不得超过原 SKILL.md 的 150%，超了 → 先精简再评
    #   ⚔ 钢人反对（思维工具）：写完方案先构造「最强反对」——为什么这会变差/为什么没必要；
    #     反对成立 → 方案重写，不带着自我怀疑上 commit

    # Step 3 执行 + git commit（message: "evolve {skill}: {改进摘要}"）

    # Step 4 paired 重评：spawn N=3 个独立 judge（close call 升 5，N 保持奇数），
    #   每个 judge 在【同一次调用内】读改前版（git show HEAD~1:<path>）与改后版，
    #   以 rubric 为比较准则（不是各打绝对分），回 {better|worse|tie} + margin{clear|slight} + 一句理由。
    #   同一 judge 同次读两版 → 它那把不准的尺对两版等量作用、在比较中抵销

    # Step 5 共识决策：
    #   better 票数 ≥ worse 票数 → keep（含 tie）
    #     keep 后按 E1 规则重算一次加权总分（triage 展示用，非权威）
    #     连续 2 轮多数为 slight 或 tie → 触顶，break 进 E3（见好就收；
    #     硬凑轮数只会引入「为凑分加冗余」的 over-engineering）
    #   worse 占多 → revert：git revert HEAD（绝不 reset --hard），results.tsv 记录票比与理由，
    #     break（本轮方向已证伪，换维度下轮再说）
    #   单评绝对分出现负 delta ≠ revert 信号；必须 paired 多数判 worse 才 revert

    # Step 6 results.tsv 追加记录

  # 🔴 CHECKPOINT · 该 skill 优化完强制人审：
  #   展示 git diff + 维度分变化 + 测试题输出对比（若跑过）
  #   用户说不好 → 回滚到优化前版本
```

### E2.5 探索性重写（按需触发）

连续 2 个 skill 都在 round 1 就触顶（涨不动）→ 提议探索性重写，突破局部最优：

```
0. 侦察找灵感：先做一轮同类技能侦察（forge.md F1.0，可只精读结构不写完整吸收表），
   看同类/相邻 skill 怎么组织结构与表达——局部最优常常是「没见过别的长法」
1. 选一个瓶颈 skill
2. git stash 保存当前最优版本
3. 从头重写 SKILL.md（重组结构与表达，不是微调）
4. paired 重评
5. 重写版更好 → 采用；否则 git stash pop 恢复
```

**🔴 CHECKPOINT · 🛑 STOP：必须征得用户同意后才执行。**

### 优化策略库（按优先级，每轮只做最高优先级的一个）

| 级别 | 问题 | 修法 |
|------|------|------|
| P0-gate | 运行时中立红灯命中（真红灯） | 中立措辞改写；badge 换三件套（标准/兼容/多运行时）；安装说明三层结构（自动检测一行命令 + 各 runtime 手动路径折叠 + cat 进 context 兜底）；工具硬编码给替代方案 |
| P0-效果 | 实测发现带 skill 比不带还差 / 输出偏离意图 | 查误导性指令；过度约束就精简；输出格式不对就补模板 |
| P1-结构 | 缺触发词 / 缺 Phase 结构 / 缺检查点 | 补中英触发词；重组线性流程；关键决策处插 🔴 |
| P2-具体性 | 步骤模糊 / 缺输入输出规格 / 缺异常处理 | 改具体操作与参数；补格式、路径、示例；补三段式失败表 |
| P3-可读性 | 段落过长 / 重复 / 缺速查 | 拆分+表格；合并去重；加 TL;DR 或决策树 |

## E3 汇总报告

```
## 进化报告
- 优化 skill 数 / 总实验次数 / 保留改进数（比例）/ 回滚次数
- 实测验证：A 次完整测试 / B 次干跑
- triage 分数变化表（Before / After / Δ；数值来自基线与各轮 keep 后的 triage 重算，
  仅展示趋势用——keep/revert 的权威依据始终是 paired 票比，Δ 保留 1 位小数）
- paired 记录表（每轮：维度 / 票比 / margin / 一句裁断理由）
- 主要改进列表（每条对应 skill + 改了什么 + 实测变化）
- 运行时中立度：红灯命中数 X → 0
```

---

## 异常与边界条件（10 条，异常先告知用户再处理，绝不静默跳过）

| 场景 | 触发条件 | 处理动作 |
|---|---|---|
| 不在 git 仓库 | `git rev-parse` 失败 | 询问用户 init 或文件备份模式 |
| results.tsv 缺失 | 文件不存在 | 新建并写表头 |
| results.tsv 损坏 | 列数不匹配 / 非 TSV | 备份为 `.bak.时间戳` 后重建，告知用户 |
| 分支已存在 | `checkout -b` 失败 | 分支名加 `-2`/`-3`；第 3 次失败切回现有分支问用户 |
| `git revert` 失败 | 冲突 / 工作树脏 | 先 stash 重试；仍失败从上个 commit 读出 SKILL.md 覆盖恢复 |
| MAX_ROUNDS 触顶 | 3 轮后仍有短板 | 不强制继续，展示最弱维度问用户「加 1 轮 / 探索性重写 / 收工」 |
| 体积超限 | 新文件 > 原 × 1.5 | 拒绝提交，先精简再评 |
| test-prompts.json 已存在 | 文件已在 | 展示后问「复用 / 重写 / 追加」 |
| SKILL.md 缺失 | 目录存在但无文件 | 该 skill 记 `status=error`，继续下一个 |
| 浮点漂移 | 分数计算 | 总分保留 1 位小数；改进须严格 > 旧分 |

## 进化操作反例黑名单（每轮改动前对照一次，任一命中 → 改方案重写）

| # | 反模式 | 为什么 | 替代做法 |
|---|--------|--------|---------|
| 1 | 同上下文自评自改 | 「我刚改的肯定更好」乐观偏差；LLM-as-judge 对细粒度差异接近抛硬币 | 独立子 agent + paired 奇数多数决 |
| 2 | 绝对分数 delta 当棘轮 | judge 换尺噪音 ±8，会误杀真实增益或保留假改进 | 绝对分只做 triage；keep/revert 走 paired |
| 3 | `git reset --hard` 回滚 | 丢未提交改动、历史断裂 | `git revert` |
| 4 | 为凑分增冗余 | 触顶后硬改 = 加废话 | 触顶 break，见好就收 |
| 5 | 跳过测试题直接评分 | 效果维度凭空打分 | E0.5 强制设计并确认 |
| 6 | 轮内改多维度 | 无法归因 | 每轮 1 维；相关簇例外（同步改但要注明） |
| 7 | dry_run 数 ≥ full_test 数 | 小样本下比例阈值失真，实测维度形同虚设、分数虚高 | 至少 1 次真实 full_test，干跑不得多于实测 |
| 8 | 忽视相关簇单独优化 | 相关维度早被前轮推顶，白做 | 看整簇再决定 |
| 9 | 静默跳过异常 | 破坏棘轮完整性 | 异常表 10 条，先告知再处理 |
