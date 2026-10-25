#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""故障注入：对验证器本身做真实攻击，确认空洞/伪造/过期证据会被拒绝。

覆盖类别：invalid_evidence（伪造回执、过期哈希、套件不符）、extreme_input
（非法命令、越界路径、畸形清单）。本文件出口的标记由 tests/verification.json
的 failure-injection suite 断言，不能靠注释或手写结论通过。
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import verify_skill as V  # noqa: E402

PASSED = []
FAILED = []


def check(name, ok, evidence):
    (PASSED if ok else FAILED).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name} :: {evidence}")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def manifest(root, suites):
    write(root / "tests" / "verification.json",
          json.dumps({"version": 1, "suites": suites}, ensure_ascii=False, indent=2))


def behavior_suite(suite_id="behavior-ok", script="tests/test_ok.py"):
    return {"id": suite_id, "kind": "behavior",
            "command": ["python", script], "timeout_seconds": 30,
            "expect": {"exit_code": 0, "stdout_regex": "BEHAVIOR_OK"}}


def injection_suite(script="tests/test_inject.py"):
    return {"id": "failure-injection", "kind": "failure_injection",
            "categories": ["invalid_evidence", "extreme_input"],
            "command": ["python", script], "timeout_seconds": 30,
            "expect": {"exit_code": 0, "stdout_regex": "INJECT_OK"}}


def make_skill(base, suites=None, with_promise=True, with_trio=False):
    root = Path(base) / "demo-skill"
    root.mkdir(parents=True)
    write(root / "SKILL.md", "---\nname: demo-skill\ndescription: demo\n---\n# demo\n")
    write(root / "scripts" / "verify.py", "print('ok')\n")
    write(root / "tests" / "test_ok.py", "print('BEHAVIOR_OK')\n")
    write(root / "tests" / "test_inject.py", "print('INJECT_OK')\n")
    manifest(root, suites or [behavior_suite(), injection_suite()])
    if with_promise:
        write(root / "references" / "promise-table.md", """# 承诺

| 承诺 | 断言 | 测试 ID | 证据 |
|---|---|---|---|
| 打开即可用 | 输出 BEHAVIOR_OK | behavior-ok | evidence/verification.json#behavior-ok |
| 异常输入有处置 | 注入脚本输出 INJECT_OK | failure-injection | evidence/verification.json#failure-injection |
| 结果可复现 | 重复执行同一输出 | behavior-ok | evidence/verification.json#behavior-ok |
""")
    if with_trio:
        (root / ".git").mkdir()
        write(root / "test-prompts.json", "[]\n")
        write(root / "results.tsv", "timestamp\tstatus\n")
    return root


def contract_error(root):
    _, error = V.load_contract(root)
    return error


