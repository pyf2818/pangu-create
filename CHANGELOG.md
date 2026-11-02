# CHANGELOG · 盘古开天（pangu-create）进化史

> 从 `SKILL.md` 顶部迁出，减少每次触发时的上下文开销；详细实验记录见 [results.tsv](results.tsv)。

## 第 6 代 · v1.5.0（2026-11-02）

- **盘古印记（`scripts/pangu_seal.py`）**：修补 v1.4「触发器只在盘古一侧、被锻造 skill 使用现场无落箱指令」的断环（实测 9 个锻造 skill 的 `SKILL.md` 0/9 提及 `inbox.tsv`）。每个锻造/补盖的 skill 在 `SKILL.md` 末尾携带 `<!-- pangu:seal v1 lineage=... -->` 区块，直接告诉执行 agent 出问题时如何落箱。
- **随行落箱工具（`feedback/log.py`）**：零依赖 CLI（`add` / `list` / `set <行> --status processing|resolved --evidence` / `bump [--depth L2|L3]`），自动净化制表符与换行、禁止无证据置 `resolved`、代次 +1 与深度只升不降一键写回 `pangu.json`。
- **印记指纹豁免（`verify_skill.py`）**：计算 `SKILL.md` 源码指纹时自动剥离 `<!-- pangu:seal ... -->` 区块，盖章或刷新印记不使既有行为回执过期。
- **脚手架升级（`scaffold.py`）**：新建 skill 出厂自带盘古印记与 `feedback/log.py`；新增 `--reseal`（及 `--adopt --seal`）幂等补盖/刷新存量 skill 印记，并按 `results.tsv` 的 `keep` 记录数自动对齐存量 `generation`。
- **注册表、跨目录反馈回收与重部署（`registry.py`）**：支持多根扫描与跨根同血统副本检测；新增 `--collect-feedback`（从已安装副本合并新反馈到权威源）、`--deploy`（把进化后源码同步回副本并保留收件箱与快照）、`--normalize-ledgers`（批量清洗历史 9 列/无表头/多制表符 `results.tsv`）；新增 `seal` 状态列、`minor >= 3` 批量触发统计、代次漂移检测与 P0–P3 **进化队列**。
- **确定性阶段导航与检查点分级（`scripts/next_step.py`）**：根据目录真实文件进度判定当前阶段（Phase 0.5 → F1 → F2 → F3 → F3.6 → F4-F5 → E0-E3）并输出 ≤6 条必做动作，防止大模型通读 800+ 行 `forge.md` 跳步；`quick` 快速档仅保留首尾 2 个硬阻塞检查点，中间全绿自动推进。
- **3-Judge 异构职责盲评与 D3 套话拦截**：`testing.md` 与 `evolve.md` 落地 Judge A（正确性与边界）/ Judge B（精简度与 `>10%` 长度膨胀惩罚）/ Judge C（领域辨识度）+ 正逆序位置交换；`rubric_score.py` D3 新增 `_is_platitude_failure_row` 拦截「重试/检查网络/报错」空泛套话行；盘古自身补齐自包含测试夹具 `tests/fixtures/mini-threejs` 与 D8 盲评实证报告 `references/research/d8-blind-eval.md`。
- **SKILL.md 瘦身与反古德哈特守则**：版本史迁入本文件、34 条完整反模式迁入 [references/anti-patterns.md](references/anti-patterns.md)（编号 1–34）、F3.5/F4 与 `forge.md` 重复的大表改为紧凑索引；`evolve.md` 新增反古德哈特禁令（AP-33：禁止为提分改评分器，改评分器须附正反误判回归集）。

## 第 5 代 · v1.4.0（2026-10-31）

- **技能群关联管理**：锻造/补登记的每个 skill 携带 `pangu.json` 血统清单，`registry.py` 一键扫描全工作区生成注册表（含孤儿检测与吸收源克隆识别）。
- **反馈收件箱**：每个 skill 自带 `feedback/inbox.tsv`，open 的 blocker/major = 强制进化触发器（进化契约 #8）。
- **读有闸、写也有闸**：新增 `gate_sibling` 吸收表闸门与竞争测试「现场可复核证据」行闸；修复 9 处文档口径漂移并新增 `docs-consistency` 守卫套件；修正 rubric 元技能分型探测优先级。

## 第 4 代 · v1.3.0（2026-10-25）

- **只读审计与可变进化分权**：评分/体检零写入、零分支、零账本、零联网。
- **行为回执双哈希绑定**：`tests/verification.json` + 源码/清单双 SHA-256 绑定的新鲜回执（CRLF/LF 归一化）。
- **rubric 诚实化**：D8 实测 19 分、D10 品味 6 分改人工，自动上限 75/100。

## 第 3 代 · v1.2.0

- rubric 分型评分、`verify_skill` 文本型三件套闸门、铁律 13/AP24 合并、英文门面 `README.en.md`。

## 第 2 代 · v1.1.0

- `csvviz-forge` 无人值守实测回流、`scaffold` 格式契约、盲评串行协议、paired 降级合法化、领域工艺图谱 `craft-atlas.md`。
