#!/usr/bin/env python3
"""
盘古开天 一键跨平台安装与技能群分发器（install.py）：零第三方依赖，支持 Windows / macOS / Linux。

功能:
  1. 将 pangu-create 本身（或通过 --skill / --fleet 指定的盘古子技能群）安装到主流 Agent 运行时的 skills 目录：
     - Claude Code: ~/.claude/skills/
     - 通用 Agent:  ~/.agents/skills/
     - Cursor:      ~/.cursor/skills/
     - TRAE:        ~/.trae-cn/skills/
     - Codex:       ~/.codex/skills/
  2. 幂等且安全：若目标目录已有同名 skill，先自动将其 feedback/inbox.tsv 中未同步的新反馈合并回源目录，
     并在目标端生成 evidence/snapshots/<ts>-install/ 快照后再更新文件，绝不丢失使用期反馈。
  3. --check：安装后自动对副本执行静态质量核验与盘古印记校验（seal=ok）。

用法:
  python scripts/install.py                                  # 自动探测已装运行时（默认装入 ~/.claude/skills 与 ~/.agents/skills）
  python scripts/install.py --target claude                  # 只装入 ~/.claude/skills
  python scripts/install.py --target all                     # 装入全部 5 类运行时目录
  python scripts/install.py --dest ./my-skills --check       # 装入自定义目录并执行安装后自检（CI 常用）
  python scripts/install.py --fleet .. --target claude       # 将整个工作区已登记的盘古技能群批量安装到运行目录
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
PANGU_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import subprocess
import registry as REG  # noqa: E402

RUNTIME_TARGETS = {
    "claude": Path(".claude") / "skills",
    "agents": Path(".agents") / "skills",
    "cursor": Path(".cursor") / "skills",
    "trae": Path(".trae-cn") / "skills",
    "codex": Path(".codex") / "skills",
}

SKIP_PARTS = {".git", ".omc", "__pycache__", "node_modules", "snapshots", "_ci_installed_skills"}


def resolve_target_roots(target: str, dest: str | None, home: Path | None = None) -> list[Path]:
    if dest:
        return [Path(dest).resolve()]
    home_dir = home or Path.home()
    if target == "all":
        return [(home_dir / rel).resolve() for rel in RUNTIME_TARGETS.values()]
    if target != "auto":
        return [(home_dir / RUNTIME_TARGETS[target]).resolve()]
    # auto: 若用户机器上已有某个运行时根目录（如 ~/.claude 或 ~/.agents），优先装入；否则默认装 claude + agents
    detected = []
    for name, rel in RUNTIME_TARGETS.items():
        runtime_parent = home_dir / rel.parts[0]
        if runtime_parent.exists():
            detected.append((home_dir / rel).resolve())
    if not detected:
        detected = [
            (home_dir / RUNTIME_TARGETS["claude"]).resolve(),
            (home_dir / RUNTIME_TARGETS["agents"]).resolve(),
        ]
    return detected


def install_one_skill(src_dir: Path, dst_root: Path) -> dict:
    src_dir = src_dir.resolve()
    manifest, _ = REG.load_manifest(src_dir)
    skill_name = (manifest or {}).get("name") or src_dir.name
    dst_dir = (dst_root / skill_name).resolve()

    if dst_dir == src_dir:
        return {"skill": skill_name, "dest": str(dst_dir), "copied_files": 0, "skipped_same": True}

    # 若目标已存在，先回收目标收件箱里的新反馈，并对目标 SKILL.md 留快照
    collected = 0
    if dst_dir.is_dir():
        collected = REG.collect_replica_feedback(src_dir, [dst_dir])
        if (dst_dir / "SKILL.md").is_file():
            ts = datetime.now().strftime("%Y%m%d-%H%M%S-install")
            snap = dst_dir / "evidence" / "snapshots" / ts
            snap.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst_dir / "SKILL.md", snap / "SKILL.md")

    copied = 0
    for item in src_dir.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(src_dir)
        if set(rel.parts) & SKIP_PARTS:
            continue
        out_file = dst_dir / rel
        out_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, out_file)
        copied += 1

    # 若刚才从旧副本回收了新反馈，把合并后的最新收件箱也写回副本
    if collected and (src_dir / REG.INBOX_REL).is_file():
        dst_inbox = dst_dir / REG.INBOX_REL
        dst_inbox.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_dir / REG.INBOX_REL, dst_inbox)

    dst_manifest, _ = REG.load_manifest(dst_dir)
    seal_st, _ = REG.seal_status(dst_dir, dst_manifest)
    return {
        "skill": skill_name,
        "source": str(src_dir),
        "dest": str(dst_dir),
        "copied_files": copied,
        "collected_feedback": collected,
        "seal": seal_st,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="盘古开天 一键跨平台安装与技能群分发器")
    parser.add_argument("--skill", default=str(PANGU_ROOT), help="要安装的 skill 目录（默认 pangu-create 自身）")
    parser.add_argument("--fleet", default=None, help="批量安装：指定工作区根目录，安装其中全部已登记的盘古技能")
    parser.add_argument("--target", choices=["auto", "claude", "agents", "cursor", "trae", "codex", "all"],
                        default="auto", help="目标运行时类型（默认 auto 自动探测）")
    parser.add_argument("--dest", default=None, help="自定义安装目标父目录（覆盖 --target）")
    parser.add_argument("--check", action="store_true", help="安装后对每个副本运行静态 11 项与盘古印记自检")
    parser.add_argument("--json", action="store_true", help="输出纯 JSON")
    args = parser.parse_args()

    if args.fleet:
        fleet_root = Path(args.fleet).resolve()
        if not fleet_root.is_dir():
            print(f"❌ 工作区目录不存在: {fleet_root}", file=sys.stderr)
            return 2
        skill_dirs, _ = REG.find_skill_dirs(fleet_root, max_depth=3)
    else:
        sdir = Path(args.skill).resolve()
        if not (sdir / "SKILL.md").is_file():
            print(f"❌ 无效的 skill 目录（缺 SKILL.md）: {sdir}", file=sys.stderr)
            return 2
        skill_dirs = [sdir]

    target_roots = resolve_target_roots(args.target, args.dest)
    installed = []
    check_failures = []

    for root in target_roots:
        for sdir in skill_dirs:
            rec = install_one_skill(sdir, root)
            if args.check:
                dest_skill_md = Path(rec["dest"]) / "SKILL.md"
                proc = subprocess.run(
                    [sys.executable, str(SCRIPT_DIR / "quality_check.py"), str(dest_skill_md)],
                    capture_output=True, text=True, encoding="utf-8"
                )
                rec["quality_check"] = "11/11" if proc.returncode == 0 else "FAIL"
                if proc.returncode != 0 or rec.get("seal") != "ok":
                    check_failures.append(rec["dest"])
            installed.append(rec)

    payload = {
        "ok": len(check_failures) == 0,
        "target_roots": [str(r) for r in target_roots],
        "installed": installed,
        "check_failures": check_failures,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1

    print(f"🚀 盘古开天安装完成（目标数: {len(target_roots)}，技能数: {len(skill_dirs)}）")
    for item in installed:
        qc_str = f" | 自检 {item['quality_check']}" if "quality_check" in item else ""
        fb_str = f" | 回收旧反馈 {item['collected_feedback']} 条" if item.get("collected_feedback") else ""
        print(f"  ✅ {item['skill']:<18} → {item['dest']} ({item['copied_files']} 文件 | seal={item.get('seal')}{qc_str}{fb_str})")

    first_root = target_roots[0]
    src_base = Path(args.fleet).resolve() if args.fleet else skill_dirs[0].parent
    print("\n🔄 后续跨目录联动命令：")
    print(f"  - 回收安装副本的使用反馈: python {PANGU_ROOT / 'scripts' / 'registry.py'} {src_base} {first_root} --collect-feedback")
    print(f"  - 进化升级后推回安装副本: python {PANGU_ROOT / 'scripts' / 'registry.py'} {src_base} {first_root} --deploy")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
