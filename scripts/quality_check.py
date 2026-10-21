#!/usr/bin/env python3
"""
盘古开天 静态质量自检：对照 11 维 rubric 中可静态判定的 11 项，逐项 PASS/FAIL。

用法:
    python3 quality_check.py <SKILL.md 路径>

说明:
    静态检查能拦住粗粒度缺陷（没有失败分支、没有检查点、软化措辞泛滥、资源路径失效），
    拦不住细粒度质量问题——后者走 testing.md 的独立评审与 paired 比较。
    本脚本退出码: 0 全过 / 1 存在 FAIL。
"""

import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MAX_BODY_LINES = 500
WARN_BODY_LINES = 650


def split_frontmatter(content: str):
    if not content.startswith("---"):
        return None, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content
    return parts[1], parts[2]


def check_frontmatter(fm: str | None, content: str):
    if fm is None:
        return False, "未找到 YAML frontmatter"
    name_m = re.search(r"^name:\s*([^\s]+)", fm, re.MULTILINE)
    desc_m = re.search(r"^description:\s*(.+?)(?=^\S|\Z)", fm, re.MULTILINE | re.DOTALL)
    if not name_m or not desc_m:
        return False, "缺少 name 或 description"
    name = name_m.group(1).strip()
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        return False, f"name 不是小写 kebab-case: {name}"
    desc = desc_m.group(1)
    if len(desc) > 1024:
        return False, f"description 超过 1024 字符（当前 {len(desc)}）"
    has_trigger = any(k in desc for k in ("触发", "trigger", "Use when", "use when", "when the user"))
    if not has_trigger:
        return False, "description 缺少触发条件（触发词 / Use when）"
    workflow_words = re.findall(r"Phase|Step \d|第一步|步骤一|首先.*然后", desc)
    if len(workflow_words) >= 3:
        return False, f"description 疑似总结了工作流（{len(workflow_words)} 处）——agent 会抄近路跳过正文"
    return True, f"name={name}, description {len(desc)} 字符, 含触发条件"


def check_workflow(body: str):
    has_phases = len(re.findall(r"^#{2,3}\s.*(Phase|阶段|Step|步骤)", body, re.MULTILINE | re.IGNORECASE))
    numbered = len(re.findall(r"^\s*\d+\.\s+\S", body, re.MULTILINE))
    if has_phases >= 2 or numbered >= 5:
        return True, f"结构步骤: {has_phases} 个阶段标题 / {numbered} 条编号步骤"
    return False, "未检测到明确的阶段/编号步骤结构"


def check_failure_branches(body: str):
    hits = 0
    hits += len(re.findall(r"如果.{0,24}失败|失败.{0,6}(兜底|降级|回退)|fallback|Fallback|FALLBACK", body))
    hits += len(re.findall(r"^\|\s*触发条件\s*\|", body, re.MULTILINE))
    hits += len(re.findall(r"三段式|一线修复|仍失败", body))
    passed = hits >= 3
    return passed, f"失败分支编码痕迹 {hits} 处 {'✅' if passed else '（需 ≥3；只写正向流程的 skill 不许出厂）'}"


def check_checkpoints(body: str):
    markers = len(re.findall(r"🔴|🛑|CHECKPOINT|STOP", body))
    passed = markers >= 1
    return passed, f"显性检查点标记 {markers} 处 {'✅' if passed else '（「建议确认」措辞不算，需 🔴/🛑/CHECKPOINT）'}"


SOFTENERS = ["建议你", "可以考虑", "视情况", "灵活把握", "酌情", "根据情况判断", "灵活应用"]


def _strip_quoted(text: str) -> str:
    """去掉被引号/反引号包裹的内容——反例引用中的措辞是被描述对象，不是指令（假阳性）。"""
    return re.sub(r"「[^」]*」|\"[^\"]*\"|`[^`]*`", "□", text)


def _strip_anti_sections(body: str) -> str:
    """反模式/黑名单/红灯章节里出现的软化措辞属假阳性，从扫描范围剔除。
    按标题行定位，删除整个章节（到下一个同级或更高级标题为止），而不只删标题行。"""
    out, skip, skip_level = [], False, 0
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})\s+", line)
        if m:
            level = len(m.group(1))
            if skip and level <= skip_level:
                skip, skip_level = False, 0
            if not skip and re.search(r"反模式|黑名单|红灯|Anti.?pattern|Red Flags", line, re.IGNORECASE):
                skip, skip_level = True, level
                continue
        if not skip:
            out.append(line)
    return "\n".join(out)


def check_specificity(body: str):
    scanned = _strip_quoted(_strip_anti_sections(body))
    found = [s for s in SOFTENERS if s in scanned]
    passed = len(found) < 3
    detail = f"软化措辞 {len(found)} 处: {found}" if found else "无软化措辞"
    return passed, detail + ("" if passed else "（≥3 处 FAIL——改为具体操作/参数/格式）")


def check_anti_examples(body: str):
    has_section = bool(re.search(r"^#{2,3}\s.*(反模式|黑名单|不要|禁止|Anti.?pattern|Red Flags|红灯)", body, re.MULTILINE | re.IGNORECASE))
    rows = len(re.findall(r"^\|\s*\d+\s*\|", body, re.MULTILINE)) + len(re.findall(r"^[-*]\s*(不要|禁止|绝不|Never|never)", body, re.MULTILINE))
    passed = has_section and rows >= 3
    return passed, f"反例章节={'有' if has_section else '无'}, 反例条目 {rows} 条（需 ≥3）"


