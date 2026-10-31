#!/usr/bin/env python3
"""
盘古开天 脚手架：为待锻造的目标 skill 创建标准目录结构与初始文件。

用法:
    python3 scaffold.py <目标skill目录> --name <skill-name> [--force]
    python3 scaffold.py <已有skill目录> --name <skill-name> --adopt [--domain <领域>] [--forge-date YYYY-MM-DD]

示例:
    python3 scaffold.py ./.agents/skills/excel-valuation --name excel-valuation
    python3 scaffold.py ./legacy-skill --name legacy-skill --adopt --domain 数据可视化

行为:
    1. 创建目录结构（SKILL.md 骨架 / references/ / tests/ / scripts/ / examples/ / assets/showcase/ / feedback/）
    2. 写入 test-prompts.json 空模板（提醒: 测试题先行，基线先跑）、references/design-thesis.md 论点档案、references/promise-table.md 承诺矩阵、tests/failure_injection.py 注入骨架
    3. 写入 pangu.json（血统清单：与盘古关联管理的锚点）与 feedback/inbox.tsv（反馈收件箱：使用问题落点，open 的 blocker/major = 强制进化触发器）
    4. --adopt 只补 pangu.json + feedback/inbox.tsv 两件（登记存量 skill，不动其他文件）
    5. 已存在时默认拒绝覆盖（--force 覆盖已存在的骨架文件，但绝不删除用户文件）

自包含原则: 所有调研文件都必须生成在目标 skill 目录内部。
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 盘古代次锚点：SKILL.md 顶部代次行升级时同步改这里（registry.py 会把 forge 时的版本记进血统清单）
PANGU_VERSION = "1.4.0"

INBOX_HEADER = "timestamp\tseverity\tscene\tsymptom\tevidence\tstatus\n"

INBOX_README = """# 反馈收件箱（进化触发器）

> 使用本 skill 过程中遇到的每个真实问题（用户抱怨 / 报错 / 静默失败 / 产出不合预期），
> 执行 agent 必须**当场**追加一行到 inbox.tsv——不许只口头说「记下了」。
> severity=blocker/major 且 status=open 的行 = 强制进化触发器（盘古进化契约 #8）。

severity: blocker（阻断核心承诺）/ major（明显影响产出）/ minor（打磨项）
status:   open → processing（进化轮已认领）→ resolved（evidence 列贴 results.tsv 行号或修复 commit）
"""


def make_manifest(name: str, adopted: bool, forge_date: str, skill_type: str, domain: str) -> dict:
    stamp = datetime.now().strftime("%Y%m%d%H%M")
    tag = hashlib.sha1(f"{name}:{stamp}".encode("utf-8")).hexdigest()[:4]
    return {
        "schema": 1,
        "lineage_id": f"pgn-{stamp}-{tag}",
        "forged_by": "pangu-create",
        "pangu_version": PANGU_VERSION,
        "name": name,
        "skill_type": skill_type,
        "domain": domain,
        "forge_date": forge_date,
        "generation": 0,
        "depth": "L1",
        "adopted": adopted,
        "notes": "由盘古 --adopt 补登记的存量 skill" if adopted else "",
    }

DESIGN_THESIS_STUB = """# 设计论点：TODO <North Star 名字>

> 产出型 skill 必填；文本型 skill 可删。模板见 references/templates.md §七点六。
>
> **格式契约（verify_skill.py gate_thesis 按此解析，改结构=改闸门）**：
> ① 三问必须是 `## 三问` 标题 + 两列表格恰好 3 行回答（表头/分隔行不算）；
> ② 竞争测试必须是 `## 竞争测试` 段，结论句须含「不成立 / 不通过 / 只有本 / 说不出」字样；
> ③ 独有素材必须是 `## 独有素材` 段 + 表格行首为 `| 数字 |`（8-12 行，下方 1 行是样例，复制补齐）；
> ④ 全文出现 TODO = 闸门必拦。

## 一句话论点
> TODO: 非显然的问题 + 默认做法为什么失败 + 我们的解法（≤100 字）

## 三问
| 问题 | 回答 |
|------|------|
| 非显然的问题是什么？ | TODO |
| 默认做法（通用 AI / 同类 skill）为什么失败？ | TODO |
| 我们的一句话解法是什么？ | TODO |

