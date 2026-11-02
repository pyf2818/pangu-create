#!/usr/bin/env python3
"""盘古技能群 · 反馈收件箱工具（由 pangu-create 随 skill 分发，零依赖，可离线）。

用法（当前目录任意，路径按本文件位置定位）:
  python feedback/log.py add --severity major --scene "在做什么" --symptom "出了什么问题" [--evidence "..."]
  python feedback/log.py list [--all]
  python feedback/log.py set <行号> --status processing|resolved|open [--evidence "..."]
  python feedback/log.py bump [--depth L2|L3]

退出码: 0 成功 / 1 参数或数据不合规 / 2 文件读写失败
"""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
INBOX = HERE / "inbox.tsv"
MANIFEST = HERE.parent / "pangu.json"
HEADER = ["timestamp", "severity", "scene", "symptom", "evidence", "status"]
SEVERITIES = ("blocker", "major", "minor")
STATUSES = ("open", "processing", "resolved")
DEPTHS = ("L1", "L2", "L3")


def clean(value):
    """单元格净化：制表符/换行会把 TSV 写坏，统一压成空格。"""
    text = " ".join(str(value or "").replace("\t", " ").split())
    return text or "-"


def load():
    """返回 (raw_lines, header, data_index)；data_index[i] = 第 i+1 条数据在 raw_lines 中的位置。"""
    if not INBOX.exists():
        return ["\t".join(HEADER)], HEADER[:], []
    raw = INBOX.read_text(encoding="utf-8-sig").splitlines()
    header, data_index = None, []
    for pos, line in enumerate(raw):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if header is None:
            header = [c.strip().lower() for c in line.split("\t")]
            continue
        data_index.append(pos)
    if header is None:
        raw, header = ["\t".join(HEADER)] + raw, HEADER[:]
    if "severity" not in header or "status" not in header:
        print(f"❌ {INBOX} 表头不合规，需包含: {' / '.join(HEADER)}")
        sys.exit(1)
    return raw, header, data_index


def save(raw):
    try:
        INBOX.write_text("\n".join(raw) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"❌ 写入失败: {exc}")
        sys.exit(2)


def cells_of(raw, header, pos):
    cells = raw[pos].split("\t")
    return cells + ["-"] * (len(header) - len(cells))


def summary(raw, header, data_index):
    sev_i, st_i = header.index("severity"), header.index("status")
    bm = minor = 0
    for pos in data_index:
        cells = cells_of(raw, header, pos)
        if cells[st_i].strip().lower() != "open":
            continue
        sev = cells[sev_i].strip().lower()
        bm += sev in ("blocker", "major")
        minor += sev == "minor"
    triggered = bm > 0 or minor >= 3
    return bm, minor, triggered


def print_trigger(raw, header, data_index):
    bm, minor, triggered = summary(raw, header, data_index)
    state = "🔴 已触发强制进化（调用 pangu-create 进化本 skill）" if triggered else "未触发"
    print(f"open blocker/major={bm} | open minor={minor}（≥3 触发）| {state}")


def cmd_add(args):
    raw, header, data_index = load()
    values = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "severity": args.severity,
        "scene": clean(args.scene),
        "symptom": clean(args.symptom),
        "evidence": clean(args.evidence),
        "status": "open",
    }
    raw.append("\t".join(values.get(col, "-") for col in header))
    save(raw)
    data_index.append(len(raw) - 1)
    print(f"✅ 已落箱 #{len(data_index)} [{args.severity}] {values['symptom']}")
    print_trigger(raw, header, data_index)
    return 0


def cmd_list(args):
    raw, header, data_index = load()
    st_i = header.index("status")
    shown = 0
    for n, pos in enumerate(data_index, 1):
        cells = cells_of(raw, header, pos)
        if not args.all and cells[st_i].strip().lower() == "resolved":
            continue
        shown += 1
        row = dict(zip(header, cells))
        print(f"#{n:<3} {row.get('status', '-'):<10} {row.get('severity', '-'):<7} "
              f"{row.get('timestamp', '-'):<16} {row.get('scene', '-')} :: {row.get('symptom', '-')}")
    if not shown:
        print("（没有未关闭的反馈）" if not args.all else "（收件箱为空）")
    print_trigger(raw, header, data_index)
    return 0


def cmd_set(args):
    raw, header, data_index = load()
    if not 1 <= args.row <= len(data_index):
        print(f"❌ 行号 #{args.row} 不存在（共 {len(data_index)} 条，用 list --all 查看）")
        return 1
    if args.status == "resolved" and clean(args.evidence) == "-":
        print("❌ 置 resolved 必须用 --evidence 附修复证据（results.tsv 行号 / commit / 回执路径）")
        return 1
    pos = data_index[args.row - 1]
    cells = cells_of(raw, header, pos)
    cells[header.index("status")] = args.status
    if clean(args.evidence) != "-" and "evidence" in header:
        ev_i = header.index("evidence")
        old = cells[ev_i].strip()
        tag = "修复证据" if args.status == "resolved" else "备注"
        cells[ev_i] = clean(f"{old} ; {tag}: {args.evidence}" if old and old != "-" else args.evidence)
    raw[pos] = "\t".join(cells[:max(len(header), len(cells))])
    save(raw)
    print(f"✅ #{args.row} → {args.status}")
    print_trigger(raw, header, data_index)
    return 0


def cmd_bump(args):
    if not MANIFEST.exists():
        print(f"❌ 缺血统清单 {MANIFEST}（用 pangu-create 的 scaffold.py --adopt 补登记）")
        return 1
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        print(f"❌ pangu.json 不可读: {exc}")
        return 2
    try:
        data["generation"] = int(data.get("generation", 0)) + 1
    except (TypeError, ValueError):
        print(f"❌ generation={data.get('generation')!r} 非整数，先人工修正")
        return 1
    if args.depth:
        current = data.get("depth", "L1")
        if current in DEPTHS and DEPTHS.index(args.depth) <= DEPTHS.index(current):
            print(f"❌ 深度只升不降：当前 {current}，请求 {args.depth}")
            return 1
        data["depth"] = args.depth
    data["last_evolved"] = date.today().isoformat()
    try:
        MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"❌ 写入失败: {exc}")
        return 2
    print(f"✅ {data.get('name', '?')} 代次 → {data['generation']}，深度 {data.get('depth')}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="盘古技能群 · 反馈收件箱")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="当场落一条反馈")
    add.add_argument("--severity", required=True, choices=SEVERITIES)
    add.add_argument("--scene", required=True, help="在做什么（场景）")
    add.add_argument("--symptom", required=True, help="出了什么问题（现象）")
    add.add_argument("--evidence", default="-", help="报错 / 文件路径 / 用户原话")
    lst = sub.add_parser("list", help="查看未关闭反馈与触发状态")
    lst.add_argument("--all", action="store_true", help="含 resolved")
    st = sub.add_parser("set", help="改状态：认领 processing / 关闭 resolved（须证据）")
    st.add_argument("row", type=int, help="list 显示的 #行号")
    st.add_argument("--status", required=True, choices=STATUSES)
    st.add_argument("--evidence", default="-")
    bump = sub.add_parser("bump", help="进化 keep 后代次 +1（可选晋升深度）")
    bump.add_argument("--depth", choices=DEPTHS)
    args = parser.parse_args()
    return {"add": cmd_add, "list": cmd_list, "set": cmd_set, "bump": cmd_bump}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
