# 反馈收件箱（进化触发器）

> 使用本 skill 过程中遇到的每个真实问题（用户抱怨 / 报错 / 静默失败 / 产出不合预期），
> 执行 agent 必须**当场**追加一行到 inbox.tsv——不许只口头说「记下了」。
> severity=blocker/major 且 status=open 的行 = 强制进化触发器（盘古进化契约 #8）。

severity: blocker（阻断核心承诺）/ major（明显影响产出）/ minor（打磨项）
status:   open → processing（进化轮已认领）→ resolved（evidence 列贴 results.tsv 行号或修复 commit）
