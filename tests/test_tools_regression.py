#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具回归：评分器与账本分析器不再用关键词/缺失数据冒充证据。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_evolution  # noqa: E402
import rubric_score  # noqa: E402
import verify_skill  # noqa: E402


class EvidencePortabilityTest(unittest.TestCase):
    def test_line_endings_do_not_change_source_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SKILL.md").write_bytes(b"# demo\nbody\n")
            (root / "scripts").mkdir()
            (root / "scripts" / "run.py").write_bytes(b"print(1)\n")
            before, count = verify_skill.source_fingerprint(root)
            (root / "SKILL.md").write_bytes(b"# demo\r\nbody\r\n")
            (root / "scripts" / "run.py").write_bytes(b"print(1)\r\n")
            after, count_after = verify_skill.source_fingerprint(root)
            self.assertEqual(before, after)
            self.assertEqual(count, count_after)

    def test_line_endings_do_not_change_contract_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            contract = root / "tests" / "verification.json"
            contract.write_bytes(b'{"version": 1}\n')
            before = verify_skill.contract_digest(root)
            contract.write_bytes(b'{"version": 1}\r\n')
            after = verify_skill.contract_digest(root)
            self.assertEqual(before, after)

    def test_sorting_order_is_deterministic_across_platforms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SKILL.md").write_text("# demo\n", encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets" / "banner.svg").write_text("<svg></svg>\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text("# changelog\n", encoding="utf-8")
            (root / "scripts").mkdir()
            (root / "scripts" / "run.py").write_text("print(1)\n", encoding="utf-8")
            fp, count = verify_skill.source_fingerprint(root)
            self.assertEqual(count, 4)
            # 验证无论 Windows 还是 POSIX，文件遍历都统一按照 POSIX 字符串序排序
            files = sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix())
            posix_rel = [p.relative_to(root).as_posix() for p in files]
            self.assertEqual(posix_rel, ["CHANGELOG.md", "SKILL.md", "assets/banner.svg", "scripts/run.py"])


