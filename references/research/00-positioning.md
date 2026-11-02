# 盘古开天（pangu-create）定位简报（七要素）

## 0. 原句回放
> 「帮我打造一个元技能（God Skill）：用户一句话描述想要什么 skill，它能自动做同类侦察、领域深研、提炼三层内核、组装确定性核心与范例、跑可执行闸门验证，并且所有由它创建的 skill 都带上盘古印记，组成技能群在使用中遇到问题自动触发进化。」

## 1. 领域与类型
- **领域**：AI Agent 元技能工程（Skill Forging / Evaluation / Fleet Evolution）
- **分型**：`text`（规则/协议/编排型元技能，兼具确定性脚手架、评分器、注册表与闸门脚本）
- **档位**：`flagship`（精品档，L3 深度）

## 2. 目标用户与触发场景
- **新建流（Forge）**：用户用一句话或模糊想法要求创建某个领域的专业 Skill（产出型或规则型）。
- **进化流（Evolve）**：对已有 Skill 做定向精炼，或在使用过程中通过 `feedback/log.py` 积累满触发条件后自动进 E0-E3。
- **技能群管理（Fleet Registry）**：跨目录盘点所有盘古子技能的血统、代次、收件箱、回执新鲜度与印记完整性，并在已安装副本与工作区源之间汇总反馈与重部署。

## 3. 输入与输出契约
- **输入**：一句话需求（新建流）、目标 Skill 目录 + 反馈/痛点（进化流）、工作区根目录（技能群巡检）。
- **输出**：
  - 含 `pangu.json` + `<!-- pangu:seal ... -->` + `feedback/inbox.tsv` + `feedback/log.py` 的完整 Skill 目录；
  - `references/research/` 调研底稿、`references/kernel.md` 三层内核、`references/promise-table.md` 四列承诺矩阵；
  - `tests/verification.json` 行为与故障注入清单 + `evidence/verification.json` 双哈希新鲜回执；
  - `results.tsv` 10 列进化账本 + `registry.tsv` 技能群总览。

## 4. 三层核心（铁律 / 模型 / 品味）
- **铁律层**：不许跳过无 skill 基线（AP-18）、不许用存在性检查冒充行为验证（AP-27）、不许修改自身评分函数刷分（AP-33）、不许丢失盘古印记与反馈落箱钩子（AP-34）。
- **模型层**：`scaffold.py` → `next_step.py` 阶段导航 → F0.5~F5 锻造 → `verify_skill.py` 双哈希回执 → `feedback/log.py` 原地落箱 → `registry.py` 跨目录汇总与部署。
- **品味层**：SKILL.md 正文保持精焊（≤500 行），按阶段懒加载 `references/*.md`；快速档仅保留首尾 2 个硬阻塞检查点，标准/精品档保留全量检查点。

## 5. 失败分支与诚实边界
- **不可验证承诺拦截**：遇到「预测明天股票涨跌」「稳赚量化策略」等不可验证承诺，在 Phase 0.5 当场降级为历史回测/方法论 Skill 或拒绝硬造。
- **反模式熔断**：连续 2 轮进化 `worse` 自动终止并输出诊断报告，不硬凑轮次。

## 6. 验收标准（绑定 `tests/verification.json`）
- `quality_check.py SKILL.md` 11/11 全过；`rubric_score.py SKILL.md` 75.0/75；
- `verify_skill.py . --type text --check` 5 套行为与对抗回归套件全绿，双哈希回执 `fresh`；
- `registry.py .. --strict` 0 孤儿、0 账本警告、10/10 印记 `ok`。
