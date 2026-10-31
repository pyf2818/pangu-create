# 技能群管理细则（registry 与 lineage）

> SKILL.md「技能群管理」一节的展开。盘古锻造的每个 skill 都是**有关联、可盘点、会自动求救**的资产，不是散落的目录。

## 三件管理载体

| 机制 | 载体 | 规则 |
|------|------|------|
| **血统清单** | 目标 skill 目录的 `pangu.json` | scaffold 出厂即写：`schema` / `lineage_id`（pgn-时间戳-校验）/ `forged_by` / `pangu_version` / `name` / `skill_type`（output/text）/ `domain`（craft-atlas 节名）/ `forge_date` / `generation`（进化代次）/ `depth`（L1/L2/L3）/ `adopted`。存量 skill 补登记：`python3 <盘古目录>/scripts/scaffold.py <目录> --name <名> --adopt [--domain <域>]`——只写 pangu.json + feedback/ 两件，不动其他文件。**进化 keep 后 generation +1；E4 回流后 depth 晋升并同步改清单** |
| **反馈收件箱** | 目标 skill 目录的 `feedback/inbox.tsv` | 6 列：`timestamp / severity / scene / symptom / evidence / status`。severity ∈ blocker（阻断核心承诺）/ major（明显影响）/ minor（打磨项）；status ∈ open / processing / resolved。**使用中遇到任何真实问题当场落行**（进化契约 #8）：blocker/major 且 open = 强制进化触发器；minor 攒 ≥3 条 open 同样触发。修复后置 resolved，evidence 列贴 results.tsv 行号或 commit |
| **注册表** | 盘古目录的 `registry.tsv`（派生缓存，可随时重建） | `python3 <盘古目录>/scripts/registry.py <工作区根> [--sync] [--json] [--strict] [--depth N]`。扫描已登记 skill 的代次/深度/worse 数/open 反馈/回执新鲜度（fresh/stale/missing，比对源码+清单双哈希）；**孤儿检测**（有 SKILL.md 无 pangu.json → 提示 --adopt）；`--strict` 在存在 open blocker/major 或孤儿时退出码 1（巡检/CI 用） |

## 会话内联动协议

1. **激活即查箱**：本 skill 被激活且用户问题涉及某个已登记 skill 时，先读该 skill 的 `feedback/inbox.tsv`——有 open 的 blocker/major → 主动提议先走一轮进化，不等用户点名。
2. **改动即同步**：任何进化 keep / E4 回流 / 补登记之后跑 `registry.py --sync`；交付摘要贴技能群总览。
3. **孤儿分类**：注册表把「有 SKILL.md 无 pangu.json」标为未登记。两类：① 盘古自造的存量 skill → 必须 `--adopt` 补登记；② 吸收用的外部源码克隆（如 research/ 下的参照实现）→ 保持未登记，这是它们的真实身份。
4. **指纹豁免**：`pangu.json`、`feedback/`、`registry.tsv` 不参与 verify_skill 源码指纹——落反馈、同步注册表不会弄脏行为回执；改行为承载文件才会。

## 边界

- registry 只扫用户给的扫描根；已安装到 agent skills 目录的副本要单独扫。
- 注册表是派生缓存：--sync 之后的变动到下次扫描才反映；分歧时以各 skill 目录内的 pangu.json / inbox.tsv 为准。
- 收件箱靠执行 agent 当场落行的纪律；闸门只能发现「缺收件箱」与「open 反馈」，漏记靠定期巡检与用户点名兜底（SKILL.md 诚实边界已声明）。
