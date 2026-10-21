#!/usr/bin/env python3
"""
盘古开天 脚手架：为待锻造的目标 skill 创建标准目录结构与初始文件。

用法:
    python3 scaffold.py <目标skill目录> --name <skill-name> [--force]

示例:
    python3 scaffold.py ./.agents/skills/excel-valuation --name excel-valuation

行为:
    1. 创建目录结构（SKILL.md 骨架 / references/ / tests/ / scripts/ / examples/ / assets/showcase/）
    2. 写入 test-prompts.json 空模板（提醒: 测试题先行，基线先跑）、references/design-thesis.md 论点档案、references/promise-table.md 承诺矩阵、tests/failure_injection.py 注入骨架
    3. 已存在时默认拒绝覆盖（--force 覆盖已存在的骨架文件，但绝不删除用户文件）

自包含原则: 所有调研文件都必须生成在目标 skill 目录内部。
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

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

> F2 收尾必填（产出型与工具型适用）。规则见 pangu-create/references/executable-checklist.md §1。
>
> **格式契约（verify_skill.py gate_promise 按此解析）**：
> ① 每行 ≥4 列，第 4 列必须是证据（非空/非 -/非 TODO：日志路径、截图文件名或实测数值）；
> ② 命令列用反引号包命令，且含 python/node/npm/npx/bash/sh/curl/playwright/pytest/verify/finalize 关键词之一；
> ③ 全表禁软化词（视情况/视具体/大致/大概/尽量/随便/看情况）；
> ④ 行数 ≥3；做不到就删承诺，不许留空话。
> 每一行 = 一句对用户的承诺 + 一条能跑的命令 + 一份能指认的证据。

| 承诺（用户视角原话） | 可执行断言 | 命令 | 证据 | 状态 |
|---|---|---|---|---|
| TODO: 「打开就能看」 | TODO: canvas 有像素、0 console error | `python3 scripts/verify.py <产物>` | TODO: logs/xxx.log 或截图 | ⬜ |
| TODO: 「断网也能用」 | TODO: 8 秒内出现降级提示 | `python3 tests/failure_injection.py --offline` | TODO: 降级截图 | ⬜ |
| TODO: 「性能达标」 | TODO: headless ≥30 FPS | `python3 scripts/verify.py --headless <产物>` | TODO: 实测数值 | ⬜ |
"""

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


def main() -> None:
    parser = argparse.ArgumentParser(description="盘古开天 脚手架")
    parser.add_argument("target", help="目标 skill 目录路径")
    parser.add_argument("--name", required=True, help="skill 名（小写 kebab-case，须与目录名一致）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的骨架文件（不删用户文件）")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args.name):
        print(f"❌ skill 名必须是小写 kebab-case（字母/数字/连字符）: {args.name}")
        sys.exit(1)

    root = Path(args.target)
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

    print(f"🔨 脚手架: {root}  (skill: {args.name})")
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
    print("  [ ] references/promise-table.md ≥3 行，每行有断言 + 命令 + 证据")
    print("  [ ] tests/failure_injection.py 改写成真实注入（≥2 类：依赖不可达 / 极端输入 / 环境缺失 / 工具自伤）")
    print("  [ ] 降级提示在用户可见 DOM（看门狗写在 module 之外）")
    print("  [ ] 量化阈值留 1.5× 余量，或 3 次取中位数")
    print("  [ ] python3 scripts/verify_skill.py <本目录> 全过")
    print()
    print("⚠️  交付后（E4/E5 回流）：")
    print("  [ ] 领域工艺参数回填 pangu-create/references/craft-atlas.md（无节则按注册格式开新节）")
    print("  [ ] 走 E5 四问（三源触发：模型自评/机器信号/用户反馈）：流程 / 闸门 / 沉淀 / 动态排异，记入 pangu-create/results.tsv")
    print()
    print("下一步: 读本 skill 目录下 references/forge.md 开始 F1 调研。")


if __name__ == "__main__":
    main()
