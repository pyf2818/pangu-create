#!/usr/bin/env python3
"""
盘古开天 rubric 自动评分：对照 references/rubric.md 的 11 维评分标准，
对 SKILL.md 逐维打 1-10 分 × 权重，输出加权总分（满分 100）。

设计原则:
  - 维度 1-7、9、11（结构/元/材料维度）：静态分析自动打分
  - 维度 8（实测表现）与维度 10（品味与排他性）：不自动判分——关键词命中不等于
    作品更好，必须人工/盲评；自动总分上限 75，禁止把结构分当能力分
  - 维度 11 自动项只证明材料存在（三问/竞争测试/范例），不裁决原创性
  - 绝对总分只用于 triage（哪支最弱、先改谁），keep/revert 一律走 paired 同-judge
  - 输出与 quality_check.py 互补：后者是 11 项二值自检（粗筛），本脚本是细粒度打分

用法:
    python3 rubric_score.py <SKILL.md 路径> [--type auto|output|text] [--json]

分型（D6/D11 的判据随类型切换，与 verify_skill.py --type 同一口径）:
    output  产出型：有 examples/showcase 范例资产，或无元技能特征（从严）
    text    文本/元技能型：无范例资产 + 正文含元技能特征（锻造管线/万物皆可成技能等）
    auto    先看范例资产（最硬证据），无资产再按正文特征判 text；都判不出按 output 从严

退出码:
    0 全维度有分（维度 8 标注需人工也算 0）
    1 文件不存在或无法解析
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── 权重表（与 rubric.md 一致，总和 100）──
WEIGHTS = {
    1: ("Frontmatter 质量", 7),
    2: ("工作流清晰度", 11),
    3: ("失败分支编码", 11),
    4: ("检查点设计", 6),
    5: ("可执行具体性", 12),
    6: ("资源整合度", 4),
    7: ("整体架构", 10),
    8: ("实测表现", 19),
    9: ("反例与黑名单", 4),
    10: ("品味与排他性", 6),
    11: ("设计洞察与署名作品", 10),
}

MAX_BODY_LINES = 500
SOFTENERS = ["建议你", "可以考虑", "视情况", "灵活把握", "酌情", "根据情况判断", "灵活应用"]
AI_FILLER = ["说白了", "换句话说", "首先其次综上", "总而言之", "综上所述"]

META_HINT = re.compile(r"元技能|锻造管线|万物皆可成技能|创建 ?skill|造 ?skill|蒸馏成 ?skill")
CORPUS_DIRS = ("examples", "assets/examples", "showcase", "assets/showcase")


def detect_skill_type(md_path: Path, body: str, forced: str = "auto") -> str:
    """D6/D11 分型（与 verify_skill.py --type 同一口径）。

    实测坑（pangu-create 自评假阴性）：元技能 SKILL.md 里给下游技能写的模板路径
    （references/design-thesis.md 等）被 D6 当成自身失效引用、D11 被判「无范例」——
    元技能的范例是它锻造出的下游 skill，不存在于自身目录。分型后各用各的判据。

    优先级（v1.4.0 修正）：frontmatter description 里的元技能自述 > 范例资产存在 >
    正文元技能特征 > 从严 output。为什么自述优先于资产：元技能的 showcase 放的是
    下游作品截图（pangu 的 assets/showcase 全是锻造产物），资产存在不构成产出型证据；
    description 是技能对自身身份的显式声明，是更强的信号。产出型从严兜底不变。
    """
    if forced in ("output", "text"):
        return forced
    fm, _ = split_frontmatter(md_path.read_text(encoding="utf-8-sig"))
    if fm and META_HINT.search(fm):
        return "text"
    root = md_path.parent
    has_corpus = any(
        (root / d).exists() and any(f.is_file() for f in (root / d).rglob("*"))
        for d in CORPUS_DIRS
    )
    if has_corpus:
        return "output"
    if META_HINT.search(body):
        return "text"
    return "output"  # 无范例资产也无元技能特征：按产出型从严（D11 会如实指出缺范例）


def split_frontmatter(content: str):
    if not content.startswith("---"):
        return None, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content
    return parts[1], parts[2]


def _strip_quoted(text: str) -> str:
    return re.sub(r"「[^」]*」|\"[^\"]*\"|`[^`]*`", "□", text)


def _strip_anti_sections(body: str) -> str:
    """删除反模式/黑名单章节（假阳性剔除），保留其余内容用于软化措辞扫描。"""
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


# ═══════════════════════════════════════════════════════════════════════════
# 各维度评分函数：返回 (分数 1-10, 理由)
# ═══════════════════════════════════════════════════════════════════════════

def score_dim1_frontmatter(fm: str | None, content: str):
    """维度1 Frontmatter 质量（权重7）"""
    if fm is None:
        return 1, "无 frontmatter"

    checks = {}
    # 1a name 是 kebab-case
    m = re.search(r"^name:\s*([^\s]+)", fm, re.MULTILINE)
    checks["name_kebab"] = bool(m and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", m.group(1).strip()))

    # 1b description 存在且有内容
    dm = re.search(r"^description:\s*(.+?)(?=^\S|\Z)", fm, re.MULTILINE | re.DOTALL)
    has_desc = bool(dm and len(dm.group(1).strip()) > 20)
    checks["has_desc"] = has_desc

    # 1c description ≤1024
    checks["desc_len"] = bool(dm and len(dm.group(1).strip()) <= 1024)

    # 1d 含触发条件
    desc = dm.group(1) if dm else ""
    checks["has_trigger"] = any(k in desc for k in ("触发", "trigger", "Use when", "use when", "when the user"))

    # 1e 不总结工作流（Phase/Step 出现 <3 次）
    wf_hits = len(re.findall(r"Phase|Step \d|第一步|步骤一|首先.*然后", desc))
    checks["no_workflow_summary"] = wf_hits < 3

    # 1f 禁空话尾巴
    tail_hits = len(re.findall(r"灵活应用|根据情况判断|视情况而定|酌情处理", desc))
    checks["no_tail"] = tail_hits == 0

    passed = sum(checks.values())
    # 6 项全过=10, 5=8, 4=6, 3=4, <3=2
    score = {6: 10, 5: 8, 4: 6, 3: 4, 2: 3, 1: 2, 0: 1}[passed]
    reasons = [k.replace("_", " ") + ("✓" if v else "✗") for k, v in checks.items()]
    return score, "; ".join(reasons)


def score_dim2_workflow(body: str):
    """维度2 工作流清晰度（权重11）"""
    checks = {}

    # 2a 有阶段标题（Phase/阶段 ≥2 个）
    phases = len(re.findall(r"^#{2,3}\s.*(Phase|阶段|Step|步骤)", body, re.MULTILINE | re.IGNORECASE))
    checks["has_phases"] = phases >= 2

    # 2b 有序号步骤（≥5 条）
    numbered = len(re.findall(r"^\s*\d+\.\s+\S", body, re.MULTILINE))
    checks["has_numbered"] = numbered >= 5

    # 2c 有入口分流表（状态路由/分流）
    checks["has_routing"] = bool(re.search(r"状态路由|入口分流|按.*分流|路由表|route", body, re.IGNORECASE))

    # 2d 有输入→输出描述（→ 箭头或 输入/输出 关键词）
    arrow_count = len(re.findall(r"→|输入|输出|Input|Output", body))
    checks["has_io"] = arrow_count >= 3

    # 2e 有执行协议/问题分类表
    checks["has_protocol"] = bool(re.search(r"执行协议|Agentic Protocol|问题类型|任务类型", body, re.IGNORECASE))

    passed = sum(checks.values())
    score = {5: 10, 4: 8, 3: 6, 2: 4, 1: 2, 0: 1}[passed]
    reasons = [k.replace("_", " ") + ("✓" if v else "✗") for k, v in checks.items()]
    return score, "; ".join(reasons)


def score_dim3_failure(body: str):
    """维度3 失败分支编码（权重11）"""
    checks = {}

    # 3a 有"如果X失败"句式
    checks["has_if_fail"] = bool(re.search(r"如果.{0,24}失败|失败.{0,6}(兜底|降级|回退)", body))

    # 3b 有三段式（一线修复/仍失败）
    checks["has_three_tier"] = bool(re.search(r"一线修复|仍失败|兜底", body))

    # 3c 有失败分支表（| 触发条件 |）
    checks["has_table"] = bool(re.search(r"^\|\s*触发条件\s*\|", body, re.MULTILINE))

    # 3d 有 fallback/降级关键词
    checks["has_fallback"] = bool(re.search(r"fallback|Fallback|FALLBACK|降级|回退", body))

    # 3e 失败分支数量（≥5 条算高分）
    fail_entries = len(re.findall(r"^\|\s*[^|]+\|.*失败.*\|", body, re.MULTILINE))
    fail_entries += len(re.findall(r"^\|\s*[^|]+\|.*fallback.*\|", body, re.MULTILINE))
    checks["enough_entries"] = fail_entries >= 5

    passed = sum(checks.values())
    # 5项全过=10, 但如果没有失败表(3c)则封顶6（rubric: 只写正向流程扣≥3分）
    score = {5: 10, 4: 8, 3: 6, 2: 4, 1: 2, 0: 1}[passed]
    if not checks.get("has_table"):
        score = min(score, 6)  # 只写正向流程本维≤6
    if not checks.get("has_if_fail") and not checks.get("has_table"):
        score = min(score, 4)  # 完全没有失败分支扣≥3分
    reasons = [k.replace("_", " ") + ("✓" if v else "✗") for k, v in checks.items()]
    return score, "; ".join(reasons)


def score_dim4_checkpoints(body: str):
    """维度4 检查点设计（权重6）"""
    # 显性标记
    markers = len(re.findall(r"🔴|🛑|CHECKPOINT|STOP", body))
    # 普通确认措辞
    soft = len(re.findall(r"建议确认|请确认|让用户确认", body))

    if markers >= 3:
        return 10, f"显性标记 {markers} 处 ✓✓✓"
    elif markers >= 2:
        return 8, f"显性标记 {markers} 处 ✓✓"
    elif markers == 1:
        return 6, f"显性标记 1 处 ✓"
    elif soft >= 1:
        return 4, f"仅有软化确认措辞（{soft} 处），无显性标记 ✗"
    else:
        return 2, "无检查点"


def score_dim5_specificity(body: str):
    """维度5 可执行具体性（权重12）"""
    scanned = _strip_quoted(_strip_anti_sections(body))

    # 5a 软化措辞计数（≥3 扣分）
    found = [s for s in SOFTENERS if s in scanned]
    soft_count = len(found)

    # 5b 具体参数/格式/示例（代码块、命令、参数名）
    cmd_count = len(re.findall(r"```(?:bash|python|sh|shell)", body))
    arg_count = len(re.findall(r"--[\w-]+", body))
    examples = len(re.findall(r"示例|例如|比如|Example", body))

    # 5c 有命令/脚本调用
    has_cmd = cmd_count >= 1 or arg_count >= 3

    # 打分
    score = 10
    if soft_count >= 5:
        score = 4
    elif soft_count >= 3:
        score = 6
    elif soft_count >= 1:
        score = 8

    if not has_cmd:
        score = min(score, 7)

    if examples >= 3:
        score = min(10, score + 1)
    elif examples == 0:
        # 只有命令没有样例 = 执行者仍要自行想象产出形态（rubric D5：示例 0 处 ≤7 分）
        score = min(score, 5 if not has_cmd else 7)

    reasons = []
    reasons.append(f"软化措辞 {soft_count} 处" + ("✗" if soft_count >= 3 else "✓"))
    # 实测坑（csvviz-forge）：旧 note 只显示 fence 数，内联 --参数 达标时仍显示「0 个」误导排查
    reasons.append(f"命令fence {cmd_count} 个/--参数 {arg_count} 处" + ("✓" if has_cmd else "✗"))
    reasons.append(f"示例/举例 {examples} 处")
    return score, "; ".join(reasons)


def score_dim6_resources(md_path: Path, body: str, fm: str | None, skill_type: str = "output"):
    """维度6 资源整合度（权重4）"""
    text = (fm or "") + "\n" + body
    root = md_path.parent
    KNOWN_EXT = (".md", ".json", ".py", ".sh", ".js", ".mjs", ".html", ".csv")
    RESOURCE_DIRS = ("references/", "scripts/", "assets/", "templates/")

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

    # 任何位置的路径提及都算引用（file map 树/代码围栏/内联代码）——
    # 实测坑（csvviz-forge）：旧正则只认 md 链接+指令性 backtick，对代码围栏里的 file map 失明，
    # 与 quality_check/verify_skill 的资源闸门互相矛盾。
    # 但仅对产出型生效：文本/元技能型的围栏路径是给下游技能的模板骨架，不是自身资源
    # （实测坑：pangu-create 自评 D6=4/10 假阴性，9 个「失效引用」全是指向下游产物的模板路径）
    if skill_type != "text":
        for m in re.findall(r"(?:references|scripts|assets|templates)/[\w\-./]+", text):
            if m.endswith(KNOWN_EXT):
                refs.add(m)

    if not refs:
        return 8, "无本地资源引用（单文件 skill），降级扣分"
    missing = [r for r in sorted(refs) if not (root / r).exists()]
    mode_note = "；text 型：围栏模板路径不计为自身引用" if skill_type == "text" else ""
    if not missing:
        return 10, f"{len(refs)} 个引用全部可达 ✓{mode_note}"
    else:
        return 4, f"{len(missing)}/{len(refs)} 个引用失效 ✗: {missing[:3]}{mode_note}"


def score_dim7_architecture(body: str, md_path: Path):
    """维度7 整体架构（权重10）"""
    checks = {}

    # 7a 正文 ≤500 行
    body_lines = len(body.splitlines())
    checks["size_ok"] = body_lines <= MAX_BODY_LINES
    size_score = {True: 3, False: 1}[checks["size_ok"]]

    # 7b 无 AI 腔废话
    filler = [f for f in AI_FILLER if f in body]
    checks["no_filler"] = len(filler) == 0
    filler_score = {True: 3, False: 1}[checks["no_filler"]]

    # 7c 有渐进式披露（references/ 或 scripts/ 引用）
    has_disclosure = bool(re.search(r"references/|scripts/|assets/", body))
    checks["has_disclosure"] = has_disclosure
    disc_score = {True: 2, False: 0}[checks["has_disclosure"]]

    # 7d 有品味/铁律章节（负重维度覆盖的迹象）
    has_taste = bool(re.search(r"铁律|品味|审美|俗手|Iron Law|Hard Rules", body))
    checks["has_quality_anchor"] = has_taste
    qa_score = {True: 2, False: 0}[checks["has_quality_anchor"]]

    score = size_score + filler_score + disc_score + qa_score
    reasons = [
        f"正文{body_lines}行" + ("✓" if checks["size_ok"] else "✗"),
        f"AI腔{len(filler)}" + ("✓" if checks["no_filler"] else "✗"),
        f"渐进披露" + ("✓" if checks["has_disclosure"] else "✗"),
        f"质量锚点" + ("✓" if checks["has_quality_anchor"] else "✗"),
    ]
    return score, "; ".join(reasons)


def score_dim8_testing():
    """维度8 实测表现（权重19）——需人工实测"""
    return None, (
        "需人工实测：跑测试题对比 with_skill vs baseline（见 testing.md §2-4）；"
        "产出型另过产出质量三关（参照物/工艺参数/盲评，见 output-quality.md）"
    )


def output_quality_evidence(md_path: Path, body: str):
    """产出质量门证据探测（启发式，仅提示不判分）。"""
    root = md_path.parent
    art = (root / "references" / "art-direction.md").exists()
    showcase_dirs = [root / "assets" / "showcase", root / "showcase"]
    showcase = any(d.exists() and any(d.iterdir()) for d in showcase_dirs if d.exists())
    is_meta = bool(re.search(r"元技能|锻造管线|万物皆可成技能|创建 ?skill|造 ?skill", body))
    visual_skill = (not is_meta) and bool(
        re.search(r"观感|视觉|美术|排版|配色|动效|页面|视频|游戏|3D|卡片|小说|PPT|设计", body)
    )
    return {
        "visual_skill": visual_skill,
        "art_direction": art,
        "showcase": showcase,
    }


def score_dim9_anti_examples(body: str):
    """维度9 反例与黑名单（权重4）"""
    checks = {}

    # 9a 有反模式章节
    has_section = bool(re.search(r"^#{2,3}\s.*(反模式|黑名单|不要|禁止|Anti.?pattern|Red Flags|红灯)", body, re.MULTILINE | re.IGNORECASE))
    checks["has_section"] = has_section

    # 9b 反例条目数（表格行 + 列表项）
    table_rows = len(re.findall(r"^\|\s*\d+\s*\|", body, re.MULTILINE))
    list_items = len(re.findall(r"^[-*]\s*(不要|禁止|绝不|Never|never)", body, re.MULTILINE))
    total = table_rows + list_items
    checks["enough_items"] = total >= 3

    # 9c 有"为什么"解释（反例不止是禁令）
    has_why = bool(re.search(r"为什么|替代做法|替代|reason|why", body, re.IGNORECASE))
    checks["has_why"] = has_why

    passed = sum(checks.values())
    # rubric: 只写"应该做X"没"不要做Y"扣≥3分
    score = {3: 10, 2: 7, 1: 4, 0: 1}[passed]
    if not checks.get("has_section"):
        score = min(score, 3)
    reasons = [k.replace("_", " ") + ("✓" if v else "✗") for k, v in checks.items()]
    reasons.append(f"反例条目 {total} 条")
    return score, "; ".join(reasons)


def score_dim10_taste(body: str):
    """维度10 品味与排他性（权重6）——不自动判分。

    关键词命中（「铁律」「俗手」「配方」）不能证明判断力属于领域前 1%，
    旧实现会给「铁律 品味 反模式 示例」这类占位文本 10/10，属于重度虚高。
    本维固定返回 None，由人工盲评按 rubric 锚点判定。
    """
    return None, (
        "需人工盲评：判断「删掉领域名后仍能认出是谁家的方法论」；"
        "关键词命中不作分数（见 rubric.md D10 锚点）"
    )


def score_dim11_insight(md_path: Path, body: str, skill_type: str = "output"):
    """维度11 设计洞察与署名作品（权重10）"""
    root = md_path.parent
    checks = {}

    # 11a 论点被显式声明（三问/North Star）
    checks["thesis_declared"] = bool(
        re.search(r"设计论点|North Star|一句话论点|design thesis", body, re.IGNORECASE)
    )

    # 11b 竞争测试：同类代入后不成立
    checks["competition_test"] = bool(
        re.search(r"竞争测试|competitor test|同类.{0,12}成立|只有本 ?skill", body, re.IGNORECASE)
    )

    if skill_type == "text":
        # 文本/元技能型：范例=它锻造/服务的下游产物，不存在于自身目录——
        # 判据换成「进化三件套」（test-prompts/results.tsv/git 或备份链，铁律 10）
        trio = [
            (root / "test-prompts.json").exists(),
            (root / "results.tsv").exists(),
            (root / ".git").exists() or bool(list(root.glob("*.bak.*"))),
        ]
        checks["evolution_trio"] = all(trio)

        # 确定性核心：核心变换脚本化 + 一键 verify/finalize
        scripts_dir = root / "scripts"
        script_files = [p for p in scripts_dir.rglob("*") if p.is_file()] if scripts_dir.exists() else []
        has_scripts = bool(script_files)
        has_verify = any(
            re.search(r"(verify|finalize|build|validate)\.(py|mjs|js|sh)$", p.name)
            for p in script_files
        ) or bool(re.search(r"一键|verify|finalize", body, re.IGNORECASE) and has_scripts)
        checks["deterministic_core"] = has_scripts and has_verify

        passed = sum(checks.values())
        score = {4: 10, 3: 8, 2: 5, 1: 3, 0: 0}[passed]
        reasons = [k.replace("_", " ") + ("✓" if v else "✗") for k, v in checks.items()]
        reasons.append("text 型判据（三件套替代范例集/署名作品）")
        reasons.append("自动项仅证明材料存在；原创性与竞争结论需独立评审")
        return score, "; ".join(reasons)

    # 11c 论点档案落盘
    checks["thesis_file"] = (root / "references" / "design-thesis.md").exists()

    # 11d 范例集：≥3 件可打开/可运行的文件
    corpus_dirs = [root / "examples", root / "assets" / "examples"]
    corpus = sum(
        sum(1 for p in d.rglob("*") if p.is_file())
        for d in corpus_dirs
        if d.exists()
    )
    checks["example_corpus"] = corpus >= 3

    # 11e 署名作品
    showcase_dirs = [root / "assets" / "showcase", root / "showcase"]
    checks["signature_work"] = any(
        d.exists() and any(p.is_file() for p in d.rglob("*"))
        for d in showcase_dirs
    )

    # 11f 确定性核心：核心变换脚本化 + 一键 verify/finalize
    scripts_dir = root / "scripts"
    script_files = [p for p in scripts_dir.rglob("*") if p.is_file()] if scripts_dir.exists() else []
    has_scripts = bool(script_files)
    has_verify = any(
        re.search(r"(verify|finalize|build|validate)\.(py|mjs|js|sh)$", p.name)
        for p in script_files
    ) or bool(re.search(r"一键|verify|finalize", body, re.IGNORECASE) and has_scripts)
    checks["deterministic_core"] = has_scripts and has_verify

    passed = sum(checks.values())
    score = {6: 10, 5: 9, 4: 7, 3: 5, 2: 3, 1: 1, 0: 0}[passed]
    reasons = [k.replace("_", " ") + ("✓" if v else "✗") for k, v in checks.items()]
    reasons.append(f"范例文件 {corpus} 件")
    return score, "; ".join(reasons)


# ═══════════════════════════════════════════════════════════════════════════
# 运行时中立性红灯扫描（gate 项）
# ═══════════════════════════════════════════════════════════════════════════

def scan_runtime_neutrality(body: str, fm: str | None):
    """扫描运行时中立性红灯。返回 (命中数, 命中行列表)"""
    text = (fm or "") + "\n" + body
    red_patterns = [
        r"在 Claude Code", r"Claude Code skill", r"Claude Code 用户",
        r"Cursor only", r"在 Codex 中", r"~/\.claude/skills/[a-z]",
        r"/plugin install\b", r"在 Cursor 里", r"在 Windsurf 里",
    ]
    hits = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for pat in red_patterns:
            if re.search(pat, line):
                hits.append(f"L{line_no}: {line.strip()[:80]}")
    return len(hits), hits


# ═══════════════════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════════════════

SCORE_FUNCS = {
    1: lambda md, fm, body, st: score_dim1_frontmatter(fm, body),
    2: lambda md, fm, body, st: score_dim2_workflow(body),
    3: lambda md, fm, body, st: score_dim3_failure(body),
    4: lambda md, fm, body, st: score_dim4_checkpoints(body),
    5: lambda md, fm, body, st: score_dim5_specificity(body),
    6: lambda md, fm, body, st: score_dim6_resources(md, body, fm, st),
    7: lambda md, fm, body, st: score_dim7_architecture(body, md),
    8: lambda md, fm, body, st: score_dim8_testing(),
    9: lambda md, fm, body, st: score_dim9_anti_examples(body),
    10: lambda md, fm, body, st: score_dim10_taste(body),
    11: lambda md, fm, body, st: score_dim11_insight(md, body, st),
}


MANUAL_DIMS = {8, 10}


def main():
    parser = argparse.ArgumentParser(description="盘古开天 rubric 自动评分（结构/材料维度；D8/D10 需人工）")
    parser.add_argument("md_path", help="SKILL.md 路径")
    parser.add_argument("--type", choices=["auto", "output", "text"], default="auto",
                        help="output=产出型（D6 围栏路径计入/D11 查范例集）；"
                             "text=文本型（D6 围栏模板路径不计/D11 查进化三件套）；"
                             "auto=范例资产优先，其次正文元技能特征")
    parser.add_argument("--json", action="store_true", help="stdout 只输出 JSON")
    args = parser.parse_args()

    md_path = Path(args.md_path)
    if not md_path.exists():
        print(f"❌ 文件不存在: {md_path}", file=sys.stderr)
        sys.exit(1)

    content = md_path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(content)
    skill_type = detect_skill_type(md_path, body, args.type)

    results = {}
    total_weighted = 0.0
    total_weight = 0

    for dim_num in range(1, 12):
        name, weight = WEIGHTS[dim_num]
        fn = SCORE_FUNCS[dim_num]
        try:
            score, reason = fn(md_path, fm, body, skill_type)
        except Exception as exc:
            score, reason = None, f"检查器异常: {exc}"

        manual = dim_num in MANUAL_DIMS or score is None
        if manual:
            results[dim_num] = {
                "name": name, "weight": weight,
                "score": None, "weighted": None,
                "note": reason, "needs_human": True,
            }
            continue

        weighted = score * weight / 10
        total_weighted += weighted
        total_weight += weight
        entry = {
            "name": name, "weight": weight,
            "score": score, "weighted": round(weighted, 1),
            "note": reason, "needs_human": False,
        }
        if dim_num == 11:
            entry["coverage_only"] = True
        results[dim_num] = entry

    manual_max = sum(WEIGHTS[dim][1] for dim in MANUAL_DIMS)
    auto_max = 100 - manual_max
    quality = output_quality_evidence(md_path, body)
    red_count, red_hits = scan_runtime_neutrality(body, fm)
    gate_pass = red_count == 0

    output = {
        "skill": md_path.name,
        "skill_type": skill_type,
        "auto_score": round(total_weighted, 1),
        "auto_max": auto_max,
        "manual_weight": manual_max,
        "manual_dimensions": sorted(MANUAL_DIMS),
        "dim11_coverage_only": True,
        "runtime_neutrality": {
            "red_count": red_count,
            "gate_pass": gate_pass,
            "hits": red_hits,
        },
        "output_quality_evidence": quality,
        "dimensions": {str(k): v for k, v in results.items()},
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
        sys.exit(0)

    print(f"rubric 评分: {md_path.name}（type={skill_type}）")
    print("=" * 60)
    for dim_num in range(1, 12):
        name, weight = WEIGHTS[dim_num]
        entry = results[dim_num]
        if entry["needs_human"]:
            print(f"  D{dim_num:>2} {name:<16} 需人工判定 (权重{weight})")
            print(f"      └─ {entry['note']}")
            continue
        print(f"  D{dim_num:>2} {name:<16} {entry['score']}/10 × {weight} = {entry['weighted']:.1f}")
        print(f"      └─ {entry['note']}")

    print("=" * 60)
    print(f"  自动结构/材料分: {total_weighted:.1f} / {auto_max}")
    print(f"  人工分剩余: {manual_max}（D8 实测 19 + D10 品味 6，均不得用关键词替代）")
    print("  该分数只用于 triage；不是能力分，也不是发布依据。")
    print(
        "  产出质量证据: art-direction "
        + ("✅" if quality["art_direction"] else "✗")
        + " | showcase "
        + ("✅" if quality["showcase"] else "✗")
    )
    if quality["visual_skill"] and not quality["art_direction"]:
        print("      ⚠ 观感类 skill 缺 references/art-direction.md（参照物/工艺参数/差距清单）——产出质量未验证")
    if quality["visual_skill"] and not quality["showcase"]:
        print("      ⚠ 缺 assets/showcase/ 代表作——盲评没有校准锚点")

    print(f"  运行时中立: {'✅ 无红灯' if gate_pass else f'⚠ {red_count} 处疑似红灯（需人工判别假阳性）'}")
    for hit in red_hits[:3]:
        print(f"      └─ {hit}")

    sys.exit(0)


if __name__ == "__main__":
    main()
