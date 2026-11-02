#!/usr/bin/env python3
"""
盘古印记（seal）：让每个盘古锻造的 skill 在「使用现场」就带着反馈与进化协议。

为什么需要它:
  pangu.json / feedback/inbox.tsv 只是旁路文件；skill 被使用时，运行时只加载
  该 skill 的 SKILL.md——盘古本身通常没被激活。若 SKILL.md 里没有「出问题就落箱」
  的指令，进化触发器永远不会被扣动（v1.4 实测：9 个锻造 skill 0/9 有此指令）。
  印记 = SKILL.md 末尾一个有边界标记的小区块 + 随 skill 分发的 feedback/log.py。

契约:
  - 区块以 `<!-- pangu:seal v1 lineage=<id> ... -->` 开头、`<!-- /pangu:seal -->` 结尾；
    apply_seal 幂等（有则替换、无则追加），区块外的任何字节都不改动。
  - 印记是管理元数据：verify_skill 计算源码指纹时剥掉区块（strip_seal_bytes），
    盖章 / 刷新印记不会让行为回执过期。
  - 本模块只被 scaffold.py / registry.py / verify_skill.py 引用，零第三方依赖。
"""

import re

SEAL_VERSION = 1
SEAL_OPEN = "<!-- pangu:seal"
SEAL_CLOSE = "<!-- /pangu:seal -->"

# 剥离时连同追加时插入的那一个前导换行一起去掉，保证「盖章前指纹 == 盖章后指纹」
_SEAL_TEXT_RE = re.compile(r"(?:\r?\n)?^<!-- pangu:seal\s+v\d+\s+lineage=[^>]*-->.*?^<!-- /pangu:seal -->[ \t]*(?:\r?\n)?", re.S | re.M)
_SEAL_BYTES_RE = re.compile(rb"(?:\r?\n)?^<!-- pangu:seal\s+v\d+\s+lineage=[^>]*-->.*?^<!-- /pangu:seal -->[ \t]*(?:\r?\n)?", re.S | re.M)
_HEAD_RE = re.compile(r"^<!-- pangu:seal\s+v(?P<version>\d+)(?P<attrs>\s+lineage=[^>]*)-->", re.M)
_ATTR_RE = re.compile(r"(\w+)=(\S+)")


def render_seal(lineage_id: str, pangu_version: str) -> str:
    """生成印记区块（以换行结尾）。命令路径按 skill 目录给出，log.py 自己按文件位置找收件箱。"""
    return (
        f"<!-- pangu:seal v{SEAL_VERSION} lineage={lineage_id} forged_by=pangu-create pangu={pangu_version} -->\n"
        "## 盘古印记 · 反馈与进化\n"
        "\n"
        f"> 本 skill 由 pangu-create 锻造，纳入技能群管理（血统 `{lineage_id}`，见 `pangu.json`）。"
        "交付只是第 0 代——使用中暴露的问题就是下一代的输入。\n"
        "\n"
        "**使用中遇到真实问题**（用户不满意 / 报错 / 静默失败 / 产出不合预期），当场记一笔，不要只口头说「记住了」：\n"
        "\n"
        "```bash\n"
        "python <本skill目录>/feedback/log.py add --severity major --scene \"在做什么\" --symptom \"出了什么问题\" --evidence \"报错/路径/用户原话\"\n"
        "```\n"
        "\n"
        "- `severity`：blocker（核心承诺失效）/ major（明显影响产出）/ minor（打磨项）；纯环境抖动（断网、端口占用）不记\n"
        "- open 的 blocker/major，或 open 的 minor ≥3 条 = **强制进化触发器**：调用 pangu-create 时会被列入进化队列优先修复\n"
        "- 无 `python` 用 `python3`；都没有就按 `feedback/README.md` 手动追加一行 TSV。查看：`log.py list`\n"
        f"{SEAL_CLOSE}\n"
    )


def read_seal(text: str):
    """返回 {'version': int, 'lineage': str|None, ...} 或 None（无印记 / 区块未闭合）。"""
    match = _HEAD_RE.search(text)
    if not match or SEAL_CLOSE not in text[match.end():]:
        return None
    attrs = dict(_ATTR_RE.findall(match.group("attrs")))
    return {"version": int(match.group("version")), "lineage": attrs.get("lineage"), **attrs}


def apply_seal(text: str, block: str) -> str:
    """幂等盖章：已有区块 → 原位替换；没有 → 追加到末尾（先补齐末尾换行，再空一行）。"""
    if _SEAL_TEXT_RE.search(text):
        return _SEAL_TEXT_RE.sub(lambda _m: "\n" + block, text, count=1)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + "\n" + block


def strip_seal_bytes(data: bytes) -> bytes:
    """指纹用：剥掉印记区块。没有区块时原样返回（不影响任何未盖章 skill 的既有指纹）。"""
    if SEAL_OPEN.encode("utf-8") not in data:
        return data
    return _SEAL_BYTES_RE.sub(b"", data, count=1)


FEEDBACK_README = """# 反馈收件箱（进化触发器）

> 使用本 skill 过程中遇到的每个真实问题（用户抱怨 / 报错 / 静默失败 / 产出不合预期），
> 执行 agent 必须**当场**记一行——不许只口头说「记下了」。优先用工具写，避免手写 TSV 写坏：
>
>     python feedback/log.py add --severity major --scene "在做什么" --symptom "出了什么问题" --evidence "报错/路径/原话"
>
> severity=blocker/major 且 status=open，或 open 的 minor ≥3 条 = 强制进化触发器（盘古进化契约 #8）。

severity: blocker（阻断核心承诺）/ major（明显影响产出）/ minor（打磨项）
status:   open → processing（进化轮已认领）→ resolved（必须附修复证据：results.tsv 行号 / commit / 回执）

其他命令：
- `log.py list [--all]`：看未关闭的反馈与是否触发进化
- `log.py set <行号> --status processing|resolved --evidence "..."`：认领 / 关闭（resolved 必须带证据）
- `log.py bump [--depth L2|L3]`：进化 keep 后代次 +1（深度只升不降），写回 ../pangu.json

无 Python 时手动追加（6 列，制表符分隔）：timestamp / severity / scene / symptom / evidence / status
"""


FEEDBACK_LOG_PY = '''#!/usr/bin/env python3
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
    text = " ".join(str(value or "").replace("\\t", " ").split())
    return text or "-"


def load():
    """返回 (raw_lines, header, data_index)；data_index[i] = 第 i+1 条数据在 raw_lines 中的位置。"""
    if not INBOX.exists():
        return ["\\t".join(HEADER)], HEADER[:], []
    raw = INBOX.read_text(encoding="utf-8-sig").splitlines()
    header, data_index = None, []
    for pos, line in enumerate(raw):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if header is None:
            header = [c.strip().lower() for c in line.split("\\t")]
            continue
        data_index.append(pos)
    if header is None:
        raw, header = ["\\t".join(HEADER)] + raw, HEADER[:]
    if "severity" not in header or "status" not in header:
        print(f"❌ {INBOX} 表头不合规，需包含: {' / '.join(HEADER)}")
        sys.exit(1)
    return raw, header, data_index


def save(raw):
    try:
        INBOX.write_text("\\n".join(raw) + "\\n", encoding="utf-8")
    except OSError as exc:
        print(f"❌ 写入失败: {exc}")
        sys.exit(2)


def cells_of(raw, header, pos):
    cells = raw[pos].split("\\t")
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
    raw.append("\\t".join(values.get(col, "-") for col in header))
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
    raw[pos] = "\\t".join(cells[:max(len(header), len(cells))])
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
        MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
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
'''
