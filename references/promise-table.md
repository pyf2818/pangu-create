# 承诺→断言矩阵（盘古自身）

> 盘古的承诺不是「文档写得全」，而是「闸门能否拦住假证据 / 交付是否必须真实执行」。
> 每行的测试 ID 对应 [tests/verification.json](../tests/verification.json)，证据必须由
> `python scripts/verify_skill.py . --type text --execute` 生成后指向回执。
> 这张表不能自证；`--execute` 失败或回执过期，本表即视为无证据。

| 承诺（用户视角） | 可执行断言 | 测试 ID | 证据 |
|---|---|---|---|
| 结构预检不会冒充行为验收 | 默认模式 `delivery_ready=false`；只有完整 `--execute` 生成的新鲜回执才可能为 true | tools-regression | evidence/verification.json#tools-regression |
| 伪造、过期、部分或环境故障回执会被拒绝 | 临时技能树中构造 18 类攻击（非法命令/错绑证据/源码变化/清单变化/部分跑/畸形回执/exit 2），闸门逐条拒绝 | failure-injection | evidence/verification.json#failure-injection |
| 新技能不会空手变绿 | 脚手架生成故意失败的占位测试与清单，`--execute` 必须报失败且 `delivery_ready=false` | scaffold-contract | evidence/verification.json#scaffold-contract |
| 锻造的 skill 与盘古关联管理，使用问题自动触发进化 | scaffold 出厂即写 pangu.json + feedback/inbox.tsv；registry.py 聚合血统/账本/收件箱/回执新鲜度，检出孤儿与 open blocker/major（--strict 退出码 1），--sync 落 registry.tsv；scaffold --adopt 只加两件文件且从 results.tsv 推断 forge_date | registry-fleet | evidence/verification.json#registry-fleet |
| 吸收表与竞争测试不能空转过闸 | gate_sibling 拦「存在但空壳/无吸收方式」的 04-sibling-skills.md；gate_thesis 要求竞争测试含「现场可复核证据」行（有路径/数值落点），无证据行即 FAIL | failure-injection | evidence/verification.json#failure-injection |
| 文档口径漂移会被机器拦截 | SKILL.md 与 references/ 的管线顺序（F3.5→F3.6）、硬产物计数（四件）、命名（Phase 0.5）、观感三档、迭代上限口径、质量维度卡列结构、收件箱表头、血统 schema 跨文件一致；11 项断言任何一项漂移即 FAIL | docs-consistency | evidence/verification.json#docs-consistency |
