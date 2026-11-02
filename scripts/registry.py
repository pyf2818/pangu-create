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
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_evolution import normalize_tsv, parse_tsv  # noqa: E402
from pangu_seal import read_seal  # noqa: E402
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
    "receipt", "seal", "lineage_id", "scanned_at",
]


def find_skill_dirs(root: Path, max_depth: int):
    """返回 (registered, orphans)；registered=有 pangu.json 的目录，orphans=只有 SKILL.md 的目录。跳过隐藏/虚拟环境/证据目录。"""
    skip_parts = {".git", ".omc", "__pycache__", "node_modules", "evidence", "artifacts", "_snap", ".venv", "venv", "research", "fixtures"}
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
    """读 feedback/inbox.tsv；返回 (counts, warnings)。
    counts={open, blocker_major, minor_open, processing, total, triggered}。
    """
    path = skill_dir / INBOX_REL
    counts = {"open": 0, "blocker_major": 0, "minor_open": 0, "processing": 0, "total": 0, "triggered": False}
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
            elif sev == "minor":
                counts["minor_open"] += 1
        elif status == "processing":
            counts["processing"] += 1
        if sev and sev not in SEVERITIES:
            warns.append(f"{INBOX_REL.as_posix()} L{line_no} severity={sev!r} 非法（blocker/major/minor）")
    counts["triggered"] = counts["blocker_major"] > 0 or counts["minor_open"] >= 3
    return counts, warns


