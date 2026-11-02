# 同类 Skill 侦察与吸收表（04-sibling-skills）

> 盘古开天（`pangu-create`）立项与 v1.5 迭代期间，针对主流元技能（Skill Creator / Auto-Research / Prompt Optimizer）的横向对比与吸收策略。

| 来源 skill | 值得吸收的手法 | 吸收方式 | 它的短板（差异化机会） |
|---|---|---|---|
| Anthropic `skill-creator`（官方示例） | 强调渐进披露（`SKILL.md` ≤500 行 + `references/`）与触发词设计，提供基础打包脚本 | **直接吸收**：渐进披露红线（500 行）与 Description 触发词矩阵；**改造吸收**：在此基础上新增 Phase 0.5 无 skill 基线强约束、`verify_skill.py` 双哈希新鲜回执与 `pangu_seal.py` 原地印记 | 1. 无「不带 skill 的基线对照」硬约束，容易自嗨<br>2. 缺少防伪造的可执行测试回执（只有静态 lint）<br>3. 创建完即失联，无技能群血统追踪与使用期反馈闭环 |
| Karpathy `autoresearch`（自主进化循环） | 提出 `results.tsv` 单文件实验账本 + 单变量迭代 + `keep/worse/crash` 决策纪律 | **改造吸收**：10 列 `results.tsv` 进化账本与单维修改纪律，升级为 3-Judge 异构职责盲评（含 Judge B `>10%` 长度膨胀惩罚）与 AP-33 反自评作弊铁律 | 1. 仅面向代码/训练指标，对 Prompt/Skill 缺乏防「越改越啰嗦」的盲评机制<br>2. 缺少防 Goodhart 作弊护栏（Agent 可能修改评估脚本本身刷分） |
| 通用 `prompt-optimizer` / 模板生成器 | 启动快，问卷式收集需求后秒出单文件 Prompt | **反着用**：彻底废除预设品类问卷，改为七要素回放 + 同类侦察；产出型强制 `design-thesis.md` 竞争测试 + `examples/` 3 件套 + `next_step.py` 确定性状态机导航 | 1. 预设死板品类问卷，不懂跨领域工艺调研<br>2. 产出型任务只有口号（「高质量、现代感」），无数值锚点与参考范例<br>3. 流程长文档让大模型后半程跳步 |