## 竞争测试
- 最近的同类 skill / 通用 AI：TODO
- 现场可复核证据（实测/参数对照，档案背书不算）：TODO
- 把对方代入论点句是否仍成立：TODO（是 = 不通过）
- 结论：TODO（必须写明「同类代入后不成立/说不出」）

## 独有素材（8-12 条，只有这个主体才有）
| # | 素材 | 换一个同类主体还成立吗？ |
|---|------|----------------------|
| 1 | TODO | TODO |

## 署名作品草案
- 作品名 / 形态：TODO
- 它如何体现论点（3 条）：TODO
- 与默认模板的 3 处实质差异：TODO
"""

PROMISE_TABLE_STUB = """# 承诺→断言矩阵

> F2 收尾必填。规则见 pangu-create/references/executable-checklist.md §1。
>
> **格式契约（verify_skill.py gate_promise 按此解析）**：
> ① 每行 4 列：承诺 | 可执行断言 | 测试 ID | 证据指针；
> ② 第三列必须是 tests/verification.json 里的 suite id（不是命令文本）；
> ③ 第四列必须是 `evidence/verification.json#<同一个 id>`；
> ④ 行数 ≥3；**本表填完还不够，必须用 --execute 真实跑出回执**。
> 占位词（待填写/TODO/自述式结论）会被闸门拒绝——这是故意的。

| 承诺（用户视角原话） | 可执行断言 | 测试 ID | 证据 |
|---|---|---|---|
| （待填写）打开就能用 | （待填写）具体断言 + 数字阈值 | behavior-placeholder | evidence/verification.json#behavior-placeholder |
| （待填写）异常输入有可见降级 | （待填写）注入后断言用户可见文案 | failure-injection | evidence/verification.json#failure-injection |
| （待填写）结果可复现 | （待填写）重复执行哈希一致 | behavior-placeholder | evidence/verification.json#behavior-placeholder |
"""

VERIFICATION_STUB = {
    "version": 1,
    "suites": [
        {
            "id": "behavior-placeholder",
            "kind": "behavior",
            "command": ["python", "tests/test_placeholder.py"],
            "timeout_seconds": 60,
            "expect": {"exit_code": 0, "stdout_regex": "OK"},
        },
        {
            "id": "failure-injection",
            "kind": "failure_injection",
            "categories": ["dependency_unavailable", "extreme_input"],
            "command": ["python", "tests/failure_injection.py", "--offline", "--empty"],
            "timeout_seconds": 60,
            "expect": {"exit_code": 0, "stdout_regex": "PASS"},
        },
    ],
}

PLACEHOLDER_TEST = '''#!/usr/bin/env python3
"""占位测试：故意失败。实现真实断言后替换本文件，别改 manifest 期望值来变绿。"""
import sys

print("NOT_IMPLEMENTED: 还没有可执行断言", file=sys.stderr)
sys.exit(1)
'''

FAILURE_INJECTION_SKELETON = '''#!/usr/bin/env python3
"""
故障注入：验证异常路径不是「代码看起来会处理」，而是真的会处理。