def seal_status(skill_dir: Path, manifest: dict | None):
    """检查 SKILL.md 末尾是否有盘古印记区块 + feedback/log.py 工具是否就位。
    返回 (status, warnings)，status ∈ ok / missing / mismatch / no-tool。
    """
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return "missing", ["缺 SKILL.md"]
    try:
        info = read_seal(md.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        return "missing", [f"SKILL.md 读取失败: {exc}"]
    if info is None:
        return "missing", ["SKILL.md 缺盘古印记区块（运行时无落箱指令；用 scaffold.py <目录> --reseal 补盖）"]
    expected = str((manifest or {}).get("lineage_id", "")).strip()
    if expected and info.get("lineage") and info.get("lineage") != expected:
        return "mismatch", [
            f"SKILL.md 印记 lineage={info.get('lineage')!r} 与 pangu.json {expected!r} 不一致（跑 --reseal 同步）"
        ]
    if not (skill_dir / "feedback" / "log.py").is_file():
        return "no-tool", ["缺 feedback/log.py 落箱脚本（跑 scaffold.py <目录> --reseal 补齐）"]
    return "ok", []


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


def _count_keeps(skill_dir: Path) -> int:
    tsv = skill_dir / "results.tsv"
    if not tsv.exists():
        return 0
    records, error, _ = parse_tsv(tsv)
    if error:
        return 0
    return sum(1 for r in records if str(r.get("status", "")).strip().lower() == "keep")


def scan_skill(skill_dir: Path, scan_root: Path):
    manifest, errors = load_manifest(skill_dir)
    worse, last_status, last_ts, ledger_warns = ledger_summary(skill_dir)
    keeps = _count_keeps(skill_dir)
    inbox, inbox_warns = read_inbox(skill_dir)
    seal, seal_warns = seal_status(skill_dir, manifest)
    generation = (manifest or {}).get("generation", 0)
    gen_drift = generation == 0 and keeps > 0
    drift_warns = (
        [f"generation=0 但 results.tsv 已有 {keeps} 次 keep（跑 feedback/log.py bump 同步代次）"]
        if gen_drift else []
    )
    all_warns = errors + ledger_warns + (inbox_warns or []) + seal_warns + drift_warns
    inbox_dict = inbox if isinstance(inbox, dict) else {}
    entry = {
        "name": (manifest or {}).get("name", skill_dir.name),
        "path": _display_path(skill_dir, scan_root),
        "domain": (manifest or {}).get("domain", "-"),
        "skill_type": (manifest or {}).get("skill_type", "-"),
        "forge_date": (manifest or {}).get("forge_date", "-"),
        "generation": generation,
        "depth": (manifest or {}).get("depth", "-"),
        "worse": worse,
        "open_fb": inbox_dict.get("open", 0),
        "blocker_major": inbox_dict.get("blocker_major", 0),
        "minor_open": inbox_dict.get("minor_open", 0),
        "evolution_triggered": bool(inbox_dict.get("triggered", False)),
        "last_status": last_status,
        "last_timestamp": last_ts,
        "receipt": receipt_status(skill_dir),
        "seal": seal,
        "gen_drift": gen_drift,
        "lineage_id": (manifest or {}).get("lineage_id", "-"),
        "scanned_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "warnings": all_warns,
        "has_inbox": inbox is not None,
        "registered": manifest is not None and not errors,
    }
    return entry


def build_evolution_queue(entries):
    """按优先级生成可执行进化队列：P0 blocker/major > P1 minor≥3 > P2 连续 worse > P3 印记/代次漂移。"""
    queue = []
    for e in entries:
        reasons, priority, action = [], None, None
        if e["blocker_major"] > 0:
            priority = "P0"
            reasons.append(f"{e['blocker_major']} 条 open blocker/major 反馈（契约 #8 强制进化）")
            action = f"读 {e['path']}/feedback/inbox.tsv → 走 E0-E3 修复 → log.py set <行> --status resolved"
        if e.get("minor_open", 0) >= 3:
            priority = priority or "P1"
            reasons.append(f"{e['minor_open']} 条 open minor 反馈已达 ≥3 阈值（契约 #8）")
            action = action or f"合并处理 {e['path']}/feedback/inbox.tsv 的 minor 项 → 走 E0-E3"
        if e["worse"] >= 2 and str(e["last_status"]).lower() == "worse":
            priority = priority or "P2"
            reasons.append(f"累计 {e['worse']} 次 worse 且末态为 worse（契约 #3：升级 E2.5 探索性重写）")
            action = action or f"对 {e['path']} 启动 E2.5 探索性重写或回炉 F2"
        if e.get("seal") != "ok":
            priority = priority or "P3"
            reasons.append(f"盘古印记={e.get('seal')}")
            action = action or f"python scripts/scaffold.py {e['path']} --reseal"
        if e.get("gen_drift"):
            priority = priority or "P3"
            reasons.append("generation=0 但账本已有 keep")
            action = action or f"python {e['path']}/feedback/log.py bump"
        if priority:
            queue.append({
                "priority": priority,
                "name": e["name"],
                "path": e["path"],
                "reasons": reasons,
                "action": action,
            })
    queue.sort(key=lambda item: (item["priority"], item["name"]))
    return queue


def _read_inbox_rows(skill_dir: Path):
    """读取 inbox.tsv 的数据行列表，每项为 (key_tuple, raw_cells)。"""
    path = skill_dir / INBOX_REL
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return []
    rows = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if len(rows) <= 1:
        return []
    delim = "\t" if rows[0].count("\t") >= rows[0].count(",") else ","
    header = [c.strip().lower() for c in rows[0].split(delim)]
    out = []
    for ln in rows[1:]:
        cells = [c.strip() for c in ln.split(delim)]
        row_map = dict(zip(header, cells))
        key = (row_map.get("timestamp", ""), row_map.get("scene", ""), row_map.get("symptom", ""))
        norm_cells = [row_map.get(col, "-") or "-" for col in INBOX_HEADER]
        out.append((key, norm_cells))
    return out


def collect_replica_feedback(primary_dir: Path, replica_dirs: list[Path]) -> int:
    """把副本目录（如 ~/.claude/skills/<name>）中新增的反馈行去重合并回主工作区源目录。"""
    primary_rows = _read_inbox_rows(primary_dir)
    seen_keys = {k for k, _ in primary_rows}
    added = []
    for rep in replica_dirs:
        for key, cells in _read_inbox_rows(rep):
            if key not in seen_keys:
                seen_keys.add(key)
                added.append(cells)
    if not added:
        return 0
    inbox_path = primary_dir / INBOX_REL
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    all_cells = [cells for _, cells in primary_rows] + added
    lines = ["\t".join(INBOX_HEADER)] + ["\t".join(c) for c in all_cells]
    inbox_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(added)


def deploy_to_replicas(primary_dir: Path, replica_dirs: list[Path]) -> list[str]:
    """把主源目录的最新文件同步到已安装副本目录（先收集副本反馈，跳过 .git/.omc/snapshots）。"""
    collect_replica_feedback(primary_dir, replica_dirs)
    skip_parts = {".git", ".omc", "__pycache__", "node_modules", "snapshots"}
    synced = []
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-deploy")
    for rep in replica_dirs:
        if (rep / "SKILL.md").is_file():
            snap = rep / "evidence" / "snapshots" / ts
            snap.mkdir(parents=True, exist_ok=True)
            shutil.copy2(rep / "SKILL.md", snap / "SKILL.md")
        for src in primary_dir.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(primary_dir)
            if set(rel.parts) & skip_parts:
                continue
            dst = rep / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        synced.append(str(rep))
    return synced


def _display_path(p: Path, root: Path):
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return str(p)


def render_table(entries, orphans):
    lines = []
    header = f"{'skill':<22} {'域':<14} {'型':<6} {'代':<3} {'深':<3} {'worse':>5} {'反馈':>4} {'末态':<10} {'回执':<7} {'印记':<8} 路径"
    lines.append(header)
    lines.append("-" * len(header))
    for e in entries:
        flag = "🔴" if e.get("evolution_triggered") else ("🟡" if e["open_fb"] else "")
        lines.append(
            f"{e['name'][:21]:<22} {str(e['domain'])[:13]:<14} {str(e['skill_type'])[:5]:<6} "
            f"{e['generation']:<3} {str(e['depth'])[:2]:<3} {e['worse']:>5} "
            f"{e['open_fb']:>4}{flag:<2} {str(e['last_status'])[:9]:<10} {e['receipt']:<7} {e.get('seal', '-'):<8} {e['path']}"
        )
    for o in orphans:
        lines.append(f"{'(未登记)':<22} {'-':<14} {'-':<6} {'-':<3} {'-':<3} {'-':>5} {'-':>4}  {'-':<10} {'-':<7} {'-':<8} {o}")
    return lines


def main():
    parser = argparse.ArgumentParser(description="盘古开天 技能群注册表")
    parser.add_argument("roots", nargs="+", help="一个或多个扫描根目录（工作区根 / ~/.claude/skills 等）")
    parser.add_argument("--json", action="store_true", help="JSON 输出（供 agent/脚本消费）")
    parser.add_argument("--sync", action="store_true", help="把总览落盘为 registry.tsv")
    parser.add_argument("--registry", default=None, help="registry.tsv 输出路径（默认 <盘古目录>/registry.tsv）")
    parser.add_argument("--strict", action="store_true", help="存在触发进化的 open 反馈、印记不一致或孤儿 → exit 1")
    parser.add_argument("--require-seal", action="store_true", help="配合 --strict：任何已登记 skill 缺盘古印记也 exit 1")
    parser.add_argument("--normalize-ledgers", action="store_true", help="规范化所有已登记 skill 的 results.tsv 为标准 10 列（改前快照）")
    parser.add_argument("--collect-feedback", action="store_true", help="多根扫描时把已安装副本的 inbox.tsv 新增反馈合并回首个根的源目录")
    parser.add_argument("--deploy", action="store_true", help="多根扫描时先收集副本反馈，再将主源目录同步到已安装副本目录")
    parser.add_argument("--depth", type=int, default=3, help="扫描深度（默认 3）")
    args = parser.parse_args()

    roots = []
    for r in args.roots:
        p = Path(r)
        if not p.is_dir():
            print(f"扫描根不存在: {p}")
            return 2
        roots.append(p.resolve())
    primary_root = roots[0]

    seen_dirs = set()
    reg_records, orphan_paths = [], []
    for r in roots:
        reg_dirs, orp_dirs = find_skill_dirs(r, max_depth=max(1, args.depth))
        for d in reg_dirs:
            resolved = d.resolve()
            if resolved not in seen_dirs:
                seen_dirs.add(resolved)
                reg_records.append((resolved, primary_root if len(roots) == 1 else r))
        for o in orp_dirs:
            resolved = o.resolve()
            if resolved not in seen_dirs:
                seen_dirs.add(resolved)
                orphan_paths.append(_display_path(o, primary_root if len(roots) == 1 else r))

    normalized_ledgers = []
    if args.normalize_ledgers:
        for d, _ in reg_records:
            tsv = d / "results.tsv"
            if tsv.is_file():
                norm = normalize_tsv(tsv)
                if norm.get("changed"):
                    normalized_ledgers.append({"skill": d.name, "fixes": len(norm.get("fixes", []))})

    # 先按 lineage_id 分组以支持跨目录反馈收集与部署
    dirs_by_lineage = {}
    for d, _ in reg_records:
        m, _ = load_manifest(d)
        lid = (m or {}).get("lineage_id", "-")
        if lid and lid != "-":
            dirs_by_lineage.setdefault(lid, []).append(d)

    collected_feedback, deployed_replicas = {}, []
    if args.collect_feedback or args.deploy:
        for lid, dlist in dirs_by_lineage.items():
            if len(dlist) > 1:
                count = collect_replica_feedback(dlist[0], dlist[1:])
                if count:
                    collected_feedback[dlist[0].name] = count
                if args.deploy:
                    deployed_replicas.extend(deploy_to_replicas(dlist[0], dlist[1:]))

    entries = [scan_skill(d, disp_root) for d, disp_root in reg_records]

    by_lineage, duplicates, dup_warns = {}, [], []
    for e in entries:
        lid = e.get("lineage_id", "-")
        if lid and lid != "-":
            by_lineage.setdefault(lid, []).append(e["path"])
    for lid, paths in by_lineage.items():
        if len(paths) > 1:
            duplicates.append({"lineage_id": lid, "paths": paths})
            if not (args.collect_feedback or args.deploy):
                dup_warns.append(f"[重复副本] lineage={lid} 同时存在于 {', '.join(paths)}（加 --collect-feedback 自动合并收件箱）")

    total_open = sum(e["open_fb"] for e in entries)
    total_blocker = sum(e["blocker_major"] for e in entries)
    minor_triggered = sum(1 for e in entries if e.get("minor_open", 0) >= 3)
    seal_ok = sum(1 for e in entries if e.get("seal") == "ok")
    seal_mismatch = sum(1 for e in entries if e.get("seal") == "mismatch")
    stale = sum(1 for e in entries if e["receipt"] == "stale")
    missing_receipt = sum(1 for e in entries if e["receipt"] == "missing")
    queue = build_evolution_queue(entries)
    prefixed_warnings = [f"[{e['name']}] {w}" for e in entries for w in e["warnings"]] + dup_warns

    result = {
        "scan_root": str(primary_root),
        "scan_roots": [str(r) for r in roots],
        "skills": entries,
        "orphans": orphan_paths,
        "duplicates": duplicates,
        "normalized_ledgers": normalized_ledgers,
        "collected_feedback": collected_feedback,
        "deployed_replicas": deployed_replicas,
        "evolution_queue": queue,
        "summary": {
            "registered": len(entries),
            "orphans": len(orphan_paths),
            "open_feedback": total_open,
            "blocker_major_open": total_blocker,
            "minor_batch_triggered": minor_triggered,
            "seal_ok": seal_ok,
            "seal_missing_or_bad": len(entries) - seal_ok,
            "receipt_fresh": len(entries) - stale - missing_receipt,
            "receipt_stale": stale,
            "receipt_missing": missing_receipt,
            "queue_size": len(queue),
        },
        "warnings": prefixed_warnings,
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
        roots_label = ", ".join(str(r) for r in roots)
        print(f"技能群总览（根: {roots_label}）  已登记 {len(entries)} | 印记 {seal_ok}/{len(entries)} | "
              f"孤儿 {len(orphan_paths)} | open 反馈 {total_open}（blocker/major {total_blocker}）")
        print()
        print("\n".join(render_table(entries, orphan_paths)))
        if queue:
            print()
            print("🧭 进化队列（按优先级）:")
            for item in queue:
                print(f"  [{item['priority']}] {item['name']} ({item['path']}): {'; '.join(item['reasons'])}")
                print(f"       └─ 动作: {item['action']}")
        if result["warnings"]:
            print()
            print("⚠️ 数据质量警告:")
            for w in result["warnings"]:
                print(f"  - {w}")
        if orphan_paths:
            print()
            print("孤儿 skill（有 SKILL.md 无 pangu.json）→ 补登记: python3 scripts/scaffold.py <目录> --name <名> --adopt --seal")
        if total_blocker or minor_triggered:
            print()
            print(f"🔴 强制进化触发（blocker/major={total_blocker}, minor≥3 技能数={minor_triggered}，evolve.md 进化契约 #8）")

    exit_code = 0
    if args.strict and (total_blocker or minor_triggered or orphan_paths or seal_mismatch):
        exit_code = 1
    if args.strict and args.require_seal and seal_ok < len(entries):
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
