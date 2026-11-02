#!/usr/bin/env python3
"""
盘古开天 阶段状态机导航器（next_step.py）：看目录真实文件状态决定「当前在哪一步、缺什么、下一个检查点是什么」。

为什么需要它:
  references/forge.md 有 800+ 行；让大模型一次通读长文档再靠记忆走完 F0.5→F5，
  后半程极易注意力衰减而跳步或漏检查点。本脚本把长文档变成确定性状态机：
  每次只输出当前阶段的缺失项、必做动作（≤6 条）以及当前档位下的 CHECKPOINT 规则。

用法:
  python scripts/next_step.py <目标skill目录> [--tier quick|standard|flagship] [--type auto|output|text] [--json]

档位检查点分级:
  - quick（快速档）：仅保留 2 个硬阻塞 🔴 CHECKPOINT（① Phase 0.5 立项+测试题确认 ② F4/F5 最终测试对比与交付收货），中间阶段全绿自动推进、异常才停
  - standard / flagship（标准/精品档）：保留全量阶段阻塞 🔴 CHECKPOINT

退出码: 0 已达出厂态 / 1 仍在锻造或有待处理进化触发器 / 2 目录参数错误
"""

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_evolution as AE  # noqa: E402
import registry as REG  # noqa: E402
import rubric_score as RS  # noqa: E402
import verify_skill as VS  # noqa: E402


def _has_real_content(path: Path, min_chars: int = 80) -> bool:
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return False
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    body = "\n".join(lines)
    return len(body) >= min_chars and "TODO" not in body


def _any_real_content(root: Path, rel_paths: list[str], min_chars: int = 60) -> tuple[bool, str]:
    for rel in rel_paths:
        if _has_real_content(root / rel, min_chars):
            return True, f"已落盘（{rel}）"
    return False, f"缺 {rel_paths[0]} 或内容为空"


