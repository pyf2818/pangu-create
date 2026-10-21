#!/usr/bin/env python3
"""
F3.6/F4 出厂闸门（可执行）：缺「论点 / 范例 / 署名作品 / 确定性核心 / 承诺矩阵 / 故障注入 / 证据」时直接 exit 1。

这是文档规则的硬卡点：不靠模型自觉，靠退出码决定能不能交付。
用法:
    python3 verify_skill.py <目标skill目录> [--type output|text] [--json]

退出码: 0 全过 / 1 有闸门未过 / 2 路径或参数错误
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

META_FILES = {".gitkeep", ".ds_store", "readme.md", "index.md"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}
WORK_EXTS = {".html", ".htm", ".js", ".mjs", ".py", ".ts", ".tsx", ".jsx",
             ".md", ".json", ".glb", ".gltf", ".mp4", ".webm", ".svg", ".pdf"}
CORE_NAME = re.compile(r"(verify|finalize|build|validate|check|qa|score|inspect)", re.IGNORECASE)
INJECT_NAME = re.compile(r"(failure[_-]?inject|expect[_-]?fail|inject|negative)", re.IGNORECASE)
INJECT_FLAG = re.compile(r"(--expect-fail|expect_fail|failure[_-]?inject|--offline)", re.IGNORECASE)
SOFT_WORDS = re.compile(r"(视情况|视具体|大致|大概|尽量|随便|看情况)")
CMD_HINT = re.compile(r"(python|python3|node|npm|npx|bash|sh\s|curl|playwright|pytest|verify|finalize)", re.IGNORECASE)
INJECT_KINDS = {
    "依赖不可达": re.compile(r"(断网|离线|offline|cdn|unreachable|不可达|network|网络|block|黑洞)", re.IGNORECASE),
    "极端输入": re.compile(r"(空数组|空数据|empty|0\s*条|null|极端|超长|minimal|single|单件)", re.IGNORECASE),
    "环境缺失": re.compile(r"(无\s*gpu|no\s*gpu|webgl|headless|小屏|localstorage|无\s*权限|环境缺失)", re.IGNORECASE),
    "工具自伤": re.compile(r"(端口|port|权限|permission|missing|缺文件|文件不存在|unsafe)", re.IGNORECASE),
}



def section(text: str, heading: str) -> str:
    """取 '## heading' 到下一个同级标题之间的内容。"""
    m = re.search(rf"^##\s+{re.escape(heading)}.*$", text, re.MULTILINE)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def real_files(directory: Path):
    if not directory.exists():
        return []
    return [p for p in directory.rglob("*") if p.is_file() and p.name.lower() not in META_FILES]


def gate_thesis(root: Path):
    f = root / "references" / "design-thesis.md"
    if not f.exists():
        return False, "缺 references/design-thesis.md（论点档案）"
    text = f.read_text(encoding="utf-8", errors="replace")
    issues = []
    if "TODO" in text:
        issues.append("仍有 TODO 未填")
    answers = [a.strip() for a in re.findall(r"^\|\s*[^|]+\|\s*([^|]+)\|", section(text, "三问"), re.M)]
    # 分隔行（|---|-----| 等）会被上面的捕获组抓成第二列，必须按纯横线剔除，否则 2 问表格会被误计为 3 问
    answers = [a for a in answers if a and not re.fullmatch(r"-{2,}", a) and a not in {"回答"}]
    if len(answers) < 3:
        issues.append(f"三问只填了 {len(answers)} 条（需 3 条）")
    comp = section(text, "竞争测试")
    if not comp:
        issues.append("缺「竞争测试」段")
    elif "TODO" in comp:
        issues.append("竞争测试未结论")
    elif not re.search(r"不成立|不通过|只有本|说不出", comp):
        issues.append("竞争测试未给出「同类代入后不成立」的结论")
    materials = re.findall(r"^\|\s*\d+\s*\|", section(text, "独有素材") or text, re.MULTILINE)
    if len(materials) < 8:
        issues.append(f"独有素材 {len(materials)} 条（需 ≥8）")
    return (not issues), "；".join(issues) if issues else f"三问 3/3，独有素材 {len(materials)} 条"


def gate_examples(root: Path):
    dirs = [root / "examples", root / "assets" / "examples"]
    files = [p for d in dirs for p in real_files(d)]
    works = [p for p in files if p.suffix.lower() in WORK_EXTS]
    if len(works) < 3:
        return False, f"examples/ 可打开范例 {len(works)} 件（需 ≥3；截图与 README 不算）"
    return True, f"{len(works)} 件：" + "、".join(p.name for p in works[:5])


def gate_signature(root: Path):
    dirs = [root / "assets" / "showcase", root / "showcase"]
    files = [p for d in dirs for p in real_files(d)]
    works = [p for p in files if p.suffix.lower() in WORK_EXTS]
    if not files:
        return False, "缺 assets/showcase/（署名作品）"
    if not works:
        return False, f"showcase 只有 {len(files)} 张截图，没有可打开的作品文件"
    return True, "署名作品：" + "、".join(p.name for p in works[:3])


def gate_core(root: Path):
    scripts = [p for p in real_files(root / "scripts") if p.suffix.lower() in {".py", ".mjs", ".js", ".sh", ".ts"}]
    if not scripts:
        return False, "缺 scripts/（核心变换必须脚本化）"
    core = [p for p in scripts if CORE_NAME.search(p.stem)]
    if not core:
        return False, f"scripts/ 有 {len(scripts)} 个脚本，但没有 verify/finalize/build/validate/check 类一键验收脚本"
    return True, "一键验收：" + "、".join(p.name for p in core[:3])


def gate_promise(root: Path):
    """G1：承诺→断言矩阵存在且每行可执行。"""
    candidates = [root / "references" / "promise-table.md", root / "promise-table.md"]
    f = next((p for p in candidates if p.exists()), None)
    if f is None:
        return False, "缺 references/promise-table.md（承诺→断言矩阵，见 executable-checklist.md §1）"
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    rows, bad = [], []
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 4:
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if "承诺" in cells[0] or cells[0] in {"#", ""}:
            continue
        rows.append(cells)
        joined = " ".join(cells)
        if "TODO" in joined or "待填" in joined:
            bad.append(f"「{cells[0][:18]}」仍是 TODO")
            continue
        if SOFT_WORDS.search(joined):
            bad.append(f"「{cells[0][:18]}」含软化措辞")
        has_cmd = any("`" in c and CMD_HINT.search(c) for c in cells) or any(CMD_HINT.search(c) for c in cells[1:3])
        if not has_cmd:
            bad.append(f"「{cells[0][:18]}」无命令")
        has_evidence = len(cells) >= 4 and cells[3] not in {"", "-", "TODO", "待填"}
        if not has_evidence:
            bad.append(f"「{cells[0][:18]}」无证据")
    if len(rows) < 3:
        return False, f"承诺矩阵 {len(rows)} 行（需 ≥3，覆盖用户最在意的三条承诺）"
    if bad:
        return False, f"{len(rows)} 行，但：" + "；".join(bad[:5])
    return True, f"{len(rows)} 行，每行有断言/命令/证据"


def gate_failure_injection(root: Path):
    """G2：存在故障注入脚本或验收脚本的 --expect-fail 模式，且覆盖 ≥2 类注入。"""
    files = [p for d in (root / "tests", root / "scripts") for p in real_files(d)
             if p.suffix.lower() in {".py", ".mjs", ".js", ".sh", ".ts"}]
    named = [p for p in files if INJECT_NAME.search(p.stem)]
    flagged = []
    for p in files:
        try:
            if INJECT_FLAG.search(p.read_text(encoding="utf-8", errors="replace")):
                flagged.append(p)
        except Exception:
            continue
    if not named and not flagged:
        return False, "既无 tests/failure_injection.*，也无任何脚本含 --expect-fail / --offline 模式"
    pool = named + [p for p in flagged if p not in named]
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in pool[:5])
    if "TODO" in text or "待填" in text:
        return False, f"{pool[0].name} 仍是骨架（含 TODO），没有真实注入逻辑"
    kinds = [k for k, rgx in INJECT_KINDS.items() if rgx.search(text)]
    if len(kinds) < 2:
        return False, f"注入脚本覆盖 {len(kinds)} 类（需 ≥2）：" + "、".join(kinds or ["无"])
    return True, "、".join(p.name for p in pool[:3]) + f"；覆盖：{'、'.join(kinds)}"


def gate_evidence(root: Path):
    """G3：results.tsv 有 evidence 列且至少一行有非空证据。"""
    f = root / "results.tsv"
    if not f.exists():
        return False, "缺 results.tsv（进化三件套之一）"
    try:
        with open(f, "r", encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            fields = reader.fieldnames or []
            rows = list(reader)
    except Exception as e:
        return False, f"results.tsv 解析失败：{e}"
    if "evidence" not in [c.strip() for c in fields]:
        return False, f"results.tsv 表头缺 evidence 列（当前：{','.join(fields)}）"
    filled = [r for r in rows if (r.get("evidence") or "").strip() not in {"", "-", "TODO"}]
    if not filled:
        return False, "evidence 列全空（贴命令输出路径、截图或退出码，不接受「已测试」）"
    return True, f"{len(filled)} 行带证据，最近：{(filled[-1].get('evidence') or '')[:48]}"



def main() -> None:
    ap = argparse.ArgumentParser(description="产出型 skill 出厂闸门（exit 1 即拦截）")
    ap.add_argument("skill_dir", help="目标 skill 目录")
    ap.add_argument("--type", choices=["output", "text"], default="output",
                    help="output=产出型（跑全部闸门）；text=文本型（只查骨架）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    root = Path(args.skill_dir)
    if not root.is_dir():
        print(f"FATAL: 不是目录 {root}")
        sys.exit(2)
    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        print(f"FATAL: 缺 {skill_md}")
        sys.exit(2)

    gates = [("SKILL.md", True, f"{len(skill_md.read_text(encoding='utf-8', errors='replace').splitlines())} 行")]
    if args.type == "output":
        gates += [
            ("设计论点", *gate_thesis(root)),
            ("范例集", *gate_examples(root)),
            ("署名作品", *gate_signature(root)),
            ("确定性核心", *gate_core(root)),
            ("承诺矩阵", *gate_promise(root)),
            ("故障注入", *gate_failure_injection(root)),
            ("交付证据", *gate_evidence(root)),
        ]

    failed = [g for g in gates if not g[1]]
    if args.json:
        print(json.dumps({
            "skill": root.name,
            "type": args.type,
            "pass": not failed,
            "gates": [{"name": n, "pass": ok, "detail": d} for n, ok, d in gates],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"产出闸门: {root.name}（type={args.type}）")
        print("=" * 60)
        for name, ok, detail in gates:
            print(f"  {'PASS' if ok else 'FAIL'}  {name:<8} {detail}")
        print("=" * 60)
        if failed:
            print(f"结果: {len(failed)} 项未过 —— 不许进入 F4/F5，更不许宣称发布级。")
            print("修复顺序：design-thesis.md → examples/ ≥3 件 → assets/showcase/ 1 件作品 → scripts/ 一键验收 "
                  "→ references/promise-table.md → 故障注入脚本 → results.tsv evidence 列。")
        else:
            print("结果: 全过 ✅（仍须跑 F4 实测、故障注入复测与产出质量三关）")

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