class RubricTypeDetectionTest(unittest.TestCase):
    """分型探测：元技能自述（frontmatter）必须压过 showcase 资产存在（v1.4.0 实测坑）。"""

    def write_skill(self, root: Path, frontmatter: str, body: str, showcase: bool = False):
        root.mkdir(parents=True, exist_ok=True)
        (root / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
        if showcase:
            (root / "assets" / "showcase").mkdir(parents=True, exist_ok=True)
            (root / "assets" / "showcase" / "shot.jpg").write_bytes(b"\xff\xd8fake")

    def test_meta_declaration_outranks_showcase_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "meta"
            self.write_skill(root,
                             "name: meta-skill\ndescription: |\n  万物皆可成技能：把任何领域锻造成 Agent Skill。",
                             "# 正文\n")
            self.assertEqual(rubric_score.detect_skill_type(root / "SKILL.md", "# 正文\n"), "text")

    def test_output_skill_with_corpus_stays_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "visual"
            self.write_skill(root,
                             "name: visual-skill\ndescription: |\n  帮用户做 3D 网页。",
                             "# 正文\n做 3D 页面。", showcase=True)
            self.assertEqual(rubric_score.detect_skill_type(root / "SKILL.md", "# 正文\n做 3D 页面。"), "output")

    def test_body_hint_without_corpus_is_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bodymeta"
            self.write_skill(root,
                             "name: plain\ndescription: |\n  一个工具。",
                             "# 正文\n本 skill 提供锻造管线。")
            self.assertEqual(rubric_score.detect_skill_type(root / "SKILL.md", "# 正文\n本 skill 提供锻造管线。"), "text")

    def test_no_signal_defaults_to_output_strictly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bare"
            self.write_skill(root, "name: bare\ndescription: |\n  做事。", "# 正文\n做事。")
            self.assertEqual(rubric_score.detect_skill_type(root / "SKILL.md", "# 正文\n做事。"), "output")


class RubricHonestyTest(unittest.TestCase):
    def test_json_is_pure_and_manual_dimensions_are_not_scored(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "rubric_score.py"),
             str(ROOT / "SKILL.md"), "--json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)  # 旧版这里会在 JSON 前打印人类可读头
        self.assertEqual(data["auto_max"], 75)
        self.assertEqual(data["manual_dimensions"], [8, 10])
        self.assertTrue(data["dimensions"]["10"]["needs_human"])
        self.assertTrue(data["dimensions"]["11"]["coverage_only"])

    def test_taste_keywords_do_not_earn_a_score(self):
        score, reason = rubric_score.score_dim10_taste("铁律 品味 反模式 示例 配方")
        self.assertIsNone(score, reason)
        self.assertIn("人工", reason)

    def test_platitude_failure_rows_do_not_earn_ten(self):
        platitude_body = (
            "## 失败处理\n"
            "| 触发条件 | 一线修复 | 仍失败兜底 |\n"
            "|---|---|---|\n"
            "| 网络请求失败 | 重试一次 | 提示用户检查网络并报错 |\n"
            "| 接口调用超时 | 重新尝试请求 | 告知用户稍后再试 |\n"
            "| 返回数据异常 | 检查网络连接 | 手动处理并提示用户 |\n"
        )
        score, reason = rubric_score.score_dim3_failure(platitude_body)
        self.assertLessEqual(score, 7, f"套话三段式不应拿满分: {score} ({reason})")
        self.assertIn("套话", reason)

    def test_concrete_failure_rows_earn_ten(self):
        concrete_body = (
            "## 失败降级（如果解析失败则触发三段式恢复）\n"
            "| 触发条件 | 一线修复 | 仍失败兜底 |\n"
            "|---|---|---|\n"
            "| CSV 含 GBK 或 BOM 解码失败 | 自动回退 utf-8-sig -> gb18030 解码 | 写入 fallback.html 诊断页并退出码 1 |\n"
            "| vendor/chart.umd.js 加载失败 | 切换内置 SVG 降级渲染器 | 输出 JSON 错误码 2，禁止裸 Traceback |\n"
            "| 数据行数 > 10000 渲染失败 | 关闭入场动画（duration=0）并按时间桶聚合 | 仅渲染前 5000 行并在页眉横幅明示采样率 |\n"
            "| 数值列全为文本解析失败 | 跳过数值聚合，切换频次统计条形图 | 生成 fallback.html 说明缺失列 |\n"
            "| 输出目录写入失败 | 自动回退至系统临时目录 tempfile | 打印完整目标路径并以 exit 2 退出 |\n"
        )
        score, reason = rubric_score.score_dim3_failure(concrete_body)
        self.assertEqual(score, 10, f"具体机制恢复分支应拿 10 分: {score} ({reason})")


class LedgerParsingTest(unittest.TestCase):
    def write(self, text):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".tsv", delete=False, encoding="utf-8", newline=""
        )
        handle.write(text)
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        return Path(handle.name)

    def test_headerless_nine_column_file_is_not_empty(self):
        path = self.write(
            "2026-10-14T00:00\tbaseline\tdemo\t-\t79.3\tkeep\tall\t初始\t-\n"
            "2026-10-16T12:00\tabc123\tdemo\t79.3\t86.3\tkeep\tD8\t修复\tpaired-self\n"
        )
        records, error, warnings = analyze_evolution.parse_tsv(path)
        self.assertIsNone(error)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["status"], "keep")
        self.assertTrue(any("未发现表头" in warning for warning in warnings))

    def test_comment_and_comma_header_is_parsed(self):
        path = self.write(
            "# comment header\n"
            "# another\n"
            "timestamp,commit,skill,old_score,new_score,status,dimension,note,eval_mode,evidence\n"
            "2026-10-01T00:00,abc,demo,-,-,worse,D10,\"含,逗号\",paired,logs/a.json\n"
        )
        records, error, warnings = analyze_evolution.parse_tsv(path)
        self.assertIsNone(error)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["note"], "含,逗号")
        self.assertEqual(records[0]["evidence"], "logs/a.json")
        self.assertEqual(warnings, [])

    def test_short_row_is_padded_and_warned(self):
        path = self.write(
            "timestamp\tstatus\tskill\n"
            "2026-10-01T00:00\tworse\tdemo\n"
            "2026-10-02T00:00\tkeep\n"
        )
        records, error, warnings = analyze_evolution.parse_tsv(path)
        self.assertIsNone(error)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["skill"], "")
        self.assertTrue(any("列数" in warning for warning in warnings))

    def test_unrecognizable_width_is_an_error(self):
        path = self.write("a,b,c\n1,2,3\n")
        records, error, warnings = analyze_evolution.parse_tsv(path)
        self.assertEqual(records, [])
        self.assertTrue(error)

    def test_normalize_tsv_repairs_legacy_and_extra_tabs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tsv = root / "results.tsv"
            tsv.write_text(
                "2026-10-14T00:00\tbaseline\tdemo\t-\t79.3\tkeep\tall\t初始\t-\n"
                "2026-10-16T12:00\tabc123\tdemo\t79.3\t86.3\tkeep\tD8\t修复说明\t带额外制表符\tpaired\tlogs/e.json\n",
                encoding="utf-8",
            )
            res = analyze_evolution.normalize_tsv(tsv)
            self.assertTrue(res["changed"])
            self.assertEqual(res["rows"], 2)
            self.assertTrue(Path(res["backup"]).is_file())
            records, error, warnings = analyze_evolution.parse_tsv(tsv)
            self.assertIsNone(error)
            self.assertEqual(warnings, [])
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["evidence"], "-")
            self.assertIn("logs/e.json", records[1]["eval_mode"])


