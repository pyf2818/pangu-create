#!/usr/bin/env python3
"""
盘古开天 进化趋势分析：读 results.tsv，输出结构化趋势报告。

设计目标:
  - 让「进化循环」从流水账变成可读的趋势——worse 集中在哪个维度？最近是改善还是恶化？
  - 为定期自审（每月一次）提供数据基础：高频 worse 维度 = 架构级短板
  - 为 evolution-feedback.md 提供回填素材：从 worse 记录提炼教训卡片

用法:
    python3 analyze_evolution.py <results.tsv 路径> [--json] [--months N]

输出:
  - 状态分布（worse/update/keep 计数 + 占比）
  - 维度频次排名（worse 记录按 dimension 字段聚合）
  - 时间趋势（按月聚合 worse 数）
  - 技能分布（每个 skill 的 worse 计数）
  - 高频痛点（worse 维度 × skill 交叉表）
  - 改进建议（基于数据自动生成）
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


CANONICAL_9 = ["timestamp", "commit", "skill", "old_score", "new_score",
              "status", "dimension", "note", "eval_mode"]
CANONICAL_10 = CANONICAL_9 + ["evidence"]
ALIASES = {
    "ts": "timestamp",
    "time": "timestamp",
    "verdict": "status",
    "notes": "note",
    "mode": "eval_mode",
    "session": "session",
    "phase": "phase",
    "check": "check",
    "expected": "expected",
    "observed": "observed",
}


def parse_tsv(path: Path):
    """解析进化账本，兼容注释头、无表头 9/10 列、逗号/Tab、旧 9 列。

    返回 (records, error, warnings)。绝不静默丢行：列数不足/超出、缺 status
    都会进入 warnings，由调用方展示。
    """
    warnings = []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return [], f"文件不存在: {path}", warnings
    except OSError as exc:
        return [], f"读取失败: {exc}", warnings

    lines = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        lines.append((line_no, line))
    if not lines:
        return [], "无有效数据行（全部为空或注释）", warnings

    first_no, first_line = lines[0]
    delimiter = "	" if first_line.count("	") >= first_line.count(",") else ","
    parsed = []
    for line_no, line in lines:
        try:
            cells = next(csv.reader([line], delimiter=delimiter))
        except csv.Error as exc:
            warnings.append(f"第 {line_no} 行无法解析：{exc}")
            continue
        parsed.append((line_no, [cell.strip() for cell in cells]))
    if not parsed:
        return [], "没有可解析的数据行", warnings

    first_cells = parsed[0][1]
    first_key = first_cells[0].lower() if first_cells else ""
    looks_header = first_key in {"timestamp", "ts", "time", "phase", "session"} or any(
        cell.lower() in {"status", "verdict", "skill"} for cell in first_cells
    )
    if looks_header:
        header = [ALIASES.get(cell.lower(), cell.lower()) for cell in first_cells]
        data_rows = parsed[1:]
    else:
        width = len(first_cells)
        if width == 9:
            header = CANONICAL_9[:]
        elif width >= 10:
            header = CANONICAL_10[:]
        else:
            return [], f"无表头且只有 {width} 列，无法识别（需 9/10 列）", warnings
        data_rows = parsed
        warnings.append(f"未发现表头；按 {len(header)} 列规范表头解析（首行 L{first_no} 视为数据）")

    if "status" not in header:
        return [], f"表头缺 status/verdict 列：{header}", warnings

    records = []
    for line_no, cells in data_rows:
        if len(cells) < len(header):
            warnings.append(f"L{line_no} 列数 {len(cells)} < {len(header)}，缺列按空值保留")
            cells = cells + [""] * (len(header) - len(cells))
        elif len(cells) > len(header):
            extra = cells[len(header) - 1:]
            cells = cells[:len(header) - 1] + [delimiter.join(extra)]
            warnings.append(f"L{line_no} 列数超出，多出的 {len(extra) - 1} 段并入最后一列")
        record = dict(zip(header, cells))
        record["_line"] = line_no
        records.append(record)

    if not records:
        return [], "只有表头，没有数据行", warnings
    return records, None, warnings


def analyze(records, months_limit=None, parse_warnings=None):
    """对记录做统计分析；只报告发生率，不从缺失数据推断「健康」。"""
    if not records:
        return None, "无记录"

    def field(record, key, default="未标注"):
        value = record.get(key, default)
        return value.strip() if isinstance(value, str) else default

    warnings = list(parse_warnings or [])
    status_counts = Counter(field(r, "status", "未标注") or "未标注" for r in records)
    worse_records = [r for r in records if field(r, "status", "").lower() == "worse"]
    dim_counts = Counter(field(r, "dimension", "未标注") or "未标注" for r in worse_records)

    monthly = defaultdict(int)
    invalid_timestamps = 0
    for r in worse_records:
        ts = field(r, "timestamp", "")
        try:
            monthly[datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m")] += 1
        except ValueError:
            invalid_timestamps += 1
            monthly["未知"] += 1
    monthly_sorted = dict(sorted(monthly.items()))
    if months_limit and len(monthly_sorted) > months_limit:
        monthly_sorted = dict(list(monthly_sorted.items())[-months_limit:])

    skill_worse = Counter(field(r, "skill", "未标注") or "未标注" for r in worse_records)
    cross = defaultdict(lambda: defaultdict(int))
    for r in worse_records:
        cross[field(r, "skill", "未标注") or "未标注"][field(r, "dimension", "未标注") or "未标注"] += 1

    eval_modes = Counter(field(r, "eval_mode", "未标注") or "未标注" for r in records)
    full_tests = eval_modes.get("full_test", 0)
    dry_runs = eval_modes.get("dry_run", 0)
    paired = sum(count for mode, count in eval_modes.items() if mode.startswith("paired"))

    missing_status = status_counts.get("未标注", 0)
    if missing_status:
        warnings.append(f"{missing_status} 条记录缺 status/verdict")
    if invalid_timestamps:
        warnings.append(f"{invalid_timestamps} 条 worse 记录时间戳不可解析")

    has_evidence_col = any("evidence" in r for r in records)
    evidence_missing = sum(1 for r in records if field(r, "evidence", "").strip() in {"", "-"})
    if not has_evidence_col:
        warnings.append("账本没有 evidence 列；所有结论都无法回溯到工件")
    elif evidence_missing:
        warnings.append(f"{evidence_missing}/{len(records)} 条记录 evidence 为空或 '-'")

    recent_worse = []
    for r in worse_records[-3:]:
        note = field(r, "note", "").strip()
        recent_worse.append({
            "timestamp": field(r, "timestamp", ""),
            "dimension": field(r, "dimension", ""),
            "note": note[:100] + "..." if len(note) > 100 else note,
        })

    suggestions = []
    if dim_counts:
        top_dim, top_count = dim_counts.most_common(1)[0]
        if top_count >= 2:
            suggestions.append(
                f"高频痛点维度「{top_dim}」出现 {top_count} 次 worse——优先回 F2/F3 查设计，不做表层修补。"
            )

    check_dims = [d for d in dim_counts if "检查点" in d or "checkpoint" in d.lower()]
    if check_dims:
        suggestions.append(f"检查点相关 worse: {check_dims}；核对记录中的用户交互/代答声明，代答不算通过。")

    taste_dims = [d for d in dim_counts if any(k in d for k in ("观感", "品味", "taste", "审美"))]
    if taste_dims:
        suggestions.append(f"观感/品味 worse: {taste_dims}；需盲评与参照物，关键词检查不能替代。")

    intent_dims = [d for d in dim_counts if any(k in d for k in ("意图", "显影", "理解"))]
    if intent_dims:
        suggestions.append(f"意图显影 worse: {intent_dims}；先索要参照物并留下意图档案。")

    if full_tests == 0:
        suggestions.append(
            f"没有任何 full_test 记录（dry_run={dry_runs}）——D8 实测表现不可打分，"
            "本轮不得宣称能力提升，也不得用结构分替代。"
        )
    elif dry_runs > full_tests:
        suggestions.append(f"dry_run({dry_runs}) > full_test({full_tests})，评估覆盖率不足，结论只作线索。")

    if len(monthly_sorted) >= 2:
        months = list(monthly_sorted.keys())
        first_count, last_count = monthly_sorted[months[0]], monthly_sorted[months[-1]]
        if last_count > first_count:
            suggestions.append(
                f"worse 数上升: {months[0]}({first_count}) → {months[-1]}({last_count})；"
                "考虑 E2.5 探索性重写而不是继续修补。"
            )
        elif last_count < first_count:
            suggestions.append(
                f"worse 数下降: {months[0]}({first_count}) → {months[-1]}({last_count})；"
                "下降只说明负面信号变少，不等于质量已被证明。"
            )

    repeated = []
    for skill, dims in cross.items():
        for dim, count in dims.items():
            if count >= 2:
                repeated.append(f"「{skill}」的「{dim}」出现 {count} 次 worse")
    if repeated:
        suggestions.append(
            f"重复 worse: {', '.join(repeated)}；同坑第二次出现应机器化拦截，而非继续加文档。"
        )

    data_quality = {
        "records": len(records),
        "has_evidence_column": has_evidence_col,
        "evidence_missing": evidence_missing,
        "full_test": full_tests,
        "dry_run": dry_runs,
        "paired": paired,
        "missing_status": missing_status,
        "invalid_timestamps": invalid_timestamps,
        "warnings": warnings,
    }
    return {
        "total_records": len(records),
        "total_worse": len(worse_records),
        "worse_incidence": round(len(worse_records) / len(records), 4),
        "status_distribution": dict(status_counts),
        "dim_frequency": dict(dim_counts.most_common()),
        "monthly_trend": monthly_sorted,
        "skill_worse": dict(skill_worse.most_common()),
        "eval_modes": dict(eval_modes),
        "data_quality": data_quality,
        "recent_worse": recent_worse,
        "cross_table": {skill: dict(dims) for skill, dims in cross.items()},
        "suggestions": suggestions,
    }, None


def format_report(analysis, source_path):
    """将分析结果格式化为可读文本。"""
    if analysis is None:
        return f"❌ 无法分析: {source_path}"

    lines = []
    lines.append(f"进化趋势分析: {source_path}")
    lines.append("=" * 60)
    lines.append("")

    # 概览
    lines.append(f"总记录: {analysis['total_records']} 条")
    lines.append(f"worse 记录: {analysis['total_worse']} 条（发生率 {analysis['worse_incidence']:.1%}）")
    lines.append("")

    lines.append("## 数据质量")
    quality = analysis["data_quality"]
    lines.append(
        f"  full_test={quality['full_test']} | dry_run={quality['dry_run']} | paired={quality['paired']}"
        f" | evidence 缺失={quality['evidence_missing']}/{quality['records']}"
    )
    if quality["warnings"]:
        for warning in quality["warnings"]:
            lines.append(f"  ! {warning}")
    else:
        lines.append("  无解析警告（仍不代表记录内容真实）")
    lines.append("")

    # 状态分布
    lines.append("## 状态分布")
    dist = analysis["status_distribution"]
    for status, count in sorted(dist.items(), key=lambda x: -x[1]):
        pct = count / analysis["total_records"] * 100 if analysis["total_records"] else 0
        bar = "█" * int(pct / 5)
        lines.append(f"  {status:<12} {count:>3} ({pct:.0f}%) {bar}")
    lines.append("")

    # 维度频次
    lines.append("## worse 维度频次排名")
    dims = analysis["dim_frequency"]
    if dims:
        for dim, count in list(dims.items())[:10]:
            lines.append(f"  {count:>3}  {dim}")
    else:
        lines.append("  （无 worse 记录）")
    lines.append("")

    # 时间趋势
    lines.append("## worse 时间趋势")
    monthly = analysis["monthly_trend"]
    if monthly:
        for month, count in monthly.items():
            bar = "█" * count
            lines.append(f"  {month}  {count:>3}  {bar}")
    else:
        lines.append("  （无时间数据）")
    lines.append("")

    # 技能分布
    lines.append("## skill worse 分布")
    skills = analysis["skill_worse"]
    if skills:
        for skill, count in skills.items():
            lines.append(f"  {count:>3}  {skill}")
    else:
        lines.append("  （无 skill worse 记录）")
    lines.append("")

    # 交叉表
    lines.append("## 高频痛点交叉表（skill × dimension）")
    cross = analysis["cross_table"]
    if cross:
        for skill, dims in cross.items():
            lines.append(f"  {skill}:")
            for dim, count in dims.items():
                lines.append(f"    {count}  {dim}")
    else:
        lines.append("  （无交叉数据）")
    lines.append("")

    # 评估模式
    lines.append("## 评估模式分布")
    modes = analysis["eval_modes"]
    if modes:
        for mode, count in modes.items():
            lines.append(f"  {mode:<20} {count:>3}")
    else:
        lines.append("  （无评估记录）")
    lines.append("")

    # 最近 worse
    lines.append("## 最近 worse 摘要")
    recent = analysis["recent_worse"]
    if recent:
        for item in recent:
            lines.append(f"  [{item['timestamp']}] {item['dimension']}")
            lines.append(f"    └─ {item['note']}")
    else:
        lines.append("  （无 worse 记录）")
    lines.append("")

    # 改进建议
    lines.append("## 改进建议（基于数据自动生成）")
    suggestions = analysis["suggestions"]
    if suggestions:
        for i, s in enumerate(suggestions, 1):
            lines.append(f"  {i}. {s}")
    else:
        lines.append("  暂无自动建议（数据不足以生成）")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="盘古开天 进化趋势分析")
    parser.add_argument("tsv_path", help="results.tsv 路径")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--months", type=int, default=None, help="限制月份数（默认全部）")
    args = parser.parse_args()

    tsv_path = Path(args.tsv_path)
    records, err, warnings = parse_tsv(tsv_path)
    if err:
        print(f"❌ {err}", file=sys.stderr)
        sys.exit(1)

    analysis, err2 = analyze(records, args.months, warnings)
    if err2:
        print(f"❌ {err2}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
    else:
        print(format_report(analysis, tsv_path))

    sys.exit(0)


if __name__ == "__main__":
    main()
