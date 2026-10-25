#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""脚手架回归：新技能必须自带可执行清单，且占位实现不能变绿。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERIFY = ROOT / "scripts" / "verify_skill.py"


class ScaffoldContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "demo-skill"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "scaffold.py"),
             str(self.target), "--name", "demo-skill"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_generates_verification_manifest_and_failing_placeholder(self):
        manifest = json.loads((self.target / "tests" / "verification.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], 1)
        self.assertEqual({suite["id"] for suite in manifest["suites"]},
                         {"behavior-placeholder", "failure-injection"})
        injection = next(s for s in manifest["suites"] if s["kind"] == "failure_injection")
        self.assertGreaterEqual(len(injection["categories"]), 2)

        placeholder = subprocess.run(
            [sys.executable, str(self.target / "tests" / "test_placeholder.py")],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(placeholder.returncode, 1)
        self.assertIn("NOT_IMPLEMENTED", placeholder.stderr)

    def test_promise_table_binds_test_ids_without_self_claims(self):
        text = (self.target / "references" / "promise-table.md").read_text(encoding="utf-8")
        self.assertIn("evidence/verification.json#behavior-placeholder", text)
        self.assertIn("evidence/verification.json#failure-injection", text)
        self.assertNotIn("已测试", text)
        self.assertNotIn("验证通过", text)

    def test_scaffold_is_not_delivery_ready(self):
        proc = subprocess.run(
            [sys.executable, str(VERIFY), str(self.target), "--type", "text", "--execute", "--json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        data = json.loads(proc.stdout)
        self.assertFalse(data["delivery_ready"])
        self.assertFalse(data["pass"])
        self.assertEqual(data["behavior_summary"]["pass"], 0)


if __name__ == "__main__":
    unittest.main()