F3.6 必过闸门（至少覆盖两类注入）。按产物类型改写下面的 run_case。
退出码: 0 全部符合预期 / 1 有场景未达预期（产品缺陷）/ 2 环境不满足（工具自伤，不算产品缺陷）
"""

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def run_case(name, expect, fn):
    try:
        got = fn()
    except Exception as e:
        got = f"exception: {e}"
    ok = (expect in str(got)) if isinstance(expect, str) else bool(got)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: 期望「{expect}」实际「{got}」")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="模拟依赖不可达（拦 CDN / 断网）")
    ap.add_argument("--empty", action="store_true", help="极端输入：空数据 / 0 条")
    args = ap.parse_args()

    cases = []
    if args.offline:
        # TODO: 用 route/abort 拦掉 CDN 域名，断言用户可见 DOM 里出现降级提示
        cases.append(("依赖不可达 → 有降级提示", "降级提示", lambda: "TODO"))
    if args.empty:
        # TODO: 喂空数组 / 0 条数据，断言不崩、有兜底文案
        cases.append(("空数据 → 兜底文案", "无数据", lambda: "TODO"))

    if not cases:
        print("未选择场景：用 --offline / --empty 指定（至少两类）")
        return 2

    ok = all(run_case(*c) for c in cases)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
'''

RESEARCH_FILES = [
    ("00-positioning.md", "定位（一句话定位 + 依据，F1.0 侦察后可回写差异化）"),
    ("01-practices.md", "权威实践与方法论"),
    ("02-failures.md", "真实失败案例与坑"),
    ("03-toolchain.md", "工具链与脚本资产"),
    ("04-sibling-skills.md", "同类技能侦察与吸收表（含差异化机会）"),
    ("05-anti.md", "反模式与争议"),
    ("06-recent.md", "领域最新动态"),
    ("baseline.md", "基线测试产出（F0.5 生成，不带 skill 的原样回答）"),
]

TEST_PROMPTS_TEMPLATE = [
    {
        "id": 1,
        "type": "happy_path",
        "prompt": "TODO: 用户会真的打出来的原话（带具体路径/参数/口语）",
        "expected": "TODO: 好产出的判据，一句话",
    },
    {
        "id": 2,
        "type": "complex",
        "prompt": "TODO: 更复杂或有歧义的场景",
        "expected": "TODO: 判据",
    },
    {
        "id": 3,
        "type": "failure",
        "prompt": "TODO: 易错边界场景",
        "expected": "TODO: 应触发失败分支/诚实承认，而不是编造",
    },
]

SKILL_MD_SKELETON = """---
name: {name}
description: |
  TODO: 一句话说明这个 skill 做什么。
  触发词：「TODO」「TODO」。
  模糊需求也触发：「TODO 用户会怎么描述这个需求」。
  English: "TODO"。
  （只写做什么+何时用+触发词；绝不总结工作流；总长 ≤1024 字符）
---

# {name} · TODO 一句话定位

> TODO 一句最能代表本 skill 方法论的核心理念

## 铁律（违反即停）

<!-- TODO: 5-12 条，每条带为什么。从失败调研反推，只收「违反必出事故」的 -->

## 执行协议（Agentic Protocol）

<!-- TODO: 问题分类表（事实型先核实 / 方法型直接执行 / 混合型先取事实再套方法）
     核实维度从铁律与心智模型推导，不写通用的「搜索相关信息」 -->

## 工作流

<!-- Phase 0: 入口分流/前置检查表
     Phase 1+: 步骤，每步 输入 → 操作 → 输出；关键步骤后跟三段式失败表
     🔴 CHECKPOINT: 用户确认点 -->

## 品味守则

<!-- TODO: 领域审美倾向 / AI 俗手清单 / 推荐做法与工作示例 -->

## 反模式黑名单

<!-- | # | 反模式 | 为什么 / 替代做法 | -->

## 特殊场景

<!-- 冷门输入 / 参照物模式 / 更新模式（增量更新哪些维度、调研时间标在哪） -->

## 反馈与进化（进化契约，不豁免）

- 本 skill 由 pangu-create 锻造（血统见 pangu.json）；交付只是第 0 代。
- **反馈落箱**：使用中遇到任何真实问题（用户抱怨 / 报错 / 静默失败 / 产出不合预期），
  当场在 `feedback/inbox.tsv` 追加一行（timestamp/severity/scene/symptom/evidence/status=open），不许只口头记。
- **自动触发**：severity=blocker/major 且 open 的反馈 = 强制进化轮（E0-E3，盘古 evolve.md 契约 #8）；
  同一问题第 2 次出现 → 升级探索性重写，不做表层修补。
- 修复后把对应行置 resolved，evidence 列贴 results.tsv 行号或修复 commit。
- 每轮进化 keep 后 `pangu.json` 的 generation +1；代表作回流（E4）后 depth 晋升（L1→L2→L3）。

## 诚实边界

