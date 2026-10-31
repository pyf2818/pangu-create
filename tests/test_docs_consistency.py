#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档口径一致性守卫：同坑二现必须机器化拦截（E5 免疫系统）。

背景（2026-10-31 独立文档审计）：SKILL.md 与 references/ 之间出现 9 处口径漂移
（F3.5 检查点跳段、三件/四件硬产物、观感两档/三档、量化表指针错指、AP 编号错位、
F0.5 命名、质量维度卡列漂移、迭代轮数上下限冲突、配方数量口径）——全是「多文档
跳读」时的执行分叉点。本文件把这些已修复的漂移固化为机器断言，复发即 FAIL。
"""

import re
import sys
import unittest
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import registry  # noqa: E402
import scaffold  # noqa: E402


def read(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


SKILL = read("SKILL.md")
FORGE = read("references", "forge.md")
EVOLVE = read("references", "evolve.md")
TESTING = read("references", "testing.md")
OUTPUT_Q = read("references", "output-quality.md")


class PipelineOrderTest(unittest.TestCase):
    def test_f35_checkpoint_leads_to_f36_not_f4(self):
        self.assertIn("进入 F3.6", FORGE,
                      "forge.md F3.5 检查点必须指向 F3.6（跳段会整段跳过可执行预检）")
        readme_ckpt = [ln for ln in FORGE.splitlines() if "README.md 草稿" in ln and "CHECKPOINT" in ln]
        self.assertTrue(readme_ckpt, "forge.md 缺 README 检查点行")
        self.assertTrue(all("进入 F3.6" in ln for ln in readme_ckpt),
                        "README 检查点之后是 F3.6 可执行预检，不许直接进 F4")

    def test_hard_artifacts_count_is_four_everywhere(self):
        self.assertIn("四件硬产物", FORGE, "forge.md F3.6 应为四件硬产物（与 SKILL.md 同口径）")
        self.assertIn("四件硬产物", SKILL)
        self.assertNotIn("三件硬产物", FORGE + SKILL)
        for ln in FORGE.splitlines():
            if "CHECKPOINT" in ln and "产物" in ln:
                self.assertIn("四件产物", ln, f"检查点产物计数漂移: {ln.strip()[:60]}")


class NamingAndPointerTest(unittest.TestCase):
    def test_no_stray_f05_alias(self):
        for name, text in (("forge.md", FORGE), ("testing.md", TESTING), ("evolve.md", EVOLVE)):
            self.assertIsNone(re.search(r"(?<!Phase )\bF0\.5\b", text),
                              f"{name} 残留 F0.5 别名（统一为 Phase 0.5）")

    def test_quant_table_pointer_targets_forge(self):
        self.assertIn("量化通过标准表见 [references/forge.md]", SKILL)
        self.assertNotIn("量化通过标准表见 [references/testing.md]", SKILL)

    def test_paired_downgrade_cites_ap19(self):
        self.assertIn("AP-19 记账污染", FORGE)
        self.assertNotIn("AP-14 记账污染", FORGE)


class ObservationGateWordingTest(unittest.TestCase):
    def test_visual_gate_is_three_tier_everywhere(self):
        self.assertIn("三档", SKILL, "SKILL.md 观感验证应为三档（及格/差距/盲评）")
        self.assertNotIn("及格线 + 惊喜线", SKILL)
        self.assertIn("及格线", FORGE)
        self.assertIn("盲评线", FORGE)

    def test_iteration_cap_is_upper_bound_not_quota(self):
        self.assertNotIn("产出型 ≥3 轮", TESTING + OUTPUT_Q + SKILL,
                         "「≥3 轮」会把上限当配额，首轮全绿的 skill 被迫空转")
        for name, text in (("SKILL.md", SKILL), ("output-quality.md", OUTPUT_Q), ("testing.md", TESTING)):
            self.assertTrue(re.search(r"(上限 ?3 轮|≤3 轮)", text),
                            f"{name} 缺「上限 3 轮」口径")
        self.assertIn("首轮即全绿可提前出厂", OUTPUT_Q + TESTING if isinstance(OUTPUT_Q + TESTING, str) else "")


class QualityDimensionCardTest(unittest.TestCase):
    def test_card_columns_match_between_forge_and_templates(self):
        templates = read("references", "templates.md")
        for name, text in (("forge.md", FORGE), ("templates.md", templates)):
            self.assertRegex(text, r"\| 负重维度 \| 本质约束（第一性） \|",
                             f"{name} 质量维度卡缺「本质约束（第一性）」列（与对比如 F1.0 维度对照表是另一张表，不得混用）")


class InboxAndRegistryContractTest(unittest.TestCase):
    def test_inbox_header_matches_across_scaffold_and_registry(self):
        scaffold_cols = scaffold.INBOX_HEADER.strip().split("\t")
        self.assertEqual(scaffold_cols, registry.INBOX_HEADER,
                         "scaffold 写出的收件箱表头与 registry 解析口径不一致")

    def test_evolution_contract_item8_exists(self):
        self.assertIn("反馈落箱（自动触发的捕获点）", EVOLVE)
        self.assertIn("进化契约 #8", SKILL)

    def test_lineage_manifest_schema_is_declared(self):
        manifest = scaffold.make_manifest("demo", adopted=False, forge_date="2026-10-31",
                                          skill_type="output", domain="测试")
        self.assertEqual(manifest["schema"], 1)
        self.assertEqual(manifest["forged_by"], "pangu-create")
        self.assertIn(manifest["pangu_version"], read("pangu.json"),
                      "scaffold PANGU_VERSION 与盘古自身 pangu.json 声明不一致")


if __name__ == "__main__":
    unittest.main(verbosity=1)
