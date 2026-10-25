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
