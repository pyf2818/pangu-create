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


def parse_tsv(path: Path):
    """解析 results.tsv，返回记录列表（dict）。"""
    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                records.append(row)
    except FileNotFoundError:
        return [], f"文件不存在: {path}"
    except Exception as e:
        return [], f"解析失败: {e}"
    return records, None


def analyze(records, months_limit=None):
    """对记录做统计分析，返回分析结果 dict。"""
    if not records:
        return None, "无记录"

    # 1. 状态分布
    status_counts = Counter(r.get("status", "").strip() for r in records)

    # 2. 维度频次（仅 worse 记录）
    worse_records = [r for r in records if r.get("status", "").strip() == "worse"]
    dim_counts = Counter(r.get("dimension", "未标注").strip() for r in worse_records)

    # 3. 时间趋势（按月聚合 worse）
    monthly = defaultdict(int)
    for r in worse_records:
        ts = r.get("timestamp", "").strip()
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            month_key = dt.strftime("%Y-%m")
        except Exception:
            month_key = "未知"
        monthly[month_key] += 1

    # 按时间排序
    monthly_sorted = dict(sorted(monthly.items()))

    # 限制月份数
    if months_limit and len(monthly_sorted) > months_limit:
        items = list(monthly_sorted.items())[-months_limit:]
        monthly_sorted = dict(items)

    # 4. 技能分布（每个 skill 的 worse 计数）
    skill_worse = Counter(r.get("skill", "未标注").strip() for r in worse_records)

    # 5. 高频痛点交叉表（worse 维度 × skill）
    cross = defaultdict(lambda: defaultdict(int))
    for r in worse_records:
        skill = r.get("skill", "未标注").strip()
        dim = r.get("dimension", "未标注").strip()
        cross[skill][dim] += 1

    # 6. 评估模式分布
    eval_modes = Counter(r.get("eval_mode", "未标注").strip() for r in worse_records)

    # 7. 最近 worse 的 note 摘要（最近 3 条）
    recent_worse = []
    for r in worse_records[-3:]:
        note = r.get("note", "").strip()
        # 截断过长 note
        if len(note) > 100:
            note = note[:100] + "..."
        recent_worse.append({
            "timestamp": r.get("timestamp", ""),
            "dimension": r.get("dimension", ""),
            "note": note,
        })

    # 8. 改进建议（基于数据自动生成）
    suggestions = []

    # 建议1: 高频维度
    if dim_counts:
        top_dim, top_count = dim_counts.most_common(1)[0]
        if top_count >= 2:
            suggestions.append(
                f"🔴 高频痛点维度: 「{top_dim}」出现 {top_count} 次 worse "
                f"——这大概率是架构级短板，建议优先审视 盘古开天 自身设计中"
                f"与该维度相关的部分（铁律/工作流/检查点），而非只做表层修补。"
            )

    # 建议2: 检查点相关 worse
    check_dims = [d for d in dim_counts if "检查点" in d or "checkpoint" in d.lower()]
    if check_dims:
        suggestions.append(
            f"⚠️ 检查点相关问题: {check_dims} —— CHECKPOINT 被跳过是已知高危模式，"
            f"确认每次锻造都有用户交互记录（results.tsv 的 eval_mode 含 paired_worse_user 说明是用户抓包）。"
        )

    # 建议3: 观感/品味相关 worse
    taste_dims = [d for d in dim_counts if any(k in d for k in ("观感", "品味", "taste", "审美", "观感维度"))]
    if taste_dims:
        suggestions.append(
            f"⚠️ 观感/品味问题: {taste_dims} —— 产出型 skill 必须有配方库 + 惊喜线验证，"
            f"确认 F3 构建阶段强制检查配方库捆绑，F4 出厂测试跑惊喜线（≥2 个进阶效果）。"
        )

    # 建议4: 意图显影相关 worse
    intent_dims = [d for d in dim_counts if "意图" in d or "显影" in d or "理解" in d]
    if intent_dims:
        suggestions.append(
            f"⚠️ 意图显影问题: {intent_dims} —— 确认 Phase 0.5 第 1 步「索要参照物」是强制动作"
            f"（一图胜十问），L1/L2 级别必须走三拍全走（方向卡 + 探针 + 定稿）。"
        )

    # 建议5: 时间趋势
    if len(monthly_sorted) >= 2:
        months = list(monthly_sorted.keys())
        first_count = monthly_sorted[months[0]]
        last_count = monthly_sorted[months[-1]]
        if last_count > first_count:
            suggestions.append(
                f"📈 worse 趋势上升: {months[0]}({first_count}) → {months[-1]}({last_count}) "
                f"—— worse 在增加说明问题在积累，可能需要一次探索性重写（E2.5）而非继续修补。"
            )
        elif last_count < first_count and last_count == 0:
            suggestions.append(
                f"📉 worse 趋势下降: {months[0]}({first_count}) → {months[-1]}({last_count}) "
                f"—— 近期无 worse，进化循环健康，可考虑将积累的成功模式固化进共享知识库。"
            )

    # 建议6: eval_mode 检查
    dry_runs = eval_modes.get("dry_run", 0)
    full_tests = eval_modes.get("full_test", 0)
    paired = eval_modes.get("paired", 0) + eval_modes.get("paired_worse_user", 0)
    if dry_runs > full_tests and full_tests == 0:
        suggestions.append(
            f"❌ 评估有效性警告: dry_run({dry_runs}) > full_test({full_tests})，"
            f"缺少真实测试题验证（rubric 维度 8 无法打分）。"
        )

    # 建议7: 重复 worse 检测（同一维度同一 skill 出现 ≥2 次 worse）
    repeated = []
    for skill, dims in cross.items():
        for dim, count in dims.items():
            if count >= 2:
                repeated.append(f"「{skill}」的「{dim}」出现 {count} 次 worse")
    if repeated:
        suggestions.append(
            f"🔴 重复 worse: {', '.join(repeated)} —— 同一问题两次 worse 按进化契约应触发"
            f"探索性重写（E2.5）或回炉 F2 内核提炼，不再做表层修补。"
        )

    return {
        "total_records": len(records),
        "total_worse": len(worse_records),
        "status_distribution": dict(status_counts),
        "dim_frequency": dict(dim_counts.most_common()),
        "monthly_trend": monthly_sorted,
        "skill_worse": dict(skill_worse.most_common()),
        "eval_modes": dict(eval_modes),
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
    lines.append(f"worse 记录: {analysis['total_worse']} 条")
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
    records, err = parse_tsv(tsv_path)
    if err:
        print(f"❌ {err}")
        sys.exit(1)

    analysis, err2 = analyze(records, args.months)
    if err2:
        print(f"❌ {err2}")
        sys.exit(1)

    if args.json:
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
    else:
        print(format_report(analysis, tsv_path))

    sys.exit(0)


if __name__ == "__main__":
    main()