class AnalyzerEvidenceTest(unittest.TestCase):
    def analyze(self, records):
        result, error = analyze_evolution.analyze(records, parse_warnings=[])
        self.assertIsNone(error)
        return result

    def test_zero_full_test_forbids_quality_claim(self):
        result = self.analyze([
            {"status": "keep", "eval_mode": "dry_run", "timestamp": "2026-10-01T00:00"},
            {"status": "worse", "eval_mode": "dry_run", "timestamp": "2026-10-02T00:00"},
        ])
        text = " ".join(result["suggestions"])
        self.assertIn("full_test", text)
        self.assertIn("不得宣称", text)
        self.assertNotIn("健康", text)
        self.assertEqual(result["data_quality"]["full_test"], 0)
        self.assertEqual(result["data_quality"]["dry_run"], 2)

    def test_decline_is_not_called_healthy(self):
        result = self.analyze([
            {"status": "worse", "eval_mode": "full_test", "timestamp": "2026-01-01T00:00", "skill": "demo"},
            {"status": "worse", "eval_mode": "full_test", "timestamp": "2026-01-02T00:00", "skill": "demo"},
            {"status": "worse", "eval_mode": "full_test", "timestamp": "2026-02-01T00:00", "skill": "demo"},
        ])
        text = " ".join(result["suggestions"])
        self.assertIn("不等于质量已被证明", text)
        self.assertNotIn("健康", text)

    def test_eval_modes_count_all_records_not_only_worse(self):
        result = self.analyze([
            {"status": "keep", "eval_mode": "full_test"},
            {"status": "worse", "eval_mode": "paired"},
            {"status": "baseline", "eval_mode": "dry_run"},
        ])
        self.assertEqual(result["eval_modes"]["full_test"], 1)
        self.assertEqual(result["eval_modes"]["paired"], 1)
        self.assertEqual(result["data_quality"]["paired"], 1)


if __name__ == "__main__":
    unittest.main()
