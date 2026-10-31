#!/usr/bin/env python3
"""
盘古开天 技能群注册表：扫描工作区内所有由盘古锻造的 skill，输出关联管理总览。

背景:
  盘古锻造的每个 skill 目录内都有 pangu.json（lineage 血统清单）与
  feedback/inbox.tsv（反馈收件箱）。本脚本把它们聚合成一张技能群总览，
  让「盘古的技能群」成为可盘点的资产，而不是散落的目录。

用法:
    python3 registry.py <扫描根目录> [--json] [--sync] [--registry <路径>] [--strict] [--depth N]

行为:
    1. 递归扫描（默认深度 3）找含 SKILL.md 的目录：
       - 有 pangu.json        → 已登记（读血统/代次/深度/账本/收件箱/回执新鲜度）
       - 无 pangu.json        → 孤儿（提示用 scaffold.py --adopt 补登记）
    2. 默认只读打印总览；--sync 把总览落盘为 registry.tsv（默认写在盘古目录根）
    3. --strict 时，存在 open 的 blocker/major 反馈或孤儿 → exit 1（CI/巡检用）

退出码:
    0 正常（含「发现孤儿/反馈」的信息性提示）  1 --strict 且有问题  2 扫描根不存在

只读边界: 除 --sync 写 registry.tsv 一个文件外，本脚本零写入、零联网、零依赖安装。
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_evolution import parse_tsv  # noqa: E402
from verify_skill import contract_digest, source_fingerprint  # noqa: E402

MANIFEST_NAME = "pangu.json"
INBOX_REL = Path("feedback") / "inbox.tsv"
INBOX_HEADER = ["timestamp", "severity", "scene", "symptom", "evidence", "status"]
SEVERITIES = {"blocker", "major", "minor"}
INBOX_STATUS = {"open", "processing", "resolved"}
VALID_DEPTHS = {"L1", "L2", "L3"}
REGISTRY_COLUMNS = [
    "name", "path", "domain", "skill_type", "forge_date", "generation", "depth",
    "worse", "open_fb", "blocker_major", "last_status", "last_timestamp",
    "receipt", "lineage_id", "scanned_at",
]


def find_skill_dirs(root: Path, max_depth: int):
    """返回 (registered, orphans)；registered=有 pangu.json 的目录，orphans=只有 SKILL.md 的目录。跳过隐藏/虚拟环境/证据目录。"""
    skip_parts = {".git", ".omc", "__pycache__", "node_modules", "evidence", "artifacts", "_snap", ".venv", "venv"}
    registered, orphans = [], []
    root = root.resolve()

    def walk(dir_path: Path, depth: int):
        if (dir_path / "SKILL.md").is_file():
            if (dir_path / MANIFEST_NAME).is_file():
                registered.append(dir_path)
            else:
                orphans.append(dir_path)
            return  # skill 目录不继续下钻，避免把子目录误当 skill
        if depth >= max_depth:
            return
        try:
            children = sorted(p for p in dir_path.iterdir() if p.is_dir())
        except OSError:
            return
        for child in children:
            if child.name.startswith(".") or set(child.parts) & skip_parts:
                continue
            walk(child, depth + 1)

    walk(root, 0)
    return registered, orphans


def load_manifest(skill_dir: Path):
    """读 pangu.json；返回 (manifest, errors)。缺字段/非法值记入 errors，不静默。"""
    errors = []
    try:
        data = json.loads((skill_dir / MANIFEST_NAME).read_text(encoding="utf-8-sig"))
    except OSError as exc:
        return None, [f"读取失败: {exc}"]
    except ValueError as exc:
        return None, [f"JSON 不可解析: {exc}"]
    if not isinstance(data, dict):
        return None, ["顶层不是对象"]
    if data.get("schema") != 1:
        errors.append(f"schema={data.get('schema')!r}（本工具只认 1）")
    if data.get("forged_by") != "pangu-create":
        errors.append(f"forged_by={data.get('forged_by')!r}（非盘古锻造？不应有本清单）")
    for key in ("lineage_id", "name", "skill_type", "forge_date"):
        if not str(data.get(key, "")).strip():
            errors.append(f"缺 {key}")
    if data.get("depth") not in VALID_DEPTHS:
        errors.append(f"depth={data.get('depth')!r}（应为 L1/L2/L3）")
    try:
        data["generation"] = int(data.get("generation", 0))
    except (TypeError, ValueError):
        errors.append(f"generation={data.get('generation')!r} 非整数")
        data["generation"] = 0
    return data, errors


def read_inbox(skill_dir: Path):
    """读 feedback/inbox.tsv；返回 (counts, warnings)。counts={open, blocker_major, total}。"""
    path = skill_dir / INBOX_REL
    counts = {"open": 0, "blocker_major": 0, "total": 0}
    if not path.exists():
        return None, [f"缺 {INBOX_REL.as_posix()}（反馈无落点=问题会丢）"]
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return counts, [f"读取失败: {exc}"]
    rows = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not rows:
        return counts, [f"{INBOX_REL.as_posix()} 无表头"]
    delim = "\t" if rows[0].count("\t") >= rows[0].count(",") else ","
    header = [c.strip().lower() for c in rows[0].split(delim)]
    if header[:2] != INBOX_HEADER[:2] or "status" not in header:
        return counts, [f"{INBOX_REL.as_posix()} 表头不合规（需 {','.join(INBOX_HEADER)}）"]
    sev_i, status_i = header.index("severity"), header.index("status")
    warns = []
    for line_no, line in enumerate(rows[1:], 2):
        cells = [c.strip() for c in line.split(delim)]
        counts["total"] += 1
        sev = cells[sev_i].lower() if sev_i < len(cells) else ""
        status = cells[status_i].lower() if status_i < len(cells) else ""
        if status == "open":
            counts["open"] += 1
            if sev in ("blocker", "major"):
                counts["blocker_major"] += 1
        if sev and sev not in SEVERITIES:
            warns.append(f"{INBOX_REL.as_posix()} L{line_no} severity={sev!r} 非法（blocker/major/minor）")
    return counts, warns


def receipt_status(skill_dir: Path):
    """回执新鲜度：比对 evidence/verification.json 存的源码/清单哈希与当前值。fresh/stale/missing。"""
    evidence = skill_dir / "evidence" / "verification.json"
    if not evidence.exists():
        return "missing"
    try:
        data = json.loads(evidence.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return "missing"
    fp, _ = source_fingerprint(skill_dir)
    cd = contract_digest(skill_dir)
    if data.get("source_sha256") == fp and data.get("contract_sha256") == cd:
        return "fresh"
    return "stale"


def ledger_summary(skill_dir: Path):
    """读 results.tsv：返回 (worse 数, 最后一条 status, 最后时间戳, 警告)。"""
    tsv = skill_dir / "results.tsv"
    if not tsv.exists():
        return 0, "-", "-", ["缺 results.tsv（进化账本未建）"]
    records, error, warnings = parse_tsv(tsv)
    if error:
        return 0, "-", "-", [f"results.tsv 解析失败: {error}"]
    worse = sum(1 for r in records if str(r.get("status", "")).strip().lower() == "worse")
    last = records[-1] if records else {}
    return (worse,
            str(last.get("status", "-")).strip() or "-",
            str(last.get("timestamp", "-")).strip() or "-",
            warnings)


def scan_skill(skill_dir: Path, scan_root: Path):
    manifest, errors = load_manifest(skill_dir)
    worse, last_status, last_ts, ledger_warns = ledger_summary(skill_dir)
    inbox, inbox_warns = read_inbox(skill_dir)
    all_warns = errors + ledger_warns + (inbox_warns or [])
    entry = {
        "name": (manifest or {}).get("name", skill_dir.name),
        "path": _display_path(skill_dir, scan_root),
        "domain": (manifest or {}).get("domain", "-"),
        "skill_type": (manifest or {}).get("skill_type", "-"),
        "forge_date": (manifest or {}).get("forge_date", "-"),
        "generation": (manifest or {}).get("generation", 0),
        "depth": (manifest or {}).get("depth", "-"),
        "worse": worse,
        "open_fb": (inbox or {}).get("open", 0) if isinstance(inbox, dict) else 0,
        "blocker_major": (inbox or {}).get("blocker_major", 0) if isinstance(inbox, dict) else 0,
        "last_status": last_status,
        "last_timestamp": last_ts,
        "receipt": receipt_status(skill_dir),
        "lineage_id": (manifest or {}).get("lineage_id", "-"),
        "scanned_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "warnings": all_warns,
        "has_inbox": inbox is not None,
        "registered": manifest is not None and not errors,
    }
    return entry


def _display_path(p: Path, root: Path):
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return str(p)


def render_table(entries, orphans):
    lines = []
    header = f"{'skill':<22} {'域':<14} {'型':<6} {'代':<3} {'深':<3} {'worse':>5} {'反馈':>4} {'末态':<10} {'回执':<7} 路径"
    lines.append(header)
    lines.append("-" * len(header))
    for e in entries:
        flag = "🔴" if e["blocker_major"] else ("🟡" if e["open_fb"] else "")
        lines.append(
            f"{e['name'][:21]:<22} {str(e['domain'])[:13]:<14} {str(e['skill_type'])[:5]:<6} "
            f"{e['generation']:<3} {str(e['depth'])[:2]:<3} {e['worse']:>5} "
            f"{e['open_fb']:>4}{flag:<2} {str(e['last_status'])[:9]:<10} {e['receipt']:<7} {e['path']}"
        )
    for o in orphans:
        lines.append(f"{'(未登记)':<22} {'-':<14} {'-':<6} {'-':<3} {'-':<3} {'-':>5} {'-':>4}  {'-':<10} {'-':<7} {o}")
    return lines


def main():
    parser = argparse.ArgumentParser(description="盘古开天 技能群注册表")
    parser.add_argument("root", help="扫描根目录（工作区根或 skills 父目录）")
    parser.add_argument("--json", action="store_true", help="JSON 输出（供 agent/脚本消费）")
    parser.add_argument("--sync", action="store_true", help="把总览落盘为 registry.tsv")
    parser.add_argument("--registry", default=None, help="registry.tsv 输出路径（默认 <盘古目录>/registry.tsv）")
    parser.add_argument("--strict", action="store_true", help="存在 open blocker/major 或孤儿 → exit 1")
    parser.add_argument("--depth", type=int, default=3, help="扫描深度（默认 3）")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"扫描根不存在: {root}")
        return 2
    root = root.resolve()

    registered_dirs, orphan_dirs = find_skill_dirs(root, max_depth=max(1, args.depth))
    entries = [scan_skill(d, root) for d in registered_dirs]
    orphan_paths = [_display_path(o, root) for o in orphan_dirs]

    total_open = sum(e["open_fb"] for e in entries)
    total_blocker = sum(e["blocker_major"] for e in entries)
    stale = sum(1 for e in entries if e["receipt"] == "stale")
    missing_receipt = sum(1 for e in entries if e["receipt"] == "missing")
    result = {
        "scan_root": str(root),
        "skills": entries,
        "orphans": orphan_paths,
        "summary": {
            "registered": len(entries),
            "orphans": len(orphan_paths),
            "open_feedback": total_open,
            "blocker_major_open": total_blocker,
            "receipt_fresh": len(entries) - stale - missing_receipt,
            "receipt_stale": stale,
            "receipt_missing": missing_receipt,
        },
        "warnings": [w for e in entries for w in e["warnings"]],
    }

    if args.sync:
        out = Path(args.registry) if args.registry else Path(__file__).resolve().parent.parent / "registry.tsv"
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = ["\t".join(REGISTRY_COLUMNS)]
        for e in entries:
            lines.append("\t".join(str(e.get(c, "-")) for c in REGISTRY_COLUMNS))
        for o in orphan_paths:
            row = {c: "-" for c in REGISTRY_COLUMNS}
            row.update({"name": "(未登记)", "path": o, "scanned_at": datetime.now().strftime("%Y-%m-%dT%H:%M")})
            lines.append("\t".join(row[c] for c in REGISTRY_COLUMNS))
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result["registry_path"] = str(out)
        if not args.json:
            print(f"registry 已同步: {out}")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"技能群总览（根: {root}）  已登记 {len(entries)} | 孤儿 {len(orphan_paths)} | open 反馈 {total_open}（blocker/major {total_blocker}）")
        print()
        print("\n".join(render_table(entries, orphan_paths)))
        if result["warnings"]:
            print()
            print("⚠️ 数据质量警告:")
            for w in result["warnings"]:
                print(f"  - {w}")
        if orphan_paths:
            print()
            print("孤儿 skill（有 SKILL.md 无 pangu.json）→ 补登记: python3 scripts/scaffold.py <目录> --name <名> --adopt")
        if total_blocker:
            print()
            print(f"🔴 {total_blocker} 条 open 的 blocker/major 反馈 = 强制进化触发器（evolve.md 进化契约 #8）")

    exit_code = 0
    if args.strict and (total_blocker or orphan_paths):
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