def _prompts_ready(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "缺 test-prompts.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return False, f"test-prompts.json 不可解析: {exc}"
    if not isinstance(data, list) or len(data) < 3:
        return False, "test-prompts.json 需至少 3 道题（happy_path / complex / failure）"
    for item in data:
        if not isinstance(item, dict) or "TODO" in str(item.get("prompt", "")) or "TODO" in str(item.get("expected", "")):
            return False, "test-prompts.json 仍有 TODO 占位未填"
    return True, f"{len(data)} 道测试题已就绪"


def evaluate_stages(root: Path, tier: str = "standard", forced_type: str = "auto") -> dict:
    manifest, manifest_errs = REG.load_manifest(root)
    skill_md = root / "SKILL.md"
    skill_type = forced_type
    if skill_type == "auto":
        if manifest and manifest.get("skill_type") in ("output", "text"):
            skill_type = manifest["skill_type"]
        elif skill_md.is_file():
            _, body = RS.split_frontmatter(skill_md.read_text(encoding="utf-8-sig"))
            skill_type = RS.detect_skill_type(skill_md, body, "auto")
        else:
            skill_type = "output"

    inbox_counts, _ = REG.read_inbox(root)
    inbox_triggered = bool(inbox_counts and inbox_counts.get("triggered"))

    stages = []

    # Stage 1: Phase 0.5 立项与基线
    p_ok, p_msg = _prompts_ready(root / "test-prompts.json")
    pos_ok, pos_msg = _any_real_content(root, ["references/research/00-positioning.md", "references/research/00-intent.md"], 60)
    base_ok, base_msg = _any_real_content(root, ["references/research/baseline.md", "references/research/baseline/baseline.md"], 60)
    s0_checks = [
        ("pangu.json 血统清单", manifest is not None and not manifest_errs,
         "已就位" if manifest and not manifest_errs else ("; ".join(manifest_errs) or "缺 pangu.json（跑 scaffold.py）")),
        ("00-positioning.md 七要素简报", pos_ok, pos_msg),
        ("test-prompts.json 三道测试题", p_ok, p_msg),
        ("baseline.md 无 skill 基线产出", base_ok, base_msg),
    ]
    stages.append({
        "id": "Phase0.5",
        "title": "第一阶段（Phase 0.5）：理解定义与测试基线",
        "passed": all(ok for _, ok, _ in s0_checks),
        "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in s0_checks],
        "actions": [
            "原句回放 + 七要素扩写写入 references/research/00-positioning.md",
            "填妥 test-prompts.json（happy_path / complex / failure 三题，去掉 TODO）",
            "不带 skill 跑一遍三道测试题，原样存入 references/research/baseline.md",
        ],
        "checkpoint": "🔴 CHECKPOINT #1（所有档位必停）：向用户展示【定位简报 + 档位 + 3 道测试题 + 基线摘要】并附 2-4 个选择题，确认后才进 F1",
        "blocking": True,
    })

    # Stage 2: F1 同类侦察与多源调研
    sib_ok, sib_msg = VS.gate_sibling(root)
    req_research = [
        ("01-practices.md 权威实践", ["references/research/01-practices.md", "research/shared/iron-rules.md"]),
        ("02-failures.md 真实失败案例", ["references/research/02-failures.md", "research/shared/anti-patterns.md"]),
    ]
    if tier in ("standard", "flagship"):
        req_research.extend([
            ("03-toolchain.md 工具链", ["references/research/03-toolchain.md", "references/craft-atlas.md"]),
            ("05-anti.md 反模式/空白图", ["references/research/05-anti.md", "references/research/05-gap-map.md", "references/anti-patterns.md"]),
            ("06-recent.md 最新动态", ["references/research/06-recent.md", "CHANGELOG.md"]),
        ])
    s1_checks = [("04-sibling-skills.md 同类吸收表", sib_ok, sib_msg)]
    for label, candidates in req_research:
        ok, detail = _any_real_content(root, candidates, 60)
        s1_checks.append((label, ok, detail))
    stages.append({
        "id": "F1",
        "title": f"F1：同类侦察与多源调研（{tier} 档）",
        "passed": all(ok for _, ok, _ in s1_checks),
        "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in s1_checks],
        "actions": [
            "先读盘古 research/shared/ 通用铁律/反模式，再搜同类 skill 落盘 04-sibling-skills.md（含吸收方式）",
            "按档位完成 references/research/ 下各调研维度文件并标注来源可信度",
            "读 references/forge.md「F1 同类侦察 + 多源调研」（只读 F1 节，勿通读全文）",
        ],
        "checkpoint": (
            "⚡ 快速档免停：F1 全绿自动进 F2（默认方向记入 results.tsv）"
            if tier == "quick"
            else "🔴 CHECKPOINT #2：展示同类覆盖图 + 空白点分析，让用户选择成熟方向或创新方向"
        ),
        "blocking": tier != "quick",
    })

    # Stage 3: F2 内核提炼与承诺矩阵
    k_ok, k_msg = _any_real_content(root, ["references/kernel.md", "references/playbooks.md"], 80)
    s2_checks = [
        ("kernel.md 三层内核", k_ok, k_msg),
    ]
    if skill_type == "output":
        th_ok, th_msg = VS.gate_thesis(root)
        s2_checks.append(("design-thesis.md 设计论点", th_ok, th_msg))
    ct_ok, ct_msg = VS.gate_contract(root)
    pr_ok, pr_msg = VS.gate_promise(root)
    s2_checks.append(("tests/verification.json 行为与注入清单", ct_ok, ct_msg))
    s2_checks.append(("references/promise-table.md 承诺→断言矩阵", pr_ok, pr_msg))
    stages.append({
        "id": "F2",
        "title": "F2：内核提炼与可执行承诺矩阵",
        "passed": all(ok for _, ok, _ in s2_checks),
        "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in s2_checks],
        "actions": [
            "提炼铁律层/模型层/品味层写入 references/kernel.md（产出型先完成 references/design-thesis.md 三问+竞争测试+8条独有素材）",
            "在 tests/verification.json 声明行为测试与 ≥2 类故障注入套件（替换故意失败的 test_placeholder.py）",
            "在 references/promise-table.md 填妥 ≥3 行四列承诺并绑定测试 ID",
        ],
        "checkpoint": "契约就绪直接进 F3（无需阻塞停顿）",
        "blocking": False,
    })

    # Stage 4: F3 构建与确定性核心
    seal_st, seal_warns = REG.seal_status(root, manifest)
    core_ok, core_msg = VS.gate_core(root)
    s3_checks = [
        ("SKILL.md 与盘古印记", skill_md.is_file() and seal_st == "ok",
         "印记 ok" if seal_st == "ok" else ("; ".join(seal_warns) or "缺印记")),
        ("确定性核心脚本", core_ok, core_msg),
    ]
    if skill_type == "output":
        ex_ok, ex_msg = VS.gate_examples(root)
        sg_ok, sg_msg = VS.gate_signature(root)
        rd_ok = _has_real_content(root / "README.md", 80)
        s3_checks.extend([
            ("examples/ 范例集（≥3 件）", ex_ok, ex_msg),
            ("assets/showcase/ 署名作品", sg_ok, sg_msg),
            ("README.md 人类可读门面（F3.5）", rd_ok, "已就绪" if rd_ok else "缺 README.md"),
        ])
    stages.append({
        "id": "F3",
        "title": "F3 & F3.5：构建 SKILL.md、确定性脚本、范例与 README",
        "passed": all(ok for _, ok, _ in s3_checks),
        "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in s3_checks],
        "actions": [
            "按 playbooks.md 与 templates.md 组装 SKILL.md（≤500 行，含失败分支与检查点），确认末尾含盘古印记（scaffold.py --reseal）",
            "实现 scripts/ 确定性校验/构建脚本与 examples/、assets/showcase/（产出型）",
            "运行 python scripts/quality_check.py <目标SKILL.md> 确保静态 11/11 全过",
        ],
        "checkpoint": (
            "⚡ 快速档免停：静态 11/11 全过直接进 F3.6"
            if tier == "quick"
            else "🔴 CHECKPOINT #3（F3.5）：展示 README.md 草稿（快速上手 + 示例输出），确认后进 F3.6"
        ),
        "blocking": tier != "quick",
    })

    # Stage 5: F3.6 可执行预检与新鲜回执
    ev_ok, ev_msg = VS.gate_evidence(root)
    s36_checks = [("evidence/verification.json 新鲜双哈希回执", ev_ok, ev_msg)]
    stages.append({
        "id": "F3.6",
        "title": "F3.6：可执行预检与故障注入回执",
        "passed": ev_ok,
        "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in s36_checks],
        "actions": [
            f"运行 python scripts/verify_skill.py {root} --type {skill_type} --execute 生成新鲜回执",
            f"运行 python scripts/verify_skill.py {root} --type {skill_type} --check 复核双哈希一致",
        ],
        "checkpoint": (
            "⚡ 快速档免停：回执 fresh 直接进 F4/F5"
            if tier == "quick"
            else "🔴 CHECKPOINT #4（F3.6）：展示四件硬产物 + 全量执行日志，确认后进 F4"
        ),
        "blocking": tier != "quick",
    })

    # Stage 6: F4 出厂测试与 F5 进化精炼
    records, tsv_err, _ = AE.parse_tsv(root / "results.tsv") if (root / "results.tsv").is_file() else ([], "缺 results.tsv", [])
    has_eval = bool(records) and not tsv_err
    trio_ok, trio_msg = VS.gate_trio(root)
    s45_checks = [
        ("进化三件套（test-prompts / results.tsv / git或snapshots）", trio_ok, trio_msg),
        ("results.tsv 出厂测试与首轮精炼记录", has_eval, f"已有 {len(records)} 条记录" if has_eval else (tsv_err or "尚无测试/进化记录")),
    ]
    stages.append({
        "id": "F4-F5",
        "title": "F4 & F5：独立盲评测试、首轮进化精炼与技能群同步",
        "passed": all(ok for _, ok, _ in s45_checks),
        "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in s45_checks],
        "actions": [
            "spawn 独立子 agent 跑 3 道测试题并与 baseline.md 盲评对比（3-Judge 异构职责：正确性 / 精简度长度惩罚 / 领域辨识度）",
            "走一轮 F5 单维改进 + paired 多数决，记录写入 results.tsv 并跑 feedback/log.py bump",
            "运行 python scripts/registry.py <工作区根> --sync 同步技能群注册表",
        ],
        "checkpoint": "🔴 CHECKPOINT #Final（所有档位必停）：展示【交付包 + 基线对比 + 评分卡 + 新鲜回执 + registry 总览】，用户确认收货",
        "blocking": True,
    })

    current = next((s for s in stages if not s["passed"]), None)
    status = "evolve_triggered" if inbox_triggered else ("ready" if current is None else "in_progress")
    return {
        "skill": (manifest or {}).get("name", root.name),
        "path": str(root),
        "skill_type": skill_type,
        "tier": tier,
        "status": status,
        "inbox_triggered": inbox_triggered,
        "inbox": inbox_counts,
        "current_stage": "E0-E3" if inbox_triggered else (current["id"] if current else "READY"),
        "stages": stages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="盘古开天 阶段状态机导航器")
    parser.add_argument("skill_dir", help="目标 skill 目录")
    parser.add_argument("--tier", choices=["quick", "standard", "flagship"], default="standard",
                        help="档位：quick（仅 2 个阻塞检查点）/ standard / flagship")
    parser.add_argument("--type", choices=["auto", "output", "text"], default="auto", help="skill 分型")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    args = parser.parse_args()

    root = Path(args.skill_dir).resolve()
    if not root.is_dir():
        print(f"❌ 目录不存在: {root}", file=sys.stderr)
        return 2

    res = evaluate_stages(root, tier=args.tier, forced_type=args.type)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["status"] == "ready" else 1

    print(f"🧭 阶段导航: {res['skill']}（type={res['skill_type']}, tier={res['tier']}）")
    print("=" * 64)
    for st in res["stages"]:
        mark = "✅ PASS" if st["passed"] else "👉 当前" if st["id"] == res["current_stage"] else "⏳ 待办"
        print(f"  {mark}  [{st['id']:<8}] {st['title']}")
    print("=" * 64)

    if res["inbox_triggered"]:
        ib = res["inbox"] or {}
        print(f"🔴 检测到强制进化触发器：open blocker/major={ib.get('blocker_major', 0)}, open minor={ib.get('minor_open', 0)}")
        print("下一步必须执行 E0-E3 进化轮（读 references/evolve.md）：")
        print(f"  1. python {root / 'feedback' / 'log.py'} list 查看待修条目并 set <行> --status processing")
        print("  2. 快照当前文件到 evidence/snapshots/，单维修复后跑 3-Judge 异构职责盲评")
        print("  3. 重跑 verify_skill.py --execute 刷回执，log.py set <行> --status resolved --evidence ...")
        print("  4. log.py bump && registry.py <工作区根> --sync")
        return 1

    if res["status"] == "ready":
        print("🎉 所有阶段闸门已通过（READY）。日常使用遇到问题请运行 feedback/log.py add 当场落箱。")
        return 0

    cur = next(s for s in res["stages"] if s["id"] == res["current_stage"])
    print(f"当前阶段: {cur['title']}")
    print("未通过项:")
    for c in cur["checks"]:
        if not c["ok"]:
            print(f"  ❌ {c['name']}: {c['detail']}")
    print("\n本阶段必做动作（只做本阶段，勿跨阶段跳步）:")
    for idx, act in enumerate(cur["actions"], 1):
        print(f"  {idx}. {act}")
    print(f"\n检查点规则: {cur['checkpoint']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
