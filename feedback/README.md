# 反馈收件箱（进化触发器）

> 使用本 skill 过程中遇到的每个真实问题（用户抱怨 / 报错 / 静默失败 / 产出不合预期），
> 执行 agent 必须**当场**记一行——不许只口头说「记下了」。优先用工具写，避免手写 TSV 写坏：
>
>     python feedback/log.py add --severity major --scene "在做什么" --symptom "出了什么问题" --evidence "报错/路径/原话"
>
> severity=blocker/major 且 status=open，或 open 的 minor ≥3 条 = 强制进化触发器（盘古进化契约 #8）。

severity: blocker（阻断核心承诺）/ major（明显影响产出）/ minor（打磨项）
status:   open → processing（进化轮已认领）→ resolved（必须附修复证据：results.tsv 行号 / commit / 回执）

其他命令：
- `log.py list [--all]`：看未关闭的反馈与是否触发进化
- `log.py set <行号> --status processing|resolved --evidence "..."`：认领 / 关闭（resolved 必须带证据）
- `log.py bump [--depth L2|L3]`：进化 keep 后代次 +1（深度只升不降），写回 ../pangu.json

无 Python 时手动追加（6 列，制表符分隔）：timestamp / severity / scene / symptom / evidence / status
