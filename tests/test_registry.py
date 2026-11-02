#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能群注册表回归：血统清单、反馈收件箱、孤儿检测、注册表同步。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import registry  # noqa: E402
import verify_skill  # noqa: E402

INBOX_HEADER = "timestamp\tseverity\tscene\tsymptom\tevidence\tstatus\n"


def make_skill(parent: Path, name: str, *, manifest: dict = None, inbox: str = None,
               results: str = None, evidence_hashes: bool = False):
    d = parent / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("# fake\n", encoding="utf-8")
    if manifest is not None:
        (d / "pangu.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    if inbox is not None:
        (d / "feedback").mkdir()
        (d / "feedback" / "inbox.tsv").write_text(inbox, encoding="utf-8")
    if results is not None:
        (d / "results.tsv").write_text(results, encoding="utf-8")
    if evidence_hashes:
        (d / "tests").mkdir()
        (d / "tests" / "verification.json").write_text('{"version": 1, "suites": []}', encoding="utf-8")
        fp, _ = verify_skill.source_fingerprint(d)
        cd = verify_skill.contract_digest(d)
        (d / "evidence").mkdir()
        (d / "evidence" / "verification.json").write_text(
            json.dumps({"source_sha256": fp, "contract_sha256": cd}), encoding="utf-8")
    return d


def good_manifest(name="alpha"):
    return {"schema": 1, "lineage_id": "pgn-1", "forged_by": "pangu-create",
            "pangu_version": "1.4.0", "name": name, "skill_type": "output",
            "domain": "测试域", "forge_date": "2026-10-31", "generation": 0,
            "depth": "L1", "adopted": False, "notes": ""}


class ScaffoldLineageTest(unittest.TestCase):
    def test_scaffold_writes_manifest_and_inbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "demo-skill"
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "scaffold.py"), str(target), "--name", "demo-skill"],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            manifest = json.loads((target / "pangu.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["forged_by"], "pangu-create")
            self.assertEqual(manifest["schema"], 1)
            self.assertTrue(manifest["lineage_id"].startswith("pgn-"))
            self.assertEqual(manifest["name"], "demo-skill")
            self.assertFalse(manifest["adopted"])
            inbox = (target / "feedback" / "inbox.tsv").read_text(encoding="utf-8")
            self.assertEqual(inbox, INBOX_HEADER)

    def test_adopt_only_adds_two_files_and_infers_forge_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "legacy"
            target.mkdir()
            skill_md = target / "SKILL.md"
            skill_md.write_text("# legacy 原文，不许被 adopt 改动\n", encoding="utf-8")
            (target / "results.tsv").write_text(
                "timestamp\tcommit\tskill\told_score\tnew_score\tstatus\tdimension\tnote\teval_mode\tevidence\n"
                "2026-10-02T01:05\t-\tlegacy\t-\t-\tbaseline\t-\t首行\tfull_test\t-\n",
                encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "scaffold.py"), str(target),
                 "--name", "legacy", "--adopt", "--domain", "测试域"],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            manifest = json.loads((target / "pangu.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["adopted"])
            self.assertEqual(manifest["forge_date"], "2026-10-02")  # 取账本首条日期
            self.assertEqual(skill_md.read_text(encoding="utf-8"), "# legacy 原文，不许被 adopt 改动\n")
            self.assertTrue((target / "feedback" / "inbox.tsv").exists())


class RegistryScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_find_registered_orphan_and_nesting(self):
        make_skill(self.root / "nest", "alpha", manifest=good_manifest())  # root/nest/alpha
        make_skill(self.root / "nest" / "alpha", "nested-inside")  # alpha 已是 skill，不再下钻
        make_skill(self.root, "orphan")
        registered, orphans = registry.find_skill_dirs(self.root, max_depth=3)
        names = {p.name for p in registered}
        self.assertEqual(names, {"alpha"})
        self.assertEqual([p.name for p in orphans], ["orphan"])

    def test_manifest_validation_errors(self):
        bad = good_manifest()
        bad["forged_by"] = "someone-else"
        bad["depth"] = "L9"
        d = make_skill(self.root, "bad", manifest=bad)
        manifest, errors = registry.load_manifest(d)
        self.assertIsNone(registry.load_manifest(self.root / "nope")[0])
        self.assertTrue(any("forged_by" in e for e in errors))
        self.assertTrue(any("depth" in e for e in errors))
        self.assertEqual(manifest["name"], "alpha")

    def test_inbox_counts_and_warnings(self):
        d = make_skill(self.root, "with-inbox", manifest=good_manifest(), inbox=(
            INBOX_HEADER
            + "2026-10-30\tblocker\t导出\t点击无反应\tshot.png\topen\n"
            + "2026-10-29\tminor\t配色\t偏差\t-\tresolved\n"
            + "2026-10-28\tmajor\t导入\t崩\tlog\topen\n"
            + "2026-10-27\t mega \t坏行\t?\t-\topen\n"))
        counts, warns = registry.read_inbox(d)
        self.assertEqual(counts["open"], 3)
        self.assertEqual(counts["blocker_major"], 2)
        self.assertEqual(counts["total"], 4)
        self.assertTrue(any("severity" in w for w in warns))
        missing, warns2 = registry.read_inbox(make_skill(self.root, "no-inbox", manifest=good_manifest()))
        self.assertIsNone(missing)
        self.assertTrue(any("feedback/inbox.tsv" in w for w in warns2))

    def test_receipt_fresh_stale_missing(self):
        fresh = make_skill(self.root, "fresh", manifest=good_manifest(), evidence_hashes=True)
        self.assertEqual(registry.receipt_status(fresh), "fresh")
        (fresh / "touched.py").write_text("x = 1\n", encoding="utf-8")  # 行为文件变了 → stale
        self.assertEqual(registry.receipt_status(fresh), "stale")
        self.assertEqual(registry.receipt_status(make_skill(self.root, "noreceipt", manifest=good_manifest())),
                         "missing")

    def test_sync_json_and_strict(self):
        make_skill(self.root, "alpha", manifest=good_manifest(), evidence_hashes=True, inbox=(
            INBOX_HEADER + "2026-10-30\tblocker\t导出\t无反应\tshot.png\topen\n"))
        make_skill(self.root, "orphan")
        reg_path = self.root / "registry.tsv"

        scan = subprocess.run(
            [sys.executable, str(SCRIPTS / "registry.py"), str(self.root), "--json"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(scan.returncode, 0, scan.stderr)
        data = json.loads(scan.stdout)
        self.assertEqual(data["summary"]["registered"], 1)
        self.assertEqual(data["summary"]["orphans"], 1)
        self.assertEqual(data["summary"]["blocker_major_open"], 1)

        strict = subprocess.run(
            [sys.executable, str(SCRIPTS / "registry.py"), str(self.root), "--strict"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(strict.returncode, 1)  # blocker open + 孤儿 → 巡检失败

        sync = subprocess.run(
            [sys.executable, str(SCRIPTS / "registry.py"), str(self.root), "--sync", "--registry", str(reg_path)],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(sync.returncode, 0, sync.stderr)
        lines = reg_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(lines[0].split("\t"), registry.REGISTRY_COLUMNS)
        self.assertEqual(len(lines), 3)  # 表头 + alpha + 孤儿行

        # 修掉反馈与孤儿后 strict 应转绿
        (self.root / "alpha" / "feedback" / "inbox.tsv").write_text(INBOX_HEADER, encoding="utf-8")
        subprocess.run([sys.executable, str(SCRIPTS / "scaffold.py"), str(self.root / "orphan"),
                        "--name", "orphan", "--adopt"], capture_output=True, text=True, encoding="utf-8")
        ok = subprocess.run(
            [sys.executable, str(SCRIPTS / "registry.py"), str(self.root), "--strict"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)

    def test_reseal_preserves_receipt_fingerprint_and_satisfies_require_seal(self):
        d = make_skill(self.root, "sealed", manifest=good_manifest("sealed"),
                       inbox=INBOX_HEADER, evidence_hashes=True)
        before_fp, _ = verify_skill.source_fingerprint(d)
        self.assertEqual(registry.receipt_status(d), "fresh")

        # 未盖章时 --strict --require-seal 应拦截
        fail_req = subprocess.run(
            [sys.executable, str(SCRIPTS / "registry.py"), str(self.root), "--strict", "--require-seal"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(fail_req.returncode, 1)

        # --reseal 盖章并补齐 log.py，且不弄脏行为回执指纹
        reseal = subprocess.run(
            [sys.executable, str(SCRIPTS / "scaffold.py"), str(d), "--reseal"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(reseal.returncode, 0, reseal.stderr)
        after_fp, _ = verify_skill.source_fingerprint(d)
        self.assertEqual(before_fp, after_fp, "--reseal 不得改变 verify_skill 源码指纹")
        self.assertEqual(registry.receipt_status(d), "fresh")
        self.assertEqual(registry.seal_status(d, registry.load_manifest(d)[0])[0], "ok")

        pass_req = subprocess.run(
            [sys.executable, str(SCRIPTS / "registry.py"), str(self.root), "--strict", "--require-seal"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(pass_req.returncode, 0, pass_req.stdout + pass_req.stderr)

        # 正文含行内 `<!-- pangu:seal -->` 字面量时，再次 --reseal 绝不能吞正文
        import pangu_seal
        prose = "# 标题\n\n正文提及 `<!-- pangu:seal -->` 行内说明。\n\n## 章节\n内容保留。\n"
        block = pangu_seal.render_seal("pgn-test", "1.5.0")
        sealed_once = pangu_seal.apply_seal(prose, block)
        sealed_twice = pangu_seal.apply_seal(sealed_once, block)
        self.assertIn("## 章节\n内容保留。", sealed_twice)
        self.assertEqual(pangu_seal.strip_seal_bytes(sealed_twice.encode("utf-8")).decode("utf-8"), prose)

    def test_feedback_log_cli_and_minor_batch_trigger(self):
        target = self.root / "cli-skill"
        subprocess.run(
            [sys.executable, str(SCRIPTS / "scaffold.py"), str(target), "--name", "cli-skill"],
            check=True, capture_output=True, text=True, encoding="utf-8")
        log_py = target / "feedback" / "log.py"

        # 写入 3 条 minor（含制表符/换行污染测试），第 3 条应触发强制进化
        for idx in range(1, 4):
            res = subprocess.run(
                [sys.executable, str(log_py), "add", "--severity", "minor",
                 "--scene", f"场景\t{idx}", "--symptom", f"问题\n{idx}", "--evidence", "ev"],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(res.returncode, 0, res.stderr)
        counts, warns = registry.read_inbox(target)
        self.assertEqual(warns, [])
        self.assertEqual(counts["minor_open"], 3)
        self.assertTrue(counts["triggered"])

        # 置 resolved 无证据必须被拒，带证据通过
        bad_resolve = subprocess.run(
            [sys.executable, str(log_py), "set", "1", "--status", "resolved"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(bad_resolve.returncode, 1)
        good_resolve = subprocess.run(
            [sys.executable, str(log_py), "set", "1", "--status", "resolved", "--evidence", "results.tsv#L2"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(good_resolve.returncode, 0, good_resolve.stdout)
        counts2, _ = registry.read_inbox(target)
        self.assertFalse(counts2["triggered"])

        # bump 代次 +1，深度只升不降
        bump_ok = subprocess.run(
            [sys.executable, str(log_py), "bump", "--depth", "L2"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(bump_ok.returncode, 0, bump_ok.stdout)
        manifest = json.loads((target / "pangu.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["generation"], 1)
        self.assertEqual(manifest["depth"], "L2")
        bump_downgrade = subprocess.run(
            [sys.executable, str(log_py), "bump", "--depth", "L1"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(bump_downgrade.returncode, 1)

    def test_multi_root_duplicate_lineage_and_evolution_queue(self):
        r1, r2 = self.root / "workspace", self.root / "installed"
        m = good_manifest("twin")
        make_skill(r1, "twin", manifest=m, inbox=INBOX_HEADER)
        make_skill(r2, "twin", manifest=m, inbox=(
            INBOX_HEADER + "2026-11-02\tblocker\t导出\t白屏\tlog\topen\n"))
        scan = subprocess.run(
            [sys.executable, str(SCRIPTS / "registry.py"), str(r1), str(r2), "--json"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(scan.returncode, 0, scan.stderr)
        data = json.loads(scan.stdout)
        self.assertEqual(len(data["duplicates"]), 1)
        self.assertEqual(data["evolution_queue"][0]["priority"], "P0")

    def test_collect_feedback_and_deploy_across_replicas(self):
        r1, r2 = self.root / "workspace", self.root / "installed"
        m1 = good_manifest("twin")
        m1["generation"] = 1
        m2 = good_manifest("twin")
        m2["generation"] = 0
        s1 = make_skill(r1, "twin", manifest=m1, inbox=INBOX_HEADER)
        s2 = make_skill(r2, "twin", manifest=m2, inbox=(
            INBOX_HEADER + "2026-11-02T10:00\tblocker\t运行时\t副本触发报错\tstack.log\topen\n"))

        # 1. --collect-feedback 从副本回收新反馈到权威源，重复运行幂等
        c1 = subprocess.run(
            [sys.executable, str(SCRIPTS / "registry.py"), str(r1), str(r2), "--collect-feedback", "--json"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(c1.returncode, 0, c1.stderr)
        d1 = json.loads(c1.stdout)
        self.assertEqual(d1["collected_feedback"], {"twin": 1})
        counts_src, _ = registry.read_inbox(s1)
        self.assertEqual(counts_src["blocker_major"], 1)

        c2 = subprocess.run(
            [sys.executable, str(SCRIPTS / "registry.py"), str(r1), str(r2), "--collect-feedback", "--json"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(json.loads(c2.stdout)["collected_feedback"], {})

        # 2. --deploy 将进化后的权威源同步回副本，且保留副本收件箱并写快照
        (s1 / "SKILL.md").write_text("# evolved v2\n", encoding="utf-8")
        dep = subprocess.run(
            [sys.executable, str(SCRIPTS / "registry.py"), str(r1), str(r2), "--deploy", "--json"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(dep.returncode, 0, dep.stderr)
        d_dep = json.loads(dep.stdout)
        self.assertEqual(len(d_dep["deployed_replicas"]), 1)
        self.assertEqual((s2 / "SKILL.md").read_text(encoding="utf-8"), "# evolved v2\n")
        self.assertTrue((s2 / "evidence" / "snapshots").is_dir())

    def test_next_step_state_machine_and_quick_tier_checkpoints(self):
        target = self.root / "nav-skill"
        subprocess.run(
            [sys.executable, str(SCRIPTS / "scaffold.py"), str(target), "--name", "nav-skill"],
            check=True, capture_output=True, text=True, encoding="utf-8")
        nav = subprocess.run(
            [sys.executable, str(SCRIPTS / "next_step.py"), str(target), "--tier", "quick", "--json"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(nav.returncode, 1)
        info = json.loads(nav.stdout)
        self.assertEqual(info["current_stage"], "Phase0.5")
        blocking_map = {s["id"]: s["blocking"] for s in info["stages"]}
        self.assertEqual(blocking_map, {
            "Phase0.5": True,
            "F1": False,
            "F2": False,
            "F3": False,
            "F3.6": False,
            "F4-F5": True,
        })

    def test_one_command_installer_and_self_check(self):
        dest = self.root / "installed_skills"
        inst = subprocess.run(
            [sys.executable, str(SCRIPTS / "install.py"), "--dest", str(dest), "--check", "--json"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(inst.returncode, 0, inst.stderr + inst.stdout)
        payload = json.loads(inst.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["installed"][0]["skill"], "pangu-create")
        self.assertEqual(payload["installed"][0]["quality_check"], "11/11")
        self.assertEqual(payload["installed"][0]["seal"], "ok")
        self.assertTrue((dest / "pangu-create" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