- TODO: 具体局限 1
- TODO: 具体局限 2
- TODO: 具体局限 3
- 调研时间：{today}，之后的变化未覆盖
"""


def write_if_absent(path: Path, content: str, force: bool) -> str:
    if path.exists() and not force:
        return f"  skip  {path.relative_to(path.anchor)} （已存在）"
    path.write_text(content, encoding="utf-8")
    return f"  write {path}"


def _infer_forge_date(root: Path, adopt: bool) -> str:
    """--adopt 且有 results.tsv 时用首条记录日期做 forge_date；否则今天。"""
    tsv = root / "results.tsv"
    if adopt and tsv.exists():
        try:
            import csv as _csv
            with tsv.open(encoding="utf-8-sig", newline="") as fh:
                for row in _csv.reader(fh, delimiter="\t"):
                    cells = [c.strip() for c in row]
                    if cells and cells[0] and not cells[0].startswith("#") and cells[0].lower() not in {"timestamp", "ts", "time"}:
                        return cells[0][:10]
        except (OSError, csv.Error):
            pass
    return date.today().isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="盘古开天 脚手架")
    parser.add_argument("target", help="目标 skill 目录路径")
    parser.add_argument("--name", required=True, help="skill 名（小写 kebab-case，须与目录名一致）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的骨架文件（不删用户文件）")
    parser.add_argument("--adopt", action="store_true",
                        help="登记模式：只写 pangu.json + feedback/inbox.tsv 两件，不动其他文件（用于给存量 skill 补血统）")
    parser.add_argument("--skill-type", choices=["output", "text"], default="output", help="skill 分型（默认 output）")
    parser.add_argument("--domain", default="TODO-领域名（craft-atlas 节名）", help="领域名（craft-atlas 节名，回填 atlas 后同步）")
    parser.add_argument("--forge-date", default=None, help="锻造日期 YYYY-MM-DD（默认今天；--adopt 且有 results.tsv 时取首条记录日期）")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args.name):
        print(f"❌ skill 名必须是小写 kebab-case（字母/数字/连字符）: {args.name}")
        sys.exit(1)

    root = Path(args.target)

    forge_date = args.forge_date
    if forge_date is None:
        forge_date = _infer_forge_date(root, args.adopt)

    if args.adopt:
        if not (root / "SKILL.md").is_file():
            print(f"❌ --adopt 要求目标已有 SKILL.md: {root}")
            sys.exit(1)
        root.mkdir(parents=True, exist_ok=True)
        manifest = make_manifest(args.name, adopted=True, forge_date=forge_date,
                                 skill_type=args.skill_type, domain=args.domain)
        print(f"🩸 补登记血统: {root}")
        print(write_if_absent(root / "pangu.json",
                              json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", args.force))
        (root / "feedback").mkdir(parents=True, exist_ok=True)
        print(write_if_absent(root / "feedback" / "inbox.tsv", INBOX_HEADER, args.force))
        print(write_if_absent(root / "feedback" / "README.md", INBOX_README, args.force))
        print()
        print("⚠️ 登记后动作：")
        print("  [ ] 同步注册表: python3 <盘古目录>/scripts/registry.py <工作区根> --sync")
        print("  [ ] 领域已在 craft-atlas.md 有节 → 把 pangu.json 的 domain 对齐节名；无节 → E4 回填时注册")
        print("  [ ] 进化 keep 后 generation +1；E4 回流后 depth 晋升（L1/L2/L3）")
        return

    if root.exists() and not args.force:
        existing = [p.name for p in root.iterdir()]
        if existing:
            print(f"⚠️  目录已存在且非空: {root}")
            print("   确认是更新已有 skill？加 --force 覆盖骨架文件（不会删除你的文件）。")
            sys.exit(1)

    (root / "references" / "research").mkdir(parents=True, exist_ok=True)
    (root / "references" / "sources").mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "examples").mkdir(parents=True, exist_ok=True)
    (root / "assets" / "showcase").mkdir(parents=True, exist_ok=True)
    (root / "feedback").mkdir(parents=True, exist_ok=True)

    manifest = make_manifest(args.name, adopted=False, forge_date=forge_date,
                             skill_type=args.skill_type, domain=args.domain)

    print(f"🔨 脚手架: {root}  (skill: {args.name})")
    print(write_if_absent(root / "pangu.json",
                          json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", args.force))
    print(write_if_absent(root / "feedback" / "inbox.tsv", INBOX_HEADER, args.force))
    print(write_if_absent(root / "feedback" / "README.md", INBOX_README, args.force))
    print(write_if_absent(root / "SKILL.md", SKILL_MD_SKELETON.format(name=args.name, today=date.today().isoformat()), args.force))
    print(write_if_absent(
        root / "references" / "design-thesis.md",
        DESIGN_THESIS_STUB,
        args.force,
    ))
    print(write_if_absent(
        root / "references" / "promise-table.md",
        PROMISE_TABLE_STUB,
        args.force,
    ))
    print(write_if_absent(
        root / "tests" / "failure_injection.py",
        FAILURE_INJECTION_SKELETON,
        args.force,
    ))
    print(write_if_absent(
        root / "tests" / "test_placeholder.py",
        PLACEHOLDER_TEST,
        args.force,
    ))
    print(write_if_absent(
        root / "tests" / "verification.json",
        json.dumps(VERIFICATION_STUB, ensure_ascii=False, indent=2) + "\n",
        args.force,
    ))
    print(write_if_absent(
        root / "test-prompts.json",
        json.dumps(TEST_PROMPTS_TEMPLATE, ensure_ascii=False, indent=2) + "\n",
        args.force,
    ))
    for fname, desc in RESEARCH_FILES:
        header = f"# {desc}\n\n调研时间：\n模式：\n\n## 关键发现\n\n## 失败模式 → 铁律候选\n\n## 矛盾与待验证\n\n## 信息不足\n"
        print(write_if_absent(root / "references" / "research" / fname, header, args.force))

    tsv_header = "timestamp\tcommit\tskill\told_score\tnew_score\tstatus\tdimension\tnote\teval_mode\tevidence\n"
    print(write_if_absent(root / "results.tsv", tsv_header, args.force))

    print()
    print("⚠️  立项检查单（Phase 0.5）：")
    print("  [ ] 定位一句话已写入手项摘要；手法初选完成（读 playbooks.md 手法速查表）")
    print("  [ ] 档位已向用户确认（快速/标准/精品）")
    print("  [ ] test-prompts.json 已填 3 道真实测试题（happy_path/complex/failure 各一）")
    print("  [ ] 基线已跑（不带 skill 回答测试题，存 research/baseline.md）")
    print("  [ ] 原句回放 + 排除清单已写入 references/research/00-intent.md")
    print("  [ ] results.tsv 表头已就位（含 evidence 列）；若尚未纳入 git，建议在目标目录 git init（进化棘轮需要）")
    print("  [ ] 🔴 CHECKPOINT 已向用户展示立项摘要")
    print()
    print("⚠️  产出型必过闸门（F3 前）：")
    print("  [ ] references/design-thesis.md 三问无空话 + 竞争测试通过（同类说不出同样的话）")
    print("  [ ] 主体盘点 8-12 条「换同类主体就不成立」的素材")
    print("  [ ] examples/ ≥3 件可打开范例；assets/showcase/ 1 件手写署名作品")
    print("  [ ] scripts/ 核心变换脚本化 + 一键 verify/finalize")
    print()
    print("⚠️  可执行预检（F3.6，不过不进 F4）：")
    print("  [ ] references/promise-table.md ≥3 行：承诺 | 断言 | 测试 ID | evidence/verification.json#ID")
    print("  [ ] tests/verification.json 的测试命令替换占位实现（占位测试故意失败，别改期望值变绿）")
    print("  [ ] tests/failure_injection.py 真实注入 ≥2 类（依赖不可达 / 极端输入 / 环境缺失 / 工具自伤）")
    print("  [ ] 降级提示在用户可见 DOM（看门狗写在 module 之外）")
    print("  [ ] 量化阈值留余量：单次 ≥1.5×，或 3 次采样中位数与最小值均 ≥ 阈值")
    print("  [ ] python3 scripts/verify_skill.py <本目录> --execute 通过并产出 evidence/verification.json")
    print("  [ ] python3 scripts/verify_skill.py <本目录> --check 复验回执（源码变了会判过期）")
    print()
    print("⚠️  交付后（E4/E5 回流）：")
    print("  [ ] 领域工艺参数回填 pangu-create/references/craft-atlas.md（无节则按注册格式开新节）")
    print("  [ ] 走 E5 四问（三源触发：模型自评/机器信号/用户反馈）：流程 / 闸门 / 沉淀 / 动态排异，记入 pangu-create/results.tsv")
    print()
    print("⚠️  技能群管理（与盘古关联）：")
    print("  [ ] pangu.json 血统清单已生成（进化 keep 后 generation +1，E4 回流后 depth 晋升）")
    print("  [ ] feedback/inbox.tsv 反馈收件箱已就位（使用中的问题当场落行，open 的 blocker/major = 强制进化触发器）")
    print("  [ ] 交付时同步注册表: python3 <盘古目录>/scripts/registry.py <工作区根> --sync")
    print()
    print("下一步: 读本 skill 目录下 references/forge.md 开始 F1 调研。")


if __name__ == "__main__":
    main()
