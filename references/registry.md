# 技能群管理细则（registry · lineage · 盘古印记）

> SKILL.md「技能群管理」一节的展开。盘古锻造的每个 skill 都是**在现场带标记、有关联、可盘点、会自动求救**的资产，不是散落的目录。

## 四件管理载体（补齐「使用现场→落箱→队列→进化」闭环）

| 机制 | 载体 | 规则 |
|---|---|---|
| **1. 盘古印记（使用现场触发器）** | 目标 `SKILL.md` 末尾 `<!-- pangu:seal v1 lineage=<id> ... -->` … `<!-- /pangu:seal -->` | 为什么必须在 `SKILL.md` 里：被锻造的 skill 在日常使用时，盘古本身并未激活，运行时只加载该 skill 的 `SKILL.md`。印记区块把「遇到真实问题当场跑 `feedback/log.py add`」直接写进目标 `SKILL.md`。`scaffold.py` 新建即盖章；存量 skill 用 `python scripts/scaffold.py <目录> --reseal` 幂等补盖/刷新。**印记区块在 `verify_skill.py` 计算源码指纹时自动剥离，盖章或刷新印记不会让行为回执过期** |
| **2. 血统清单** | 目标 skill 目录的 `pangu.json` | `schema` / `lineage_id`（`pgn-时间戳-校验`）/ `forged_by` / `pangu_version` / `name` / `skill_type`（`output`/`text`）/ `domain`（craft-atlas 节名）/ `forge_date` / `generation`（进化代次）/ `depth`（`L1`/`L2`/`L3`）/ `adopted`。存量补登记：`python scripts/scaffold.py <目录> --name <名> --adopt [--seal]`（默认只加旁路文件不动 `SKILL.md`；加 `--seal` 或 `--reseal` 同步在 `SKILL.md` 盖印记，并按 `results.tsv` 的 `keep` 数自动同步初始 `generation`）。**进化 keep 后跑 `python feedback/log.py bump`（`generation +1`）；E4 回流后 `log.py bump --depth L2|L3`（深度只升不降）** |
| **3. 反馈收件箱与随行工具** | 目标 skill 目录的 `feedback/inbox.tsv` + `feedback/log.py` | 6 列 TSV：`timestamp / severity / scene / symptom / evidence / status`。随 skill 分发的零依赖脚本 `feedback/log.py` 提供四条子命令：① `add --severity blocker|major|minor --scene "..." --symptom "..." [--evidence "..."]`（自动净化制表符/换行并报告是否触发强制进化）② `list [--all]` ③ `set <行号> --status processing|resolved --evidence "..."`（置 `resolved` 强制要求修复证据）④ `bump [--depth L2|L3]`。**open 的 blocker/major，或 open 的 minor ≥3 条 = 强制进化触发器（进化契约 #8）** |
| **4. 注册表与进化队列** | 盘古目录的 `registry.tsv`（派生缓存，可随时重建） | `python scripts/registry.py <根1> [<根2> ...] [--sync] [--json] [--strict] [--require-seal] [--depth N]`。支持**多根扫描**（如同时扫工作区与 `~/.claude/skills`）并检测跨根同 `lineage_id` 副本；检查每支 skill 的代次/深度/worse 数/open 反馈/回执新鲜度（`fresh`/`stale`/`missing`）/**印记状态**（`ok`/`missing`/`mismatch`/`no-tool`）/代次漂移；自动按 P0（open blocker/major）→ P1（open minor ≥3）→ P2（连续 worse）→ P3（印记缺失/代次漂移）输出**可执行进化队列** |

## 会话内联动协议

1. **现场即落箱**：任何带盘古印记的 skill 在使用中遇到用户抱怨、报错、静默失败、产出不合预期，执行 agent 按印记指令当场运行 `python <该skill目录>/feedback/log.py add ...` 落行，禁止口头说「记住了」。
2. **激活即查箱**：本 skill（盘古）被激活且涉及某个已登记 skill 时，先跑 `python <目标目录>/feedback/log.py list` 或 `registry.py`——命中 P0/P1 进化触发器时，主动提议先走一轮进化（E0-E3），不等用户点名。
3. **改动即同步**：任何进化 keep（`log.py bump`）/ E4 回流（`log.py bump --depth L2|L3`）/ 补登记或补盖印记之后，跑 `registry.py <工作区根> --sync` 刷新总览。
4. **孤儿分类**：注册表把「有 `SKILL.md` 无 `pangu.json`」标为未登记。两类：① 盘古自造的存量 skill → 用 `--adopt --seal` 补登记并盖章；② 吸收用的外部源码克隆（如 `research/` 下的参照实现）→ 保持未登记，这是它们的真实身份。
5. **指纹豁免**：`pangu.json`、`feedback/`、`registry.tsv` 以及 `SKILL.md` 内的 `<!-- pangu:seal ... -->` 区块均不参与 `verify_skill.py` 源码指纹——落反馈、盖印记、同步注册表不会弄脏行为回执；改行为承载文件才会。

## 边界

- 多根扫描发现同一 `lineage_id` 的两份副本（工作区源目录 vs 已安装目录）时会发出警告，进化前注意核对两边的 `feedback/inbox.tsv`。
- 注册表是派生缓存：`--sync` 之后的变动到下次扫描才反映；分歧时以各 skill 目录内的 `pangu.json` / `inbox.tsv` 为准。
- 盘古印记解决了「目标 `SKILL.md` 无指令」的断环，但模型在极端上下文压力下仍可能漏跑命令；靠 `registry.py` 定期巡检与用户点名兜底。