def check_taste(body: str):
    has_iron = bool(re.search(r"铁律|Iron Law|HARD RULES|Hard Rules|硬规则", body))
    has_taste = bool(re.search(r"品味|审美|俗手|辨识|Taste|风格", body))
    passed = has_iron and has_taste
    return passed, f"铁律层={'有' if has_iron else '无'}, 品味层={'有' if has_taste else '无'}（两层都要有才够排他性）"


def check_honest_boundary(body: str):
    m = re.search(r"(?:^#{2,3}\s*.*(?:诚实边界|局限|Boundary|limitation).*?$)(.*?)(?=^#{1,3}\s|\Z)", body, re.MULTILINE | re.IGNORECASE | re.DOTALL)
    if not m:
        return False, "未找到诚实边界/局限章节"
    items = re.findall(r"^[-*]\s+\S", m.group(1), re.MULTILINE)
    passed = len(items) >= 3
    return passed, f"诚实边界 {len(items)} 条（需 ≥3 具体局限，只有一句「不能替代真人」不算）"


KNOWN_EXT = (".md", ".json", ".py", ".sh", ".js", ".mjs", ".html", ".csv")
RESOURCE_DIRS = ("references/", "scripts/", "assets/", "templates/")


def check_resources(md_path: Path, body: str, fm: str | None):
    """只检查真实指令性引用：markdown 链接 + 「读/见/运行 X」句式中的路径。
    「产出/写入/存入 X」是对目标 skill 生成产物的描述，不属于本 skill 的资源依赖（假阳性）。"""
    text = (fm or "") + "\n" + body
    root = md_path.parent
    refs = set()

    for link in re.findall(r"\]\(([^)]+)\)", text):
        if link.startswith(("http", "#")):
            continue
        if any(link.startswith(d) for d in RESOURCE_DIRS) and link.endswith(KNOWN_EXT):
            refs.add(link)

    for line in text.splitlines():
        if not re.match(r"^\s*(?:先读|读|见|参见|查看|执行|运行|打开)", line):
            continue
        for m in re.findall(r"`((?:references|scripts|assets|templates)/[\w\-./]+)`", line):
            if m.endswith(KNOWN_EXT):
                refs.add(m)

    if not refs:
        return True, "未引用本地资源文件（单文件 skill，跳过）"
    missing = [r for r in sorted(refs) if not (root / r).exists()]
    passed = not missing
    detail = f"{len(refs)} 个指令性引用全部可达 ✅" if passed else f"引用失效: {missing}"
    return passed, detail


def check_self_contained(md_path: Path, body: str):
    external = re.findall(r"\.\./[\w\-./]+", body)
    bad = [p for p in set(external) if not p.startswith("../research")]
    passed = len(bad) == 0
    detail = "引用全部在 skill 目录内 ✅" if passed else f"存在目录外引用（破坏自包含原则）: {bad}"
    return passed, detail


def check_size(md_path: Path):
    content = md_path.read_text(encoding="utf-8")
    _, body = split_frontmatter(content)
    n = len(body.splitlines())  # 只计正文（rubric 维度 7 的口径是正文 ≤500 行）
    if n <= MAX_BODY_LINES:
        return True, f"正文 {n} 行（≤{MAX_BODY_LINES}，渐进式披露合格）"
    if n <= WARN_BODY_LINES:
        return True, f"正文 {n} 行 ⚠️（超过 {MAX_BODY_LINES}，重参考应移入 references/）"
    return False, f"正文 {n} 行 ❌（超过 {WARN_BODY_LINES}，正文过载）"


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    md_path = Path(sys.argv[1])
    if not md_path.exists():
        print(f"❌ 文件不存在: {md_path}")
        sys.exit(1)

    content = md_path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(content)

    checks = [
        ("Frontmatter 质量", lambda: check_frontmatter(fm, content)),
        ("工作流清晰度", lambda: check_workflow(body)),
        ("失败分支编码", lambda: check_failure_branches(body)),
        ("检查点设计", lambda: check_checkpoints(body)),
        ("可执行具体性", lambda: check_specificity(body)),
        ("反例与黑名单", lambda: check_anti_examples(body)),
        ("品味与排他性", lambda: check_taste(body)),
        ("诚实边界", lambda: check_honest_boundary(body)),
        ("资源可达性", lambda: check_resources(md_path, body, fm)),
        ("自包含", lambda: check_self_contained(md_path, body)),
        ("体积预算", lambda: check_size(md_path)),
    ]

    print(f"盘古开天 静态自检: {md_path.name}")
    print("=" * 56)
    passed_count = 0
    for name, fn in checks:
        try:
            passed, detail = fn()
        except Exception as e:  # 单项异常不中断整体
            passed, detail = False, f"检查器异常: {e}"
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name:<10} {status}  {detail}")
        passed_count += bool(passed)
    print("=" * 56)
    total = len(checks)
    print(f"结果: {passed_count}/{total} 通过")
    if passed_count == total:
        print("🎉 静态全过。细粒度质量请继续走 testing.md 的独立评审与 paired 比较。")
    elif passed_count >= total - 2:
        print("⚠️  基本通过，修复 FAIL 项后交付。")
    else:
        print("❌ 多项不通过——回到 F3 构建/进化循环修复，不许出厂。")
    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    main()
