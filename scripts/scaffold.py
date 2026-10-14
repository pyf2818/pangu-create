#!/usr/bin/env python3
"""
super-create 脚手架：为待锻造的目标 skill 创建标准目录结构与初始文件。

用法:
    python3 scaffold.py <目标skill目录> --name <skill-name> [--force]

示例:
    python3 scaffold.py ./.agents/skills/excel-valuation --name excel-valuation

行为:
    1. 创建目录结构（SKILL.md 骨架 / test-prompts.json / references/research/ / sources/ / scripts/）
    2. 写入 test-prompts.json 空模板（提醒: 测试题先行，基线先跑）
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
    parser = argparse.ArgumentParser(description="super-create 脚手架")
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

    print(f"🔨 脚手架: {root}  (skill: {args.name})")
    print(write_if_absent(root / "SKILL.md", SKILL_MD_SKELETON.format(name=args.name, today=date.today().isoformat()), args.force))
    print(write_if_absent(
        root / "test-prompts.json",
        json.dumps(TEST_PROMPTS_TEMPLATE, ensure_ascii=False, indent=2) + "\n",
        args.force,
    ))
    for fname, desc in RESEARCH_FILES:
        header = f"# {desc}\n\n调研时间：\n模式：\n\n## 关键发现\n\n## 失败模式 → 铁律候选\n\n## 矛盾与待验证\n\n## 信息不足\n"
        print(write_if_absent(root / "references" / "research" / fname, header, args.force))

    tsv_header = "timestamp\tcommit\tskill\told_score\tnew_score\tstatus\tdimension\tnote\teval_mode\n"
    print(write_if_absent(root / "results.tsv", tsv_header, args.force))

    print()
    print("⚠️  立项检查单（Phase 0.5）：")
    print("  [ ] 定位一句话已写入手项摘要；手法初选完成（读 playbooks.md 手法速查表）")
    print("  [ ] 档位已向用户确认（快速/标准/精品）")
    print("  [ ] test-prompts.json 已填 3 道真实测试题（happy_path/complex/failure 各一）")
    print("  [ ] 基线已跑（不带 skill 回答测试题，存 research/baseline.md）")
    print("  [ ] results.tsv 表头已就位；若尚未纳入 git，建议在目标目录 git init（进化棘轮需要）")
    print("  [ ] 🔴 CHECKPOINT 已向用户展示立项摘要")
    print()
    print("下一步: 读本 skill 目录下 references/forge.md 开始 F1 调研。")


if __name__ == "__main__":
    main()