def main():
    tmp = tempfile.TemporaryDirectory()
    try:
        base = Path(tmp.name)

        print("[A] 非法清单")
        root = make_skill(base / "a")
        bad = behavior_suite()
        bad["command"] = "python tests/test_ok.py"
        manifest(root, [bad, injection_suite()])
        check("A1 拒绝 shell 字符串命令", bool(contract_error(root)), contract_error(root))

        root = make_skill(base / "b")
        bad = behavior_suite()
        bad["command"] = ["python", "-c", "print(1)"]
        manifest(root, [bad, injection_suite()])
        check("A2 拒绝 python -c", bool(contract_error(root)), contract_error(root))

        root = make_skill(base / "c")
        bad = behavior_suite()
        bad["command"] = ["python", "../evil.py"]
        manifest(root, [bad, injection_suite()])
        check("A3 拒绝越界路径", bool(contract_error(root)), contract_error(root))

        root = make_skill(base / "d")
        bad = behavior_suite()
        bad["artifacts"] = "logs/x.json"
        manifest(root, [bad, injection_suite()])
        check("A4 拒绝非数组 artifacts", bool(contract_error(root)), contract_error(root))

        root = make_skill(base / "e")
        bad = injection_suite()
        bad["categories"] = ["extreme_input"]
        manifest(root, [behavior_suite(), bad])
        check("A5 拒绝不足两类注入", bool(contract_error(root)), contract_error(root))

        print("[B] 承诺绑定")
        root = make_skill(base / "f")
        ok, detail = V.gate_promise(root)
        check("B1 合法承诺矩阵通过", ok, detail)

        write(root / "references" / "promise-table.md", """| 承诺 | 断言 | 测试 ID | 证据 |
|---|---|---|---|
| a | b | `python tests/test_ok.py` | evidence/verification.json#behavior-ok |
| c | d | behavior-ok | evidence/verification.json#behavior-ok |
| e | f | behavior-ok | evidence/verification.json#behavior-ok |
""")
        ok, detail = V.gate_promise(root)
        check("B2 拒绝命令文本冒充测试 ID", not ok, detail)

        write(root / "references" / "promise-table.md", """| 承诺 | 断言 | 测试 ID | 证据 |
|---|---|---|---|
| a | b | behavior-ok | evidence/verification.json#failure-injection |
| c | d | behavior-ok | evidence/verification.json#behavior-ok |
| e | f | behavior-ok | evidence/verification.json#behavior-ok |
""")
        ok, detail = V.gate_promise(root)
        check("B3 拒绝证据指针串号", not ok, detail)

        print("[C] 回执核验")
        root = make_skill(base / "g")
        report = V.execute_contract(root)
        V_path = root / V.EVIDENCE_REL
        V_path.parent.mkdir(parents=True, exist_ok=True)
        V_path.write_text(json.dumps(report), encoding="utf-8")
        ok, detail = V.gate_evidence(root)
        check("C1 新鲜完整回执通过", ok, detail)

        write(root / "SKILL.md", "changed\n")
        ok, detail = V.gate_evidence(root)
        check("C2 源码变化后回执过期", not ok, detail)

        root = make_skill(base / "h")
        report = V.execute_contract(root)
        V_path = root / V.EVIDENCE_REL
        V_path.parent.mkdir(parents=True, exist_ok=True)
        V_path.write_text(json.dumps(report), encoding="utf-8")
        manifest(root, [behavior_suite(), injection_suite(), behavior_suite("extra")])
        ok, detail = V.gate_evidence(root)
        check("C3 清单变化后回执过期", not ok, detail)

        root = make_skill(base / "i")
        report = V.execute_contract(root)
        report["suites"][0]["status"] = "fail"
        V_path = root / V.EVIDENCE_REL
        V_path.parent.mkdir(parents=True, exist_ok=True)
        V_path.write_text(json.dumps(report), encoding="utf-8")
        ok, detail = V.gate_evidence(root)
        check("C4 含失败套件的回执被拒", not ok, detail)

        root = make_skill(base / "j")
        partial = V.execute_contract(root, ["behavior-ok"])
        V_path = root / V.EVIDENCE_REL
        V_path.parent.mkdir(parents=True, exist_ok=True)
        V_path.write_text(json.dumps(partial), encoding="utf-8")
        ok, detail = V.gate_evidence(root)
        check("C5 部分回执被拒", not ok, detail)

        root = make_skill(base / "k")
        V_path = root / V.EVIDENCE_REL
        V_path.parent.mkdir(parents=True, exist_ok=True)
        V_path.write_text("{not json", encoding="utf-8")
        ok, detail = V.gate_evidence(root)
        check("C6 畸形回执被拒", not ok, detail)

        print("[D] 环境故障分流")
        root = make_skill(base / "l")
        write(root / "tests" / "test_env.py", "import sys\nsys.exit(2)\n")
        manifest(root, [{"id": "env", "kind": "behavior",
                         "command": ["python", "tests/test_env.py"],
                         "timeout_seconds": 30, "expect": {"exit_code": 0}}])
        report = V.execute_contract(root)
        check("D1 环境故障 exit 2 且不算通过",
              report["overall_exit_code"] == 2 and report["status"] == "env_error",
              f"exit={report['overall_exit_code']} status={report['status']}")

        print("[E] CLI 交付判定")
        root = make_skill(base / "m", with_trio=True)
        cli = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_skill.py"),
             str(root), "--type", "text", "--execute", "--json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        data = json.loads(cli.stdout)
        check("E1 --execute 全过才 delivery_ready",
              cli.returncode == 0 and data["delivery_ready"] and data["pass"],
              f"exit={cli.returncode} ready={data['delivery_ready']}")

        cli = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_skill.py"),
             str(root), "--type", "text", "--check", "--json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        data = json.loads(cli.stdout)
        check("E2 --check 可复验新鲜回执",
              cli.returncode == 0 and data["delivery_ready"],
              f"exit={cli.returncode} ready={data['delivery_ready']}")

        write(root / "SKILL.md", "changed after evidence\n")
        cli = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_skill.py"),
             str(root), "--type", "text", "--check", "--json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        data = json.loads(cli.stdout)
        check("E3 --check 拦截过期回执",
              cli.returncode == 1 and not data["delivery_ready"],
              f"exit={cli.returncode} ready={data['delivery_ready']}")
    finally:
        tmp.cleanup()

    print(f"\nFAILURE_INJECTION {len(PASSED)} PASS / {len(FAILED)} FAIL")
    if FAILED:
        for name in FAILED:
            print(f"  - {name}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
